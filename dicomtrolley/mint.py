"""Models the MINT DICOM exchange protocol
See:
https://code.google.com/archive/p/medical-imaging-network-transport/downloads
"""
import datetime
from typing import ClassVar, List, Optional, Sequence, Set
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from pydantic.class_validators import validator
from pydantic.main import BaseModel
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset

from dicomtrolley.core import DICOMObject, Instance, Searcher, Series, Study
from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.fields import (
    InstanceLevel,
    SeriesLevel,
    SeriesLevelPromotable,
    StudyLevel,
)


class QueryLevels:
    STUDY = "STUDY"
    SERIES = "SERIES"
    INSTANCE = "INSTANCE"

    ALL = {STUDY, SERIES, INSTANCE}


class MintObject(DICOMObject):
    """Python representation of MINT xml"""

    xml_element: ClassVar[str]

    def all_instances(self):
        """
        Returns
        -------
        List[MintInstance]
            All instances contained in this object
        """
        raise NotImplementedError()


class MintInstance(Instance, MintObject):
    xml_element: ClassVar = "{http://medical.nema.org/mint}instance"
    parent: "MintSeries"

    @classmethod
    def init_from_element(cls, element, parent):
        data = parse_attribs(element)

        return cls(data=data, uid=data.SOPInstanceUID, parent=parent)


class MintSeries(Series, MintObject):
    xml_element: ClassVar = "{http://medical.nema.org/mint}series"
    instances: List[MintInstance]
    parent: "MintStudy"

    @classmethod
    def init_from_element(cls, element, parent):
        data = parse_attribs(element)

        series = cls(
            data=data,
            uid=data.SeriesInstanceUID,
            parent=parent,
            instances=[],
        )
        for x in element.findall(MintInstance.xml_element):
            series.instances.append(
                MintInstance.init_from_element(x, parent=series)
            )

        return series


class MintStudy(Study, MintObject):
    xml_element: ClassVar = "{http://medical.nema.org/mint}study"

    mint_uuid: str  # non-DICOM MINT-only id for this series
    last_modified: str
    series: List[MintSeries]

    @classmethod
    def init_from_element(cls, element):
        data = parse_attribs(element)

        study = cls(
            data=data,
            uid=data.StudyInstanceUID,
            mint_uuid=element.attrib["studyUUID"],
            last_modified=element.attrib["lastModified"],
            series=[],
        )
        for x in element.findall(MintSeries.xml_element):
            study.series.append(MintSeries.init_from_element(x, parent=study))

        return study

    def dump_content(self) -> str:
        """Dump entire contents of this study and containing series, instances

        For quick inspection in scripts
        """

        output = [str(self.data)]
        for series in self.series:
            output.append(str(series.data))
            for instance in series.instances:
                output.append(str(instance.data))
        return "\n".join(output)


class MintAttribute:
    """A DICOM element like PatientID=001"""

    xml_element = "{http://medical.nema.org/mint}attr"


