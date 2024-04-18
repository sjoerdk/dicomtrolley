"""Mock responses

Based on live responses from a server running Vitrea Connection 8.2.0.1
"""
import json
import re
import urllib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Pattern, Union

from requests_mock import ANY
from requests_toolbelt.multipart.encoder import MultipartEncoder

from dicomtrolley.core import InstanceReference, QueryLevels
from dicomtrolley.xml_templates import (
    A_RAD69_RESPONSE_SOAP_HEADER,
    RAD69_SOAP_RESPONSE_NOT_FOUND,
)
from tests.factories import (
    create_dicom_bytestream,
    quick_dataset,
)


@dataclass
class MockResponse:
    """A fake server response that can be fed to response-mock easily"""

    url: Union[str, Pattern[str]]
    status_code: int = 200
    method: str = "GET"
    text: Union[str, Callable[[Any, Any], Any]] = ""
    content: bytes = field(default_factory=bytes)
    json: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    exc = None

    def as_dict(self):
        """Non-empty and non-None items as dictionary

        Facilitates use as keyword arguments. Like
        some_method(**MockResponse().as_dict())
        """
        return {x: y for x, y in self.__dict__.items() if y}


@dataclass
class MockResponseList:
    """Holds multiple MockResponses mapped to the same URL and Method.

    See [requests-mock reference](https://requests-mock.readthedocs.io/en/
    latest/response.html#response-lists)


    Notes
    -----
    MockResponse instances url and method parameters are overwritten by the
    responselists' fields when setting these responses
    """

    url: Union[str, Pattern[str]]
    method: str
    responses: List[MockResponse]


class MockUrls:
    """For re-using across the code"""

    LOGIN = "https://server/login"
    MINT_URL = "https://server/mint"
    WADO_URI_URL = "https://server/wado_uri"
    WADO_RS_URL = "https://server/wado_rs"
    RAD69_URL = "https://server/rids"
    QIDO_RS_URL = "https://server/qido"


class MockWadoParameters:
    """Calling mock wado with this will trigger mock response"""

    study_instance_uid = "111"
    series_instance_uid = "222"
    sop_instance_uid = "333"

    @classmethod
    def as_dict(cls):
        return {
            "studyUID": cls.study_instance_uid,
            "seriesUID": cls.series_instance_uid,
            "objectUID": cls.sop_instance_uid,
        }

    @classmethod
    def as_wado_query_string(cls):
        params = cls.as_dict()
        params.update(
            {"requestType": "WADO", "contentType": "application/dicom"}
        )
        return "?" + urllib.parse.urlencode(params)

    @classmethod
    def as_instance_reference(cls):
        return InstanceReference(
            study_uid=cls.study_instance_uid,
            series_uid=cls.series_instance_uid,
            instance_uid=cls.sop_instance_uid,
        )


LOGIN_SUCCESS = MockResponse(
    url=MockUrls.LOGIN,
    status_code=200,
    json={"access_token": "123MOCKACCESSTOKEN", "token_type": "Bearer"},
    method="POST",
)
LOGIN_DENIED = MockResponse(
    url=MockUrls.LOGIN,
    text="Login failed: bad username/password",
    status_code=401,
    reason="Unauthorized",
    method="POST",
)

MINT_401 = MockResponse(
    url=MockUrls.MINT_URL,
    status_code=401,
    reason="Unauthorized",
    method="GET",
    text="""<html>
<head>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8"/>
<title>Error 401 you need to log in to access this page.</title>
</head>
<body><h2>HTTP ERROR 401</h2>
<p>Problem accessing /rest/api/vault/mint/studies. Reason:
<pre>    you need to log in to access this page.</pre></p><hr>
<a href="http://eclipse.org/jetty">Powered by Jetty://
 9.4.12.v20180830</a><hr/>

</body>
</html>""",
)

LOGIN_IMPAX_INITIAL = MockResponse(
    url=MockUrls.LOGIN, text="whatever", status_code=200, method="GET"
)

LOGIN_SUCCESS_IMPAX = MockResponse(
    url=re.compile(r".*j_security_check\?j_username=.*&j_password=.*"),
    text="<html> Access to the requested resource has been denied </html>",
    status_code=403,  # I have no idea why this is. But it is.
    method="GET",
)

