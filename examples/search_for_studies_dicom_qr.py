"""Finding studies with DICOM-QR

This example read the following variables from system environment:
HOST  # Server to use for DICOM-QR
PORT  # Port to use on host
AET   # Application Entity Title - What to call yourself
AEC   # Application Entity Called - The name of the server you are calling

Please set these before running this example

"""
from datetime import datetime
from os import environ

from dicomtrolley.dicom_qr import DICOMQR, DICOMQuery, QueryRetrieveLevels
from dicomtrolley.mint import Mint
from dicomtrolley.servers import IMPAXDataCenter
from dicomtrolley.trolley import Trolley
from dicomtrolley.wado import Wado

dicom_qr = DICOMQR(
    host=environ["HOST"],
    port=int(environ["PORT"]),
    aet=environ["AET"],
    aec=environ["AEC"],
)

session = IMPAXDataCenter(environ["LOGIN_URL"]).log_in(
    environ["USER"], environ["PASSWORD"]
)

trolley = Trolley(
    searcher=Mint(session, environ["MINT_URL"]),
    wado=Wado(session, environ["WADO_URL"]),
)


print("More extensive search")
studies = dicom_qr.find_studies(
    DICOMQuery(
        PatientName="BAL*",
        minStudyDate=datetime(year=2015, month=3, day=1),
        maxStudyDate=datetime(year=2015, month=4, day=1),
        includeFields=["PatientBirthDate", "SOPClassesInStudy"],
        QueryRetrieveLevel=QueryRetrieveLevels.STUDY,
    )
)

print(f"Found {len(studies)} studies")
