import os

WINDOWS = "win"  # windows platform
UNIX = "posix"  # linux platform
PLATFORM = "win" if 'nt' in os.name else 'posix'
WINDOWS_MAX_PATH = 260

class ParameterError(Exception):
    pass