LOGIN_DENIED_IMPAX = MockResponse(
    url=re.compile(r".*j_security_check\?j_username=.*&j_password=.*"),
    text="<html> lots of content and then: Login Failed! etc. </html>",
    status_code=200,
    method="GET",
)

MINT_SEARCH_MOCK_STUDY_UID = "1.2.340.114850.2.857.2.793263.2.125336546.1"

MINT_SEARCH_STUDY_LEVEL = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=STUDY",
    text="<?xml version='1.0' encoding='UTF-3'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" queryfields="PatientName=B*" '
    'includefields="StudyInstanceUID,PatientName,PatientID"><study '
    'studyUUID="35997945-c535-4570-3c1f-3514f27695e9" version="1" '
    'lastModified="2021-08-09T06:42:04.325Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="TEST^K.J.M." /><attr '
    'tag="0020000d" vr="UI" val="' + MINT_SEARCH_MOCK_STUDY_UID + '" />'
    '</study><study studyUUID="c19a038a-fe0f-4e4b-b690-a895bd8db1e2" version="1"'
    ' lastModified="2021-08-09T06:42:26.722Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="TEST^K.J.M." />'
    '<attr tag="0020000d" vr="UI" '
    'val="' + MINT_SEARCH_MOCK_STUDY_UID + '" /></study><study '
    'studyUUID="26582e0f-473e-422d-9c24-12ebdbc6dac3" version="1" '
    'lastModified="2021-08-09T06:42:10.598Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="BEELDEN^W^I L" /><attr '
    'tag="0020000d" vr="UI" val="' + MINT_SEARCH_MOCK_STUDY_UID + '" />'
    "</study></studySearchResults>",
)

# exactly one study
MINT_SEARCH_STUDY_LEVEL_SINGLE = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=STUDY",
    text="<?xml version='1.0' encoding='UTF-3'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" queryfields="PatientName=B*" '
    'includefields="StudyInstanceUID,PatientName,PatientID"><study '
    'studyUUID="35997945-c535-4570-3c1f-3514f27695e9" version="1" '
    'lastModified="2021-08-09T06:42:04.325Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="TEST^K.J.M." /><attr '
    'tag="0020000d" vr="UI" val="' + MINT_SEARCH_MOCK_STUDY_UID + '" />'
    "</study></studySearchResults>",
)

MINT_SEARCH_SERIES_LEVEL = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=SERIES",
    text="<?xml version='1.0' encoding='UTF-8'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" query_level="SERIES" '
    'queryfields="PatientName=B*" includefields="StudyInstanceUID,PatientName,'
    'PatientID"><study studyUUID="26532e0f-478e-422d-9c24-12ebdbc6dac8" '
    'version="1" lastModified="2021-03-09T06:42:10.593Z"><series><attr '
    'tag="0020000e" vr="UI" '
    'val="1.2.40.0.13.1.31997853020103855051756062351916846110" /></series>'
    '<series><attr tag="0020000e" vr="UI" '
    'val="1.2.840.113619.2.239.1783.1568025913.0.105" /></series><series><attr '
    ' tag="0020000e" vr="UI" val="1.2.840.113619.2.239.1783.1568025913.0.76" />'
    '</series><attr tag="00100020" vr="LO" val="1392052" /><attr tag="00100010"'
    ' vr="PN" val="BEELDENZORG^W^I L" /><attr tag="0020000d" vr="UI" '
    'val="' + MINT_SEARCH_MOCK_STUDY_UID + '" /></study><study'
    ' studyUUID="85997945-c585-4570-8c1f-8514f27695e9" version="1" '
    'lastModified="2021-03-09T06:42:04.825Z"><series><attr tag="0020000e"'
    ' vr="UI" val="1.2.40.0.13.1.202066129828111990737107018349786560571"'
    ' /></series><series><attr tag="0020000e" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.2.1.20201105.84519.348" />'
    '</series><attr tag="00100020" vr="LO" val="1392052" /><attr tag="00100010"'
    ' vr="PN" val="BEELDENZORG^W^I L" /><attr tag="0020000d" '
    'vr="UI" val="' + MINT_SEARCH_MOCK_STUDY_UID + '" />'
    "</study></studySearchResults>",
)

