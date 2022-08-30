"""Full example dicomtrolley usage

This example read the following variables from system environment:
USER           # user to log in with
PASSWORD       # user password
REALM          # Needed for Vitrea login
LOGIN_URL      # full url to login page, including https:// and port
MINT_URL       # full url to mint endpoint, without trailing slash
RAD69_URL      # full url to rad69 endpoint, without trailing slash
DOWNLOAD_PATH  # Path to download to

Please set these before running this example
"""
from os import environ

from dicomtrolley.auth import create_session
from dicomtrolley.mint import Mint, MintQuery
from dicomtrolley.rad69 import Rad69
from dicomtrolley.trolley import Trolley

print("Creating session")
session = create_session(
    environ["LOGIN_URL"],
    environ["USER"],
    environ["PASSWORD"],
    environ["REALM"],
)

trolley = Trolley(
    searcher=Mint(session, environ["MINT_URL"]),
    downloader=Rad69(session, environ["RAD69_URL"]),
)

print("Quick search for studies")
studies = trolley.find_studies(
    MintQuery(
        StudyInstanceUID="1.2.840.114350.2.357.2.798268.2.165355273.1",
        include_fields=["NumberOfStudyRelatedInstances"],
    )
)

print(f"Found {len(studies)} studies. Taking one with least instances")
studies.sort(key=lambda x: int(x.data.NumberOfStudyRelatedInstances))
study = studies[0]
print(f"Downloading study with {study.data.NumberOfStudyRelatedInstances}")
print(f"Saving datasets to {environ['DOWNLOAD_PATH']}")
trolley.download(study, environ["DOWNLOAD_PATH"], use_async=False)
print("Done")
