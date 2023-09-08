"""Finding studies with DICOM-QR

This example read the following variables from system environment:
HOST  # Server to use for DICOM-QR
PORT  # Port to use on host
AET   # Application Entity Title - What to call yourself
AEC   # Application Entity Called - The name of the server you are calling

Please set these before running this example

"""
from os import environ

from dicomtrolley.core import QueryLevels
from dicomtrolley.dicom_qr import DICOMQR, DICOMQuery


def search_for_studies_dicom_qr():
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
            PatientName="*",
            query_level=QueryLevels.STUDY,
        )
    )

    print(f"Found {len(studies)} studies")


if __name__ == "__main__":
    search_for_studies_dicom_qr()