MINT_SEARCH_SERIES_LEVEL_SINGLE = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=SERIES",
    text="<?xml version='1.0' encoding='UTF-8'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" query_level="SERIES" '
    'queryfields="PatientName=B*" includefields="StudyInstanceUID,PatientName,'
    'PatientID"><study studyUUID="26532e0f-478e-422d-9c24-12ebdbc6dac8" '
    'version="1" lastModified="2021-03-09T06:42:10.593Z"><series><attr '
    'tag="0020000e" vr="UI" '
    'val="1.2.40.0.13.1.31997853020103855051756062351916846110" /></series>'
    '<series><attr tag="0020000e" vr="UI" '
    'val="1.2.840.113619.2.239.1783.1568025913.0.105" /></series><series><attr '
    ' tag="0020000e" vr="UI" val="1.2.840.113619.2.239.1783.1568025913.0.76" />'
    '</series><attr tag="00100020" vr="LO" val="1392052" /><attr tag="00100010"'
    ' vr="PN" val="BEELDENZORG^W^I L" /><attr tag="0020000d" vr="UI" '
    'val="' + MINT_SEARCH_MOCK_STUDY_UID + '" /></study></studySearchResults>',
)

MINT_SEARCH_INSTANCE_LEVEL = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=INSTANCE",
    text="<?xml version='1.0' encoding='UTF-8'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" query_level="INSTANCE" '
    'queryfields="PatientName=B*" includefields="StudyInstanceUID,'
    'PatientName,PatientID"><study '
    'studyUUID="85997945-c585-4570-8c1f-8514f27695e9" version="1" '
    'lastModified="2021-03-09T06:42:04.825Z"><series><instance><attr '
    'tag="00080018" vr="UI" '
    'val="1.2.276.0.48.10201.3783241097.13128.1604568146536.12" />'
    '<attr tag="00020010" vr="UI" val="1.2.840.10008.1.2.1" /></instance>'
    '<attr tag="0020000e" vr="UI" '
    'val="1.2.40.0.13.1.202066129828111990737107018349786560571" />'
    '</series><series><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.1.20201105.84758.490" />'
    '<attr tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" />'
    '</instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.11.20201105.85329.902" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.70" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.12.20201105.85352.253" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.13.20201105.85408.42" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.14.20201105.85421.624" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.15.20201105.85439.320" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.16.20201105.85450.358" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.17.20201105.85513.576" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.70" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.18.20201105.85541.713" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.19.20201105.85551.608" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.2.20201105.84818.162" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.20.20201105.85606.956" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.50" /><'
    '/instance><instance><attr tag="00080018" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.3.21.20201105.85626.622" /><attr '
    'tag="00020010" vr="UI" val="1.2.840.10008.1.2.4.70" /></instance><attr '
    'tag="0020000e" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.2.1.20201105.84519.348" /><'
    '/series><attr tag="00100020" vr="LO" val="1392052" /><attr '
    'tag="00100010" vr="PN" val="BEELDENZORG^W^I L" /><attr tag="0020000d" '
    'vr="UI" val="' + MINT_SEARCH_MOCK_STUDY_UID + '" /><attr tag="00201208" '
    'vr="IS" val="200" /><attr tag="00100030" '
    'vr="DA" val="1900" /></study><'
    "/studySearchResults>",
)


# The IDS in the MINT response. To not have to copy-paste these in tests
MINT_SEARCH_INSTANCE_LEVEL_IDS = {
    "study_uid": MINT_SEARCH_MOCK_STUDY_UID,
    "series_uids": (
        "1.2.40.0.13.1.202066129828111990737107018349786560571",
        "1.2.840.113663.1500.1.460388269.2.1.20201105.84519.348",
    ),
}


# Will return mint study response to any mint server query

