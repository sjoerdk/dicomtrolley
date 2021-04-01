"""Models the MINT DICOM exchange protocol
See:
https://code.google.com/archive/p/medical-imaging-network-transport/downloads
"""
from itertools import chain
from typing import (
    ClassVar,
    List,
    Tuple,
)
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from pydantic.main import BaseModel
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset

from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.query import Query


class MintObject(BaseModel):
    """Python representation of MINT xml"""

    xml_element: ClassVar[str]

    data: Dataset  # all DICOM elements returned with query
    uid: str  # StudyInstanceUID. Also in data, provided for convenience

    def __str__(self):

        return type(self).__name__ + " " + self.uid

    def all_instances(self):
        raise NotImplementedError()


class MintInstance(MintObject):
    xml_element: ClassVar = "{http://medical.nema.org/mint}instance"
    parent: "MintSeries"

    @classmethod
    def init_from_element(cls, element, parent):
        data = parse_attribs(element)

        return cls(data=data, uid=data.SOPInstanceUID, parent=parent)

    def all_instances(self):
        """Conforms to similar methods in Series and Study"""

        return [self]


class MintSeries(MintObject):
    xml_element: ClassVar = "{http://medical.nema.org/mint}series"
    instances: Tuple[MintInstance, ...]
    parent: "MintStudy"

    @classmethod
    def init_from_element(cls, element, parent):
        data = parse_attribs(element)

        series = cls(
            data=data,
            uid=data.SeriesInstanceUID,
            parent=parent,
            instances=tuple(),
        )
        series.instances = tuple(
            MintInstance.init_from_element(x, parent=series)
            for x in element.findall(MintInstance.xml_element)
        )

        return series

    def all_instances(self):
        """Return each instance contained in this series"""

        return self.instances


class MintStudy(MintObject):
    xml_element: ClassVar = "{http://medical.nema.org/mint}study"

    mint_uuid: str  # non-DICOM MINT-only id for this series
    last_modified: str
    series: Tuple[MintSeries, ...]

    @classmethod
    def init_from_element(cls, element):
        data = parse_attribs(element)

        study = cls(
            data=data,
            uid=data.StudyInstanceUID,
            mint_uuid=element.attrib["studyUUID"],
            last_modified=element.attrib["lastModified"],
            series=tuple(),
        )
        study.series = tuple(
            MintSeries.init_from_element(x, parent=study)
            for x in element.findall(MintSeries.xml_element)
        )

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

    def all_instances(self) -> List[MintInstance]:
        """Return each instance contained in this study"""

        return list(chain(*(x.instances for x in self.series)))


class MintAttribute:
    """A DICOM element like PatientID=001"""

    xml_element = "{http://medical.nema.org/mint}attr"


class Mint:
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

    def find_studies(self, query: Query) -> List[MintStudy]:
        """Get all studies matching query

        Parameters
        ----------
        query: Query
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

    def find_study(self, query: Query) -> MintStudy:
        """Like find_studies, but guarantees exactly one result. Exception if not.

        This method is meant for searches that contain unique identifiers like
        StudyInstanceUID, AccessionNumber, SeriesInstanceUID.

        Notes
        -----
        If you want to get multiple studies at once, use find_studies(). This is
        more efficient as it requires only a single call to the server

        Raises
        ------
        DICOMTrolleyException
            If no results or more than one result is returned by query
        """
        results = self.find_studies(query)
        if len(results) == 0 or len(results) > 1:
            raise DICOMTrolleyException(
                f"Expected exactly one study for query '{query}', but"
                f" found {len(results)}"
            )
        return results[0]


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
