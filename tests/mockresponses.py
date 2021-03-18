"""Mock responses

Based on live responses from a server running Vitrea Connection 8.2.0.1
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MockResponse:
    """A fake server response that can be fed to response-mock easily"""

    url: str
    status_code: int
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