# a Response that contains a valid DICOM bytes
WADO_RESPONSE_DICOM = MockResponse(
    url=MockUrls.WADO_URI_URL + MockWadoParameters.as_wado_query_string(),
    content=create_dicom_bytestream(
        quick_dataset(
            PatientName="Jane",
            StudyDescription="Test",
            StudyInstanceUID=MockWadoParameters.study_instance_uid,
            SeriesInstanceUID=MockWadoParameters.series_instance_uid,
            SOPInstanceUID=MockWadoParameters.sop_instance_uid,
        )
    ),
)

WADO_RESPONSE_INVALID_DICOM = MockResponse(
    url=MockUrls.WADO_URI_URL + MockWadoParameters.as_wado_query_string(),
    content=bytes(1234),
)

WADO_RESPONSE_INVALID_NON_DICOM = MockResponse(
    url=MockUrls.WADO_URI_URL + MockWadoParameters.as_wado_query_string(),
    status_code=502,
    text="Error, server really does not know anymore",
)


MINT_SEARCH_STUDY_LEVEL_ERROR_500 = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=STUDY",
    status_code=500,
    text="""<html>
<head>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8"/>
<title>Error 500 Request failed.</title>
</head>
<body><h2>HTTP ERROR 500</h2>
<p>Problem accessing /rest/api/vault/mint/studies. Reason:
<pre>    Request failed.</pre></p><hr><a href="http://eclipse.org/jetty">Powered
 by Jetty:// 9.4.12.v20180830</a><hr/>

</body>
</html>""",
)


def quick_rad69_response(**kwargs):
    """A rad69 response containing a dataset with kwargs values. Kwargs should
    be valid DICOM fields and values

    Examples
    --------
    quick_rad69_response(PatientName="Jim")
    """
    return create_rad69_response_from_dataset(quick_dataset(**kwargs))


def create_rad69_response_from_dataset(dataset):
    """Create a multi-part rad69 response, with a soap part and a dicom byte stream"""
    return create_rad69_response_from_datasets([dataset])


def create_rad69_response_from_datasets(datasets, soap_header=None):
    """Create a multi-part rad69 response, with a soap part and a dicom byte stream"""
    return create_rad69_response(
        bytes_parts=[create_dicom_bytestream(dataset) for dataset in datasets],
        soap_header=soap_header,
    )


def create_rad69_response(bytes_parts, soap_header=None):
    """Create a multi-part rad69 response, with a soap part and the given list of
    bytes as subsequent parts. Each element in bytes_part should be the bytes for one
    dicom object
    """
    if not soap_header:
        soap_header = A_RAD69_RESPONSE_SOAP_HEADER

    # Recorded from response of a Vitrea connection 8 server
    multi_part_soap_response = MultipartEncoder(
        fields=[("part1", soap_header)]
        + [
            (f"part{idx+2}", ("filename", bytes_part, "application/dicom"))
            for idx, bytes_part in enumerate(bytes_parts)
        ],
    )

    return MockResponse(
        url=MockUrls.RAD69_URL,
        content=multi_part_soap_response.read(),
        method="POST",
        headers={"Content-Type": multi_part_soap_response.content_type},
    )


RAD69_RESPONSE_INVALID_DICOM = create_rad69_response(bytes_parts=[bytes(1234)])

RAD69_RESPONSE_INVALID_NON_DICOM = MockResponse(
    url=MockUrls.RAD69_URL,
    method="POST",
    status_code=502,
    text="Bad server error rad69",
)

RAD69_RESPONSE_INVALID_NON_MULTIPART = MockResponse(
    url=MockUrls.RAD69_URL,
    method="POST",
    status_code=200,
    text="This is a non-error response, but its not multipart.. very unexpected",
)

# Response when trying to request a non-existant slice
RAD69_RESPONSE_OBJECT_NOT_FOUND = MockResponse(
    url=MockUrls.RAD69_URL,
    method="POST",
    status_code=200,
    headers={
        "Accept": "application/soap+xml, text/html, image/gif,"
        " image/jpeg, *; q=.2, */*; q=.2",
        "Content-Type": "application/soap+xml; charset=utf-8",
    },
    text=RAD69_SOAP_RESPONSE_NOT_FOUND,
)

