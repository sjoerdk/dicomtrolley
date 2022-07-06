import uuid
from typing import List, Optional

import pytest
import requests
from pydantic.main import BaseModel

from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.servers import IMPAXDataCenter, VitreaConnection
from tests.conftest import set_mock_response
from tests.mock_responses import (
    LOGIN_DENIED_IMPAX,
    LOGIN_IMPAX_INITIAL,
    LOGIN_SUCCESS_IMPAX,
    MINT_401,
    MINT_SEARCH_STUDY_LEVEL,
    MockUrls,
)


@pytest.fixture
def a_login():
    return VitreaConnection(login_url=MockUrls.LOGIN)


def test_login(a_login, login_works):
    """Just check that nothing crashes"""
    session = a_login.log_in(user="test", password="test", realm="test")
    assert session


def test_login_fails(a_login, login_denied):
    """Check that correct exception is raised"""
    with pytest.raises(DICOMTrolleyError) as e:
        a_login.log_in(user="test", password="test", realm="test")
    assert "Unauthorized" in str(e)


@pytest.fixture
def an_impax(requests_mock):
    impax = IMPAXDataCenter(wado_url=MockUrls.LOGIN)
    set_mock_response(requests_mock, LOGIN_IMPAX_INITIAL)
    return impax


def test_impax_login_works(an_impax, requests_mock):
    set_mock_response(requests_mock, LOGIN_SUCCESS_IMPAX)
    assert an_impax.log_in("user", "pass")


def test_impax_login_fails(an_impax, requests_mock):
    set_mock_response(requests_mock, LOGIN_DENIED_IMPAX)
    with pytest.raises(DICOMTrolleyError):
        an_impax.log_in("user", "pass")


def test_impax_login_fails_connection_error(requests_mock):
    requests_mock.register_uri(
        url=MockUrls.LOGIN,
        method="GET",
        exc=requests.exceptions.ConnectionError,
    )
    with pytest.raises(DICOMTrolleyError):
        IMPAXDataCenter(wado_url=MockUrls.LOGIN).log_in("user", "pass")


@pytest.fixture
def mock_vitrea_server(requests_mock):
    """Simulates vitrea Connection login and responses

    Valid login with VITREA_CREDENTIALS
    """
    server = VitreaServer(allowed_credentials=VITREA_CREDENTIALS)
    server.register_all_responses(requests_mock)
    return server


def test_vitrea_login(mock_vitrea_server):
    """Test basic login into a vitrea server"""
    server = mock_vitrea_server

    # try to get some mint response. Won't work without login
    assert requests.Session().get(server.mint_url).status_code == 401

    # now log in and try again
    connection = VitreaConnection(login_url=server.login_url)
    session = connection.log_in(
        user=VITREA_CREDENTIALS.user_id,
        password=VITREA_CREDENTIALS.password,
        realm=VITREA_CREDENTIALS.realm,
    )
    assert session.get(server.mint_url).status_code == 200


def test_vitrea_login_session_timeout(mock_vitrea_server):
    """If session times out, login should be re-attempted"""
    server = mock_vitrea_server

    assert requests.Session().get(server.mint_url).status_code == 401
    connection = VitreaConnection(login_url=server.login_url)
    session = connection.log_in(
        user=VITREA_CREDENTIALS.user_id,
        password=VITREA_CREDENTIALS.password,
        realm=VITREA_CREDENTIALS.realm,
    )
    assert session.get(server.mint_url).status_code == 200
    # session times out. No 200 responses anymore from server
    server.allow_all = False

    # this should trigger an internal re-login
    assert session.get(server.mint_url).status_code == 200


class VitreaCredentials(BaseModel):
    """Credentials needed to log in to a Vitrea server"""

    user_id: str
    password: str
    realm: str


class VitreaServer:
    """A server that you can log in to the vitrea way, for testing login and session
    persistence

    requires requests_mock to mock url calls

    Notes
    -----
    Tried to get actual session-cookie based request auth working but could not.
    For some reason a Session with a valid cookie does not pass this cookie on
    to requests when calling session.get(). I can't figure out why.
    In addition, requests_mock does not pass on cookie to session. Known issue
    tracked here: https://github.com/jamielennox/requests-mock/pull/143

    Opted instead to go for a server-wide 'allow all' switch after succesful login.
    This will fulfil testing requirements for now.
    """

    def __init__(
        self,
        allowed_credentials: Optional[VitreaCredentials] = None,
        url="https://mockserver",
    ):
        self.url = url
        self.login_url = f"{url}/login"
        self.mint_url = f"{url}/mint"

        self.allowed_credentials = allowed_credentials
        self._authorized_tokens: List[str] = []
        self._authorized_sessions: List[str] = []
        self.allow_all = False

    def set_allowed_credentials(self, credentials: VitreaCredentials):
        self.allowed_credentials = credentials

    def register_login_response(self, requests_mock):
        """Register this server's login url with requests mock"""
        requests_mock.register_uri(
            "POST", url=self.login_url, text=self.create_login_callback()
        )

    def register_mint_response(self, requests_mock):
        requests_mock.register_uri(
            "GET", url=self.mint_url, text=self.create_mint_callback()
        )

    def register_all_responses(self, requests_mock):
        """Make sure requests calls to this servers's urls are routed through here"""
        self.register_login_response(requests_mock)
        self.register_mint_response(requests_mock)

    def add_token(self):
        token = str(uuid.uuid4())
        self._authorized_tokens.append(token)
        return token

    def add_session_token(self):
        session_token = str(uuid.uuid4())
        self._authorized_sessions.append(session_token)
        return session_token

    def create_login_callback(self):
        def callback(request, context):
            if self.can_login(request):
                self.allow_all = True
                context.status_code = 200
                context.json = {
                    "access_token": self.add_token(),
                    "token_type": "Bearer",
                }
                context.cookies = {"JSESSIONID": self.add_session_token()}
                return "success"
            else:
                context.status_code = 401
                context.reason = ("Unauthorized",)
                return "Login failed: bad username/password"

        return callback

    def can_login(self, request) -> bool:
        """Does this request provide the right data to log in?"""
        provided = VitreaCredentials(
            user_id=request.headers.get("X-Userid"),
            password=request.headers.get("X-Password"),
            realm=request.headers.get("X-Realm"),
        )
        return provided == self.allowed_credentials

    def create_mint_callback(self):
        def callback(request, context):
            if self.is_authenticated(request):
                context.status_code = MINT_SEARCH_STUDY_LEVEL.status_code
                return MINT_SEARCH_STUDY_LEVEL.text
            else:
                context.status_code = MINT_401.status_code
                context.reason = MINT_401.reason
                return MINT_401.text

        return callback

    def is_authenticated(self, request):
        """Is this request allowed to get stuff?

        Weirdly enough for the Vitrea Connection 8.2.0.1 there seems to be no
        checking of the access token at all. It's all based on the session cookie
        """
        if self.allow_all:
            return True
        if hasattr(request, "cookies"):  # this net gets used, see class notes
            return (
                request.cookies.get("JSESSIONID") in self._authorized_sessions
            )
        else:
            return False


# for testing login
VITREA_CREDENTIALS = VitreaCredentials(
    user_id="user", password="pass", realm="some_realm"
)
