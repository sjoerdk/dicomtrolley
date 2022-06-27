"""Mock responses

Based on live responses from a server running Vitrea Connection 8.2.0.1
"""
import re
import urllib
from dataclasses import dataclass, field
from typing import Any, Dict, Pattern, Union

from requests_mock.adapter import ANY
from requests_toolbelt.multipart.encoder import MultipartEncoder

from dicomtrolley.core import InstanceReference
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
    text: str = ""
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


class MockUrls:
    """For re-using across the code"""

    LOGIN = "https://testserver/login"
    MINT_URL = "https://testserver/mint"
    WADO_URL = "https://testserver/wado"
    RAD69_URL = "https://testserver/rids"


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
            study_instance_uid=cls.study_instance_uid,
            series_instance_uid=cls.series_instance_uid,
            sop_instance_uid=cls.sop_instance_uid,
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

MINT_SEARCH_STUDY_LEVEL = MockResponse(
    url=MockUrls.MINT_URL + "/studies?PatientName=B*&QueryLevel=STUDY",
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
    'val="1.2.840.114350.2.357.3.798268.2.126847153.1" /></study><study'
    ' studyUUID="85997945-c585-4570-8c1f-8514f27695e9" version="1" '
    'lastModified="2021-03-09T06:42:04.825Z"><series><attr tag="0020000e"'
    ' vr="UI" val="1.2.40.0.13.1.202066129828111990737107018349786560571"'
    ' /></series><series><attr tag="0020000e" vr="UI" '
    'val="1.2.840.113663.1500.1.460388269.2.1.20201105.84519.348" />'
    '</series><attr tag="00100020" vr="LO" val="1392052" /><attr tag="00100010"'
    ' vr="PN" val="BEELDENZORG^W^I L" /><attr tag="0020000d" '
    'vr="UI" val="1.2.840.114350.2.357.2.798268.2.125886546.1" />'
    "</study></studySearchResults>",
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
    'vr="UI" val="1.2.840.114350.2.357.2.798268.2.125886546.1" /></study><'
    "/studySearchResults>",
)

# Will return mint study response to any mint server query
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

# a Response that contains a valid DICOM bytes
WADO_RESPONSE_DICOM = MockResponse(
    url=MockUrls.WADO_URL + MockWadoParameters.as_wado_query_string(),
    content=create_dicom_bytestream(
        quick_dataset(PatientName="Jane", StudyDescription="Test")
    ),
)

WADO_RESPONSE_INVALID_DICOM = MockResponse(
    url=MockUrls.WADO_URL + MockWadoParameters.as_wado_query_string(),
    content=bytes(1234),
)

WADO_RESPONSE_INVALID_NON_DICOM = MockResponse(
    url=MockUrls.WADO_URL + MockWadoParameters.as_wado_query_string(),
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
        "Date": "Thu, 14 Apr 2022 08:22:54 GMT",
        "Accept": "application/soap+xml, text/html, image/gif,"
        " image/jpeg, *; q=.2, */*; q=.2",
        "Content-Type": "application/soap+xml; charset=utf-8",
        "Content-Length": "1181",
        "Server": "Jetty(9.4.12.v20180830)",
    },
    text=RAD69_SOAP_RESPONSE_NOT_FOUND,
)