# like object not found, but different error code
RAD69_RESPONSE_UNKNOWN = MockResponse(
    url=MockUrls.RAD69_URL,
    method="POST",
    status_code=200,
    headers={
        "Accept": "application/soap+xml, text/html, image/gif,"
        " image/jpeg, *; q=.2, */*; q=.2",
        "Content-Type": "application/soap+xml; charset=utf-8",
    },
    text=RAD69_SOAP_RESPONSE_NOT_FOUND.replace(
        "XDSMissingDocument", "UnknownError"
    ),
)

# Simple valid dataset for call to rad69 url
RAD69_RESPONSE_ANY = quick_rad69_response(PatientName="Test")
RAD69_RESPONSE_ANY.url = MockUrls.RAD69_URL

# Three studies at study level
QIDO_RS_STUDY_LEVEL = MockResponse(
    url=re.compile(MockUrls.QIDO_RS_URL + ".*"),
    method="GET",
    status_code=200,
    text=json.dumps(
        [
            {
                "00080020": {"vr": "DA", "Value": ["13495156"]},
                "00080030": {"vr": "TM", "Value": ["298451.540"]},
                "00080050": {"vr": "SH", "Value": ["6928536.88731372"]},
                "00080056": {"vr": "CS", "Value": ["DCEWMJ"]},
                "00080061": {"vr": "CS", "Value": ["JR"]},
                "00080090": {
                    "vr": "PN",
                    "Value": [{"Alphabetic": "087195^TZIPB^B.F.^TZ"}],
                },
                "00081190": {
                    "vr": "UR",
                    "Value": [
                        "https://testserver/qido/dicomweb/studies/1.2.392.200036.9116.2.6.1.3229.2462354167.1685325303.929533"
                    ],
                },
                "00100010": {
                    "vr": "PN",
                    "Value": [{"Alphabetic": "EMWDJXDCJPFA^S"}],
                },
                "00100020": {"vr": "LO", "Value": ["3102219"]},
                "00100030": {"vr": "DA", "Value": ["43835405"]},
                "00100040": {"vr": "CS", "Value": ["Z"]},
                "0020000D": {
                    "vr": "UI",
                    "Value": [
                        "7.7.832.734150.2814.5.0.4.6559.8696629511.6805009058.073242"
                    ],
                },
                "00200010": {"vr": "SH", "Value": ["5722324.12608235"]},
                "00201206": {"vr": "IS", "Value": [11]},
                "00201208": {"vr": "IS", "Value": [7972]},
            },
            {
                "00080020": {"vr": "DA", "Value": ["01500700"]},
                "00080030": {"vr": "TM", "Value": ["092705.911"]},
                "00080050": {"vr": "SH", "Value": ["3667278.11004347"]},
                "00080056": {"vr": "CS", "Value": ["PQFURO"]},
                "00080061": {"vr": "CS", "Value": ["BE"]},
                "00080090": {
                    "vr": "PN",
                    "Value": [{"Alphabetic": "043693^DZIGOGPM^A.D.F."}],
                },
                "00081190": {
                    "vr": "UR",
                    "Value": [
                        "https://testserver/qido/dicomweb/studies/1.2.392.200036.9116.6.20.18523571.1467.20230529175134676.3.2"
                    ],
                },
                "00100010": {
                    "vr": "PN",
                    "Value": [{"Alphabetic": "HYBAGZLA^R"}],
                },
                "00100020": {"vr": "LO", "Value": ["1411762"]},
                "00100030": {"vr": "DA", "Value": ["49186581"]},
                "00100040": {"vr": "CS", "Value": ["H"]},
                "0020000D": {
                    "vr": "UI",
                    "Value": [
                        "2.5.241.458109.5292.3.03.66517245.6439.64814793504015160.1.0"
                    ],
                },
                "00200010": {"vr": "SH", "Value": ["47393807A1232"]},
                "00201206": {"vr": "IS", "Value": [7]},
                "00201208": {"vr": "IS", "Value": [98]},
            },
            {
                "00080020": {"vr": "DA", "Value": ["07613949"]},
                "00080030": {"vr": "TM", "Value": ["733440"]},
                "00080050": {"vr": "SH", "Value": ["EDB51975356.0644"]},
                "00080056": {"vr": "CS", "Value": ["FESRTJ"]},
                "00080061": {"vr": "CS", "Value": ["MP"]},
                "00080090": {
                    "vr": "PN",
                    "Value": [{"Alphabetic": "385960^GYUNZH^Y.S.I.I."}],
                },
                "00081190": {
                    "vr": "UR",
                    "Value": [
                        "https://testserver/qido/dicomweb/studies/1.2.40.0.13.1.20824033173342836000295543233473981868"
                    ],
                },
                "00100010": {
                    "vr": "PN",
                    "Value": [{"Alphabetic": "WZSHWZDRM^S^BSI"}],
                },
                "00100020": {"vr": "LO", "Value": ["8379268"]},
                "00100030": {"vr": "DA", "Value": ["69725200"]},
                "00100040": {"vr": "CS", "Value": ["V"]},
                "0020000D": {
                    "vr": "UI",
                    "Value": [
                        "2.4.05.6.17.1.11063029529943328216399526680942319832"
                    ],
                },
                "00200010": {"vr": "SH", "Value": ["TFE44654152.7002"]},
                "00201206": {"vr": "IS", "Value": [71]},
                "00201208": {"vr": "IS", "Value": [69]},
            },
        ]
    ),
)

