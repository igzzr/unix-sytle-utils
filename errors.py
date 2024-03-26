class FileHandlingError(Exception):
    pass


class FileRemoveError(FileHandlingError):
    pass


class FileMoveError(FileHandlingError):
    pass


class ParameterError(Exception):
    pass


class UnsupportedModeError(ParameterError):
    pass


class InvalidArgType(ParameterError):
    pass
