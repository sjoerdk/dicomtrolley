"""Full example dicomtrolley usage

This example read the following variables from system environment:
USER           # user to log in with
PASSWORD       # user password
REALM          # Needed for Vitrea login
LOGIN_URL      # full url to login page, including https:// and port
MINT_URL       # full url to mint endpoint, without trailing slash
WADO_URL       # full url to WADO-URI endpoint, without trailing slash
DOWNLOAD_PATH  # Path to download to

Please set these before running this example
"""
from os import environ

from dicomtrolley.auth import create_session
from dicomtrolley.core import Query
from dicomtrolley.mint import Mint, QueryLevels
from dicomtrolley.trolley import Trolley
from dicomtrolley.wado_uri import WadoURI


def go_shopping():
    print("Creating session")
    session = create_session(
        environ["LOGIN_URL"],
        environ["USER"],
        environ["PASSWORD"],
        environ["REALM"],
    )

    trolley = Trolley(
        searcher=Mint(session, environ["MINT_URL"]),
        downloader=WadoURI(session, environ["WADO_URL"]),
    )

    print("Quick search for studies")
    studies = trolley.find_studies(
        Query(
            PatientName="B*", include_fields=["NumberOfStudyRelatedInstances"]
        )
    )

    print(f"Found {len(studies)} studies. Taking one with least instances")
    studies.sort(key=lambda x: int(x.data.NumberOfStudyRelatedInstances))
    study = studies[0]

    print(f"Getting slice info for {study}")
    studies_full = trolley.find_studies(
        Query(StudyInstanceUID=study.uid, query_level=QueryLevels.INSTANCE)
    )  # query_level=INSTANCE will return all instances inside each study

    print(f"Saving datasets to {environ['DOWNLOAD_PATH']}")
    trolley.download(studies_full, environ["DOWNLOAD_PATH"], use_async=False)
    print("Done")


if __name__ == "__main__":
    go_shopping()
