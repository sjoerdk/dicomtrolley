"""Models https layer interaction, login, session handling"""

import requests

from dicomtrolley.exceptions import DICOMTrolleyException


class VitreaConnectionLogin:
    """Login for Vitrea Connection 8.2.0.1"""

    def __init__(self, url):
        """

        Parameters
        ----------
        url: str
            Full url of login method, including https://
        """
        self.url = url

    def get_session(self, user, password, realm):
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
            self.url,
            headers={"X-Userid": user, "X-Password": password, "X-Realm": realm},
        )
        if response.status_code == 401:
            raise DICOMTrolleyException(
                f"login failed. {response.status_code}:{response.reason}"
            )

        return session
