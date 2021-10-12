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

print("Setting up DICOM query-retrieve")
dicom_qr = DICOMQR(
    host=environ["HOST"],
    port=int(environ["PORT"]),
    aet=environ["AET"],
    aec=environ["AEC"],
)


print("Perform a search")
studies = dicom_qr.find_studies(
    DICOMQuery(
        PatientName="BAL*",
        ProtocolName="Thorax",
        minStudyDate=datetime(year=2015, month=3, day=1),
        maxStudyDate=datetime(year=2015, month=4, day=1),
        includeFields=[
            "PatientBirthDate",
            "SOPClassesInStudy",
            "Modality",
            "StudyDescription",
            "SeriesDescription",
            "ProtocolName",
        ],
        QueryRetrieveLevel=QueryRetrieveLevels.SERIES,
    )
)

print(f"Found {len(studies)} studies")
