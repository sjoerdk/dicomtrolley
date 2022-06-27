"""Finding studies with MINT

This example read the following variables from system environment:
USER       # user to log in with
PASSWORD   # user password
REALM      # Needed for Vitrea login
LOGIN_URL  # full url to login page, including https:// and port
MINT_URL   # full url to mint endpoint, without trailing slash

Please set these before running this example

"""
from datetime import datetime
from os import environ

from dicomtrolley.mint import Mint, MintQuery, QueryLevels
from dicomtrolley.servers import VitreaConnection

# Log in to get an authenticated session
session = VitreaConnection(environ["LOGIN_URL"]).log_in(
    environ["USER"], environ["PASSWORD"], environ["REALM"]
)

# Using mint for search
mint = Mint(session, environ["MINT_URL"])


print("Quick search for some studies")
studies = mint.find_studies(
    MintQuery(PatientName="B*", include_fields=["PatientBirthDate"])
)
print(f"Found {len(studies)} studies")

print("More extensive search")
studies = mint.find_studies(
    MintQuery(
        PatientName="B*",  # wildcards can be used
        ModalitiesInStudy="CT*",  # more parameters can be found
        PatientSex="M",  # in dicomtrolley.mint.MintQuery
        min_study_date=datetime(year=2015, month=3, day=1),
        max_study_date=datetime(year=2020, month=3, day=1),
        include_fields=[
            "PatientBirthDate",  # which fields to get back.
            "SOPClassesInStudy",
        ],  # see dicomtrolley.fields for options
        query_level=QueryLevels.INSTANCE,  # get instance info. Slow but thorough
    )
)
# include_fields requested 'PatientBirthDate'. This should now be in Study.data
print(f"Birthdates: {[x.data.PatientBirthDate for x in studies]}")

# You can traverse study/series/instances like a tree
print(f"Found {len(studies)} studies")
print(f"The first study contains {len(studies[0].series)} series")
print("The first thee instances in the first series are:")
for instance in studies[0].series[0].instances[:3]:
    print(instance)

# And anything in the tree can be downloaded by a Trolley instance
# Trolley().download(studies)
# Trolley().download(studies[0].series[1:3])
# Trolley().download([studies[0], studies[1].series[3])
