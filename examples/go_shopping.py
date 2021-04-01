"""Full example dicomtrolley usage

This example read the following variables from system environment:
USER       # user to log in with
PASSWORD   # user password
REALM      # Needed for Vitrea login
LOGIN_URL  # full url to login page, including https:// and port
MINT_URL   # full url to mint endpoint, without trailing slash
WADO_URL   # full url to mint endpoint, without trailing slash

Please set these before running this example
"""
from os import environ

from dicomtrolley.core import DICOMStorageDir, Trolley
from dicomtrolley.https import log_in_to
from dicomtrolley.mint import Mint
from dicomtrolley.query import Query, QueryLevels
from dicomtrolley.wado import Wado

print("logging in")
session = log_in_to(environ["LOGIN_URL"])
trolley = Trolley(
    mint=Mint(session, environ["MINT_URL"]),
    wado=Wado(session, environ["WADO_URL"]),
)

print("Quick search for studies")
studies = trolley.find_studies(
    Query(patientName="B*", includeFields=["NumberOfStudyRelatedInstances"])
)

print(f"Found {len(studies)} studies. Taking one with least instances")
studies.sort(key=lambda x: x.data.NumberOfStudyRelatedInstances)
study = studies[0]

print(f"Getting slice info for {study}")
details = trolley.find_studies(
    Query(studyInstanceUID=study.uid, queryLevel=QueryLevels.INSTANCE)
)
instances = trolley.extract_instances(details)
print(f"Got {len(instances)} instances for {study}")

storage = DICOMStorageDir("/tmp/trolley")
print(f"Saving datasets to {storage}")
for instance in instances:
    print(f"downloading {instance}")
    storage.save(trolley.get_dataset(instance))

print("Done")