class MintQuery(BaseModel):
    """Things you can search for with the MINT find DICOM studies function

    Notes
    -----
    * All string arguments support (*) as a wildcard
    * non-pep8 parameter naming format follows MINT url parameters naming
    """

    # String parameters (wildcards allowed)
    studyInstanceUID: str = ""
    accessionNumber: str = ""
    patientName: str = ""
    patientID: str = ""
    modalitiesInStudy: str = ""
    institutionName: str = ""
    patientSex: str = ""
    studyDescription: str = ""
    institutionalDepartmentName: str = ""

    # date search parameters
    patientBirthDate: Optional[datetime.date]
    minStudyDate: Optional[datetime.datetime]
    maxStudyDate: Optional[datetime.datetime]

    # meta parameters: how to return results
    queryLevel: str = QueryLevels.STUDY  # to which depth to return results
    includeFields: List[str] = []  # which dicom fields to return
    limit: int = 0  # how many results to return. 0 = all

    class Config:
        extra = "forbid"  # raise ValueError when passing an unknown keyword to init

    def __str__(self):
        return str(self.as_parameters())

    @validator("maxStudyDate", always=True)
    def min_max_study_date_xor(cls, value, values):  # noqa: B902, N805
        """Min and max should both be given or both be empty"""
        if values.get("minStudyDate", None) and not value:
            raise ValueError(
                f"minStudyDate parameter was passed "
                f"({values['minStudyDate']}), "
                f"but maxStudyDate was not. Both need to be given"
            )
        elif value and not values.get("minStudyDate", None):
            raise ValueError(
                f"maxStudyDate parameter was passed ({value}), "
                f"but minStudyDate was not. Both need to be given"
            )
        return value

    @validator("includeFields")
    def include_fields_check(cls, include_fields, values):  # noqa: B902, N805
        """Include fields should be valid and match query level"""
        query_level = values["queryLevel"]
        valid_fields = get_valid_fields(query_level=query_level)
        for field in include_fields:
            if field not in valid_fields:
                raise ValueError(
                    f'"{field}" is not a valid include field for query '
                    f"level {query_level}. Valid fields: {valid_fields}"
                )
        return include_fields

    def as_parameters(self):
        """All non-empty query parameters. For use as url parameters"""
        parameters = {x: y for x, y in self.dict().items() if y}

        if "minStudyDate" in parameters:
            parameters["minStudyDate"] = parameters["minStudyDate"].strftime(
                "%Y%m%d"
            )

        if "maxStudyDate" in parameters:
            parameters["maxStudyDate"] = parameters["maxStudyDate"].strftime(
                "%Y%m%d"
            )

        if "patientBirthDate" in parameters:
            parameters["patientBirthDate"] = parameters[
                "patientBirthDate"
            ].strftime("%Y%m%d")

        if "includeFields" in parameters:
            parameters["includeFields"] = ",".join(parameters["includeFields"])

        return parameters


def get_valid_fields(query_level) -> Set[str]:
    """All fields that can be returned at the given MINT query level"""
    if query_level == QueryLevels.INSTANCE:
        return (
            StudyLevel.fields
            | SeriesLevel.fields
            | SeriesLevelPromotable.fields
            | InstanceLevel.fields
        )
    elif query_level == QueryLevels.SERIES:
        return (
            StudyLevel.fields
            | SeriesLevel.fields
            | SeriesLevelPromotable.fields
        )
    elif query_level == QueryLevels.STUDY:
        return StudyLevel.fields
    else:
        raise ValueError(
            f'Unknown query level "{query_level}". Valid values '
            f"are {QueryLevels.ALL}"
        )


class Mint(Searcher):
    """A connection to a mint server"""

    def __init__(self, session, url):
        """
        Parameters
        ----------
        session: requests.session
            A logged in session over which MINT calls can be made
        url: str
            MINT endpoint, including protocol and port. Like https://server:8080/mint
        """

        self.session = session
        self.url = url

    def find_studies(self, query: MintQuery) -> Sequence[MintStudy]:
        """Get all studies matching query

        Parameters
        ----------
        query: MintQuery
            Search based on these parameters. See Query object

        Returns
        -------
        List[MintStudy]
            All studies matching query. Might be empty.
            If Query.QueryLevel is SERIES or INSTANCE, MintStudy objects might
            contain MintSeries and MintInstance instances.
        """
        search_url = self.url + "/studies"
        response = self.session.get(search_url, params=query.as_parameters())
        return parse_mint_studies_response(response.text)


def parse_mint_studies_response(xml_raw) -> List[MintStudy]:
    """Parse the xml response to a MINT find DICOM studies call

    Raises
    ------
    DICOMTrolleyException
        If parsing fails
    """
    try:
        studies = ElementTree.fromstring(xml_raw).findall(
            MintStudy.xml_element
        )
    except ParseError:
        raise DICOMTrolleyException(
            f"Could not parse server response as MINT "
            f"studies. Response was: {xml_raw}"
        )
    return [MintStudy.init_from_element(x) for x in studies]


def parse_attribs(element):
    """Parse xml attributes from a MINT find call to DICOM elements in a Dataset"""
    dataset = Dataset()
    for child in element.findall(MintAttribute.xml_element):
        attr = child.attrib
        val = attr.get("val", "")  # treat missing val as empty
        dataset[attr["tag"]] = DataElement(attr["tag"], attr["vr"], val)

    return dataset


MintInstance.update_forward_refs()  # enables pydantic validation
MintSeries.update_forward_refs()
MintStudy.update_forward_refs()
