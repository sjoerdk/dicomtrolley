"""Finding studies

This example read the following variables from system environment:
USER       # user to log in with
PASSWORD   # user password
REALM      # Needed for Vitrea login
LOGIN_URL  # full url to login page, including https:// and port
MINT_URL   # full url to mint endpoint, without trailing slash
WADO_URL   # full url to mint endpoint, without trailing slash

Please set these before running this example

"""
from datetime import datetime
from os import environ

from dicomtrolley.core import Trolley
from dicomtrolley.https import log_in_to
from dicomtrolley.mint import Mint
from dicomtrolley.query import Query
from dicomtrolley.wado import Wado

# log in
session = log_in_to(environ["LOGIN_URL"])
trolley = Trolley(
    mint=Mint(session, environ["MINT_URL"]),
    wado=Wado(session, environ["WADO_URL"]),
)

print("Quick search for some studies")
studies = trolley.find_studies(
    Query(patientName="B*", includeFields=["PatientBirthDate"])
)
print(f"Found {len(studies)} studies:\n" + "\n".join([x.uid for x in studies]))


print(
    "Query parameters are in dicomtrolley.mint.Query. Any field in "
    "dicomtrolley.include_fields can be returned"
)
studies = trolley.find_studies(
    Query(
        patientName="B*",
        modalitiesInStudy="CT*",
        patientSex="M",
        minStudyDate=datetime(year=2015, month=3, day=1),
        maxStudyDate=datetime(year=2020, month=3, day=1),
        includeFields=["PatientBirthDate", "SOPClassesInStudy"],
    )
)
# All data returned by mint is in the study.data field
print(f"Birthdates: {[x.data.PatientBirthDate for x in studies]}")
