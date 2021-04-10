"""Models VNA server specifics. Mainly log-in procedures"""

import requests

from dicomtrolley.dicom_qr import DICOMQR
from dicomtrolley.exceptions import DICOMTrolleyException
from dicomtrolley.mint import Mint
from dicomtrolley.trolley import Trolley
from dicomtrolley.wado import Wado


class VitreaConnection:
    """A server running Vitrea Connection 8.2.0.1"""

    def __init__(self, login_url):
        """

        Parameters
        ----------
        login_url: str
            Full url of login method, including https://
        """
        self.login_url = login_url

    def log_in(self, user, password, realm):
        """
        Parameters
        ----------
        user: str
            username
        password: str
            password to log in with
        realm: str
           realm to log in to

        Returns
        -------
        requests.Session
            A logged in session on the VNA

        Raises
        ------
        DICOMTrolleyException
            If login fails for some reason

        """
        session = requests.Session()
        response = session.post(
            self.login_url,
            headers={
                "X-Userid": user,
                "X-Password": password,
                "X-Realm": realm,
            },
        )
        if response.status_code == 401:
            raise DICOMTrolleyException(
                f"login failed. {response.status_code}:{response.reason}"
            )

        return session

    def get_mint_trolley(
        self, user, password, realm, wado_url, mint_url
    ) -> Trolley:
        """Create a logged in trolley with wado and mint

        Parameters
        ----------
        user: str
            User to log in with
        password:
            Password for user
        realm: str
            realm to log in to
        wado_url: str
            WADO endpoint, including http(s)://  and port
        mint_url
            MINT endpoint, including http(s)://  and port

        Returns
        -------
        Trolley
            logged in trolley with wado and mint

        """
        session = VitreaConnection(login_url=self.login_url).log_in(
            user=user, password=password, realm=realm
        )
        return Trolley(
            wado=Wado(session=session, url=wado_url),
            searcher=Mint(session=session, url=mint_url),
        )


class IMPAXDataCenter:
    """WADO Login for AGFA IMPAX Data Center 3.1.1"""

    def __init__(self, wado_url):
        """

        Parameters
        ----------
        wado_url: str
            Full url of WADO endpoint login method, including https:// and port
        """
        self.wado_url = wado_url

    def log_in(self, user, password):
        """Get a logged in session for WADO on this server

        Parameters
        ----------
        user: str
            username
        password: str
            password to log in with

        Returns
        -------
        requests.Session
            A logged in session on IMPAX

        Raises
        ------
        DICOMTrolleyException
            If login fails for some reason

        """
        session = requests.Session()

        # AGFA IMPAX WADO login is stateful and strange.
        # A better method might be available. However, this one works.
        try:
            session.get(
                self.wado_url
            )  # this is required to make the next GET work..
            response = session.get(
                f"{self.wado_url}/j_security_check"
                f"?j_username={user}&j_password={password}"
            )
        except requests.exceptions.ConnectionError as e:
            raise DICOMTrolleyException(
                f"Error logging in to {self.wado_url}: {e}"
            )

        if (
            "Login Failed!" in response.text
        ):  # login fail status_code is 200 OK..
            raise DICOMTrolleyException(
                f"Logging in to {self.wado_url} failed. "
                f"Invalid Credentials?"
            )
        else:
            return (
                session  # login worked. status_code is now 403 (forbidden)..
            )

    def get_dicom_qr_trolley(
        self,
        wado_user,
        wado_pass,
        host,
        port,
        aet="DICOMTROLLEY",
        aec="ANY-SCP",
    ) -> Trolley:
        """Log in to WADO and create a Trolley with wado and DICOM-QR

        Notes
        -----
        DICOM-QR credentials will only be verified during the first trolley find
        command.

        Parameters
        ----------
        wado_user: str
            User to log in to wado
        wado_pass: str
            Password for wado
        host: str
            Hostname for DICOM-QR
        port: int
            port for DICOM-QR
        aet: str, optional
            Application Entity Title - Name of the calling entity (this class).
            Defaults to 'DICOMTROLLEY'
        aec: str, optional
            Application Entity Called - The name of the server you are calling.
            Defaults to 'ANY-SCP'
        Returns
        -------

        """
        session = IMPAXDataCenter(self.wado_url).log_in(wado_user, wado_pass)
        return Trolley(
            wado=Wado(session, self.wado_url),
            searcher=DICOMQR(host=host, port=port, aet=aet, aec=aec),
        )
