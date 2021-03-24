"""Mock responses

Based on live responses from a server running Vitrea Connection 8.2.0.1
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MockResponse:
    """A fake server response that can be fed to response-mock easily"""

    url: str
    status_code: int = 200
    method: str = "GET"
    text: str = ""
    json: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def as_dict(self):
        """Non-empty and non-None items as dictionary"""
        return {x: y for x, y in self.__dict__.items() if y}


def set_mock_response(requests_mock, response):
    """Register the given MockResponse with requests_mock"""
    requests_mock.register_uri(**response.as_dict())
    return response


class MockUrls:
    """For re-using across the code"""

    LOGIN = "https://testserver/login"
    MINT_URL = "https://testserver/mint"


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

MINT_SEARCH_STUDY_LEVEL = MockResponse(
    url=MockUrls.MINT_URL + "/studies?patientName=B*&queryLevel=STUDY",
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
    url=MockUrls.MINT_URL + "/studies?patientName=B*&queryLevel=SERIES",
    text="<?xml version='1.0' encoding='UTF-8'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" queryLevel="SERIES" '
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
    url=MockUrls.MINT_URL + "/studies?patientName=B*&queryLevel=INSTANCE",
    text="<?xml version='1.0' encoding='UTF-8'?><studySearchResults "
    'xmlns="http://medical.nema.org/mint" queryLevel="INSTANCE" '
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
