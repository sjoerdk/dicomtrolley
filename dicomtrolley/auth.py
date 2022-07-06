"""Authentication mechanisms for DICOM servers"""

from requests.auth import AuthBase
from requests.models import Request

from dicomtrolley.exceptions import DICOMTrolleyError


class VitreaAuth(AuthBase):
    """Can log in to a server running Vitrea Connection 8.2.0.1

    Raises
    ------
    DICOMTrolleyAuthError
        If logging in fails

    Notes
    -----
    Vitrea login returns an auth token, but for some reason this is not checked
    at all and instead all validation is done based on session token.
    """

    def __init__(self, login_url, user, password, realm):
        self.login_url = login_url
        self.user = user
        self.password = password
        self.realm = realm

    def response_hook(self, r, **kwargs):
        """Called before returning response. Try to log if not authenticated"""
        if r.status_code == 401:
            """Not logged in, try to log in and retry request"""
            # first log in. This should automatically save the session ID
            login_response = self.do_login_call(r.connection)
            request = r.request.copy()
            request.prepare_cookies(
                login_response.cookies
            )  # transfer manually here
            retry_response = r.connection.send(request, **kwargs)

            # history makes cookies persist in session
            retry_response.history.append(login_response)
            return retry_response
        else:
            return r

    def do_login_call(self, connection):
        """Log in to vitrea connection url

        Raises
        ------
        DICOMTrolleyAuthError
            If logging in fails
        """
        req = Request(
            method="POST",
            url=self.login_url,
            headers={
                "X-Userid": self.user,
                "X-Password": self.password,
                "X-Realm": self.realm,
            },
        )
        response = connection.send(req.prepare())
        if response.status_code != 200:
            raise DICOMTrolleyAuthError(
                f"login failed. {response.status_code}: {response.reason}"
            )
        return response

    def __call__(self, r):
        """Called before sending the request"""

        # Make sure keep alive because session is authenticated, not just the
        # connection
        r.headers["Connection"] = "Keep-Alive"
        r.register_hook("response", self.response_hook)
        return r


class DICOMTrolleyAuthError(DICOMTrolleyError):
    pass
