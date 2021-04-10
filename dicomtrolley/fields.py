"""Fields that can be returned for Study, Series and Instance levels

Notes
-----
Valid fields per level have all been taken from the Vitrea Connection 8.2.0.1
manual. These list might be different for different software.
"""


class InstanceLevel:
    """attributes can be returned if queryLevel=INSTANCE"""

    fields = {
        "SOPInstanceUID",
        "SOPClassUID",
        "Rows",
        "Columns",
        "NumberOfFrames",
        "BitsAllocated",
        "ContentDate",
        "ContentTime",
        "ObservationDateTime",
        "ConceptNameCodeSequence",
        "ContentLabel",
        "ContentDescription",
        "PresentationCreationDate",
        "PresentationCreationTime",
        "ContentCreatorName",
        "RetrieveURI",
        "TransferSyntaxUID",
        "InstanceNumber",
        "Manufacturer",
        "StationName",
        "ManufacturerModelName",
        "DeviceSerialNumber",
        "InstitutionAddress",
        "CorrectedImage",
        "SoftwareVersions",
        "DateOfLastCalibration",
        "TimeOfLastCalibration",
        "PixelPaddingValue",
    }


class SeriesLevel:
    """attributes can be returned if queryLevel=SERIES, or queryLevel=INSTANCE"""

    fields = {
        "SeriesInstanceUID",
        "Modality",
        "SeriesDate",
        "SeriesTime",
        "SeriesDescription",
        "Laterality",
        "AnatomicRegionSequence",
        "BodyPartExamined",
        "FrameOfReferenceUID",
        "PerformedProcedureStepDescription",
        "ProtocolName",
        "PerformingPhysicianName",
        "PerformedProcedureStepStartDate",
        "PerformedProcedureStepStartTime",
        "OperatorsName",
        "PerformedProcedureStepStatus",
        "PresentationIntentType",
        "SeriesNumber",
        "SeriesType",
        "SmallestPixelValueInSeries",
        "SpatialResolution",
        "NumberOfSeriesRelatedInstances",
    }


class SeriesLevelPromotable:
    """Instance level attributes that may be returned even if queryLevel=SERIES

    These attributes are promotable from the Image-level to the Series-level metadata
    if the attribute value for all SOP instances in that series contain the same
    value. Therefore these attributes may be returned in a queryLevel=SERIES query,
    but only when this condition is satisfied.

    Notes
    -----
    Including any of these attributes as return keys in a Series-level query will
    cause the full study metadata to be loaded from disk, even if the corresponding
    attribute was promoted to the study summary MINT metadata. This means there is an
    extra read from disk in addition to the database, so the performance of such
    queries may be slightly slower than queries for other Series-level attributes.
    """

    fields = {
        "Manufacturer",
        "ManufacturerModelName",
        "CorrectedImage",
        "DeviceSerialNumber",
        "InstitutionAddress",
        "SoftwareVersions",
        "StationName",
        "DateOfLastCalibration",
        "TimeOfLastCalibration",
    }


class StudyLevel:
    """All fields that can be returned for queryLevel=STUDY, SERIES or INSTANCE.

    Notes
    -----
    From manual:
    Note that if a specified attribute is not in the study, the attribute will not
    be returned. If the specified attribute is in the study but does not have a
    value, it will be returned without a value.
    """

    fields = {
        "PatientID",
        "IssuerOfPatientID",
        "IssuerOfPatientIDQualifiersSequence",
        "PatientName",
        "PatientSex",
        "PatientBirthDate",
        "PatientBirthTime",
        "StudyInstanceUID",
        "AccessionNumber",
        "IssuerOfAccessionNumberSequence",
        "StudyID",
        "StudyDate",
        "StudyTime",
        "ModalitiesInStudy",
        "ReferringPhysicianName",
        "RequestedProcedureID",
        "StudyDescription",
        "InstanceAvailability",
        "InstitutionName",
        "StudyStatusID",
        "ConfidentialityCode",
        "ProcedureCodeSequence",
        "ReasonForPerformedProcedureCodeSequence",
        "OtherPatientIDsSequence",
        "InstitutionalDepartmentName",
        "NumberOfStudyRelatedSeries",
        "NumberOfStudyRelatedInstances",
        "InstanceAvailability",
        "SOPClassesInStudy",
        "CurrentPatientLocation",
        "SourceApplicationEntityTitle",
    }
