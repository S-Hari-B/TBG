"""Custom exceptions for data loading and validation."""


class DataError(Exception):
    """Base exception for the data layer."""


class DataLoadError(DataError):
    """Raised when JSON files are missing or invalid."""


class DataValidationError(DataError):
    """Raised when JSON content fails structural validation."""


class DataReferenceError(DataError):
    """Raised when definitions reference missing related data."""


