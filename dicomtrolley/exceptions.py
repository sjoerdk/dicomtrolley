class DICOMTrolleyError(Exception):
    """Base for all exceptions raised in dicomtrolley"""

    pass


class UnSupportedParameterError(DICOMTrolleyError):
    """A query parameter was set that cannot be used in this Searcher type.
    See Query class notes
    """

    pass
