"""Using WADO download without any search, using UIDs directly

This example read the following variables from system environment:
USER           # user to log in with
PASSWORD       # user password
REALM          # Needed for Vitrea login
LOGIN_URL      # full url to login page, including https:// and port
WADO_URL       # full url to WADO-URI endpoint, without trailing slash
DOWNLOAD_PATH  # Path to download to

"""
from os import environ

from dicomtrolley.auth import create_session
from dicomtrolley.core import InstanceReference
from dicomtrolley.wado import Wado

# Create auto-login session
session = create_session(
    environ["LOGIN_URL"],
    environ["USER"],
    environ["PASSWORD"],
    environ["REALM"],
)

wado = Wado(session, environ["WADO_URL"])

# Study, Series and Instance UIDs are already known. dicomtrolley uses
# InstanceReference to represent a WADO-downloadable slice
instance1 = InstanceReference(
    series_instance_uid="1.2.840.113619.2.239.1783.1568025913.0.105",
    study_instance_uid="1.2.840.114350.2.357.3.798268.2.126847153.1",
    sop_instance_uid="1.2.840.113619.2.239.1783.1568025913.0.113",
)

instance2 = InstanceReference(
    series_instance_uid="1.2.840.113619.2.239.1783.1568025913.0.76",
    sop_instance_uid="1.2.840.113619.2.239.1783.1568025913.0.77.64",
    study_instance_uid="1.2.840.114350.2.357.3.798268.2.126847153.1",
)

# InstanceReference can be fed to wado download methods
instances = [instance1, instance2]
print(f'Downloading {len(instances)} instances to {environ["DOWNLOAD_PATH"]}')
for ds in wado.datasets(instances):
    ds.save_as(f'{environ["DOWNLOAD_PATH"]}/{ds.SOPInstanceUID}')

print("Done")
