"""
This module contains custom exceptions for file handling operations.
"""


class FileHandlingError(Exception):
    """
        Base class for file handle exceptions in this module.
    """

    pass


class FileRemoveError(FileHandlingError):
    """
        Exception raised for errors in the file removal operation.
    """
    pass


class FileMoveError(FileHandlingError):
    """
        Exception raised for errors in the file move operation.
    """

    pass


class ParameterError(Exception):
    """
        Base class for parameter related exceptions.
    """

    pass


class UnsupportedModeError(ParameterError):
    """
        Exception raised for unsupported mode.
    """

    pass


class InvalidArgType(ParameterError):
    """
        Exception raised for invalid argument type.
    """

    pass
