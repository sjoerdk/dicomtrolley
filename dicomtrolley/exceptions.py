class DICOMTrolleyError(Exception):
    """Base for all exceptions raised in dicomtrolley"""

    pass


class UnSupportedParameterError(DICOMTrolleyError):
    """A query parameter was set that cannot be used in this Searcher type.
    See Query class notes
    """

    pass


class NoReferencesFoundError(DICOMTrolleyError):
    """Cannot find any references for this object at the given level. Used in
    DICOMDownloadable
    """

    pass


class NoQueryResultsError(DICOMTrolleyError):
    """Raised when a query returns 0 results"""
