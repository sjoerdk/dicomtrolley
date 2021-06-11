"""Full example dicomtrolley usage

This example read the following variables from system environment:
USER           # user to log in with
PASSWORD       # user password
REALM          # Needed for Vitrea login
LOGIN_URL      # full url to login page, including https:// and port
MINT_URL       # full url to mint endpoint, without trailing slash
WADO_URL       # full url to mint endpoint, without trailing slash
DOWNLOAD_PATH  # Path to download to

Please set these before running this example
"""
from os import environ

from dicomtrolley.mint import Mint, MintQuery, QueryLevels
from dicomtrolley.servers import VitreaConnection
from dicomtrolley.trolley import Trolley
from dicomtrolley.wado import Wado

print("logging in")

session = VitreaConnection(environ["LOGIN_URL"]).log_in(
    environ["USER"], environ["PASSWORD"], environ["REALM"]
)

trolley = Trolley(
    searcher=Mint(session, environ["MINT_URL"]),
    wado=Wado(session, environ["WADO_URL"]),
)

print("Quick search for studies")
studies = trolley.find_studies(
    MintQuery(
        patientName="B*", includeFields=["NumberOfStudyRelatedInstances"]
    )
)

print(f"Found {len(studies)} studies. Taking one with least instances")
studies.sort(key=lambda x: int(x.data.NumberOfStudyRelatedInstances))
study = studies[1]

print(f"Getting slice info for {study}")
studies_full = trolley.find_studies(
    MintQuery(studyInstanceUID=study.uid, queryLevel=QueryLevels.INSTANCE)
)  # queryLevel=INSTANCE will return all instances inside each study


print(f"Saving datasets to {environ['DOWNLOAD_PATH']}")
trolley.download(studies_full, environ["DOWNLOAD_PATH"], use_async=False)
print("Done")