# respond with a valid mint search response containing three studies, whatever the
# called url was. Blunt.
MINT_SEARCH_ANY = MockResponse(
    url=ANY,
    method=ANY,
    text="<?xml version='1.0' encoding='UTF-3'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" queryfields="PatientName=B*" '
    'includefields="StudyInstanceUID,PatientName,PatientID"><study '
    'studyUUID="35997945-c535-4570-3c1f-3514f27695e9" version="1" '
    'lastModified="2021-08-09T06:42:04.325Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="TEST^K.J.M." /><attr '
    'tag="0020000d" vr="UI" val="1.2.340.114850.2.857.2.793263.2.125336546.1" />'
    '</study><study studyUUID="c19a038a-fe0f-4e4b-b690-a895bd8db1e2" version="1"'
    ' lastModified="2021-08-09T06:42:26.722Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="TEST^K.J.M." />'
    '<attr tag="0020000d" vr="UI" '
    'val="1.2.340.114850.2.857.8.793263.2.126347154.1" /></study><study '
    'studyUUID="26582e0f-473e-422d-9c24-12ebdbc6dac3" version="1" '
    'lastModified="2021-08-09T06:42:10.598Z"><attr tag="00100020" vr="LO" '
    'val="1892052" /><attr tag="00100010" vr="PN" val="BEELDEN^W^I L" /><attr '
    'tag="0020000d" vr="UI" val="1.2.340.114850.2.857.8.793263.2.126347158.1" />'
    "</study></studySearchResults>",
)


def mint_response(request, context):
    """Generate a MINT query response that matches the requested StudyInstanceUID
    and also honours query_level.
    """
    query_level = request.qs["querylevel"][0].upper()
    requested_suid = request.qs["studyinstanceuid"][0]

    if query_level == QueryLevels.STUDY:
        base_response = MINT_SEARCH_STUDY_LEVEL_SINGLE.text
    elif query_level == QueryLevels.SERIES:
        base_response = MINT_SEARCH_SERIES_LEVEL_SINGLE.text
    elif query_level == QueryLevels.INSTANCE:
        base_response = MINT_SEARCH_INSTANCE_LEVEL.text
    else:
        raise ValueError(f"Unknown query level {query_level}")

    return base_response.replace(MINT_SEARCH_MOCK_STUDY_UID, requested_suid)


# Respond to MockUrls.QIDO_RS_URL queries with a mint response matching the
# requested StudyInstanceUID.
MINT_SEARCH_MATCH_SUID = MockResponse(
    url=re.compile(MockUrls.MINT_URL + ".*"), method=ANY, text=mint_response
)

# a valid response when a query has 0 results
QIDO_RS_204_NO_RESULTS = MockResponse(
    url=re.compile(MockUrls.QIDO_RS_URL + ".*"),
    method="GET",
    status_code=204,
    content=b"",
)
