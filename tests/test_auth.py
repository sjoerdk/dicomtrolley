import uuid
from typing import List, Optional

import pytest
import requests
from pydantic.main import BaseModel
from requests import Request

from dicomtrolley.auth import DICOMTrolleyAuthError, VitreaAuth
from tests.mock_responses import MINT_401, MINT_SEARCH_STUDY_LEVEL


def test_vitrea_auth_session_timeout(mock_vitrea_server):
    """If session times out, login should be re-attempted"""
    server = mock_vitrea_server

    assert requests.Session().get(server.mint_url).status_code == 401

    session = requests.Session()
    session.auth = VitreaAuth(
        login_url=server.login_url,
        user=VITREA_CREDENTIALS.user_id,
        password=VITREA_CREDENTIALS.password,
        realm=VITREA_CREDENTIALS.realm,
    )

    assert session.get(server.mint_url).status_code == 200
    assert len(server._calls_to_login) == 1
    # session times out. No 200 responses anymore from server

    server.reset_all()
    assert len(server._calls_to_login) == 0

    # this should trigger an internal re-login
    assert session.get(server.mint_url).status_code == 200
    assert len(server._calls_to_login) == 1


def test_vitrea_auth_wrong_credentials(mock_vitrea_server):
    """If credentials do not work, make this known with exception"""
    server = mock_vitrea_server
    session = requests.Session()
    session.auth = VitreaAuth(
        login_url=server.login_url,
        user=VITREA_CREDENTIALS.user_id,
        password="WRONG_PASSWORD",
        realm=VITREA_CREDENTIALS.realm,
    )
    with pytest.raises(DICOMTrolleyAuthError):
        session.get(server.mint_url)


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
        url="http://mockserver",
    ):
        self.url = url
        self.login_url = f"{url}/login"
        self.mint_url = f"{url}/mint"

        self.allowed_credentials = allowed_credentials
        self._authorized_tokens: List[str] = []
        self._authorized_sessions: List[str] = []
        self._calls_to_login: List[Request] = []
        self.allow_all = False

    def reset_all(self):
        """Remove all credentials and call logs, re-login is required"""
        self._authorized_sessions = []
        self._authorized_tokens = []
        self._calls_to_login = []
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
            self._calls_to_login.append(request)
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


VITREA_CREDENTIALS = VitreaCredentials(
    user_id="user", password="pass", realm="some_realm"
)


@pytest.fixture
def mock_vitrea_server(requests_mock):
    """Simulates vitrea Connection login and responses

    Valid login with VITREA_CREDENTIALS
    """
    server = VitreaServer(allowed_credentials=VITREA_CREDENTIALS)
    server.register_all_responses(requests_mock)
    return server
