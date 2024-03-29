"""
This module provides functions to handle file paths in a platform-independent manner.

Functions:
    touncpath: Converts a path to a UNC path if it exceeds the maximum path length in Windows.
    windows: Converts a path to a Windows-compatible path.
    unix: Converts a path to a Unix-compatible path.
    adaptive: Converts a path to a platform-compatible path based on the current operating system.
"""

import logging
import os
import re

from .defines import WINDOWS, PLATFORM, WINDOWS_MAX_PATH
from .errors import ParameterError


def touncpath(path, maximum=WINDOWS_MAX_PATH):
    """This function is used to handle the maximum path length issue in Windows.
    It takes a path as input and returns a modified path that can be used when the original path exceeds the maximum path length allowed by Windows.

    Parameters:
        path (str): The original file or directory path.
        maximum (int): The maximum value of the path length allowed by Windows. The Default value is 260

    Returns:
        str: The modified path that can be used if the original path exceeds the maximum path length allowed by Windows.

    """
    if PLATFORM != WINDOWS:
        logging.warning("This 'touncpath' function is only for Windows OS.")
        return path
    if re.search(r'^\\\\\?(\\UNC)?', path):
        return path
    if len(path) > maximum:
        if path.startswith(r"\\"):
            path = "\\\\?\\UNC\\" + str(path[2:])
        else:
            path = "\\\\?\\" + str(path)
    return path


def windows(path: str):
    # when path-split quote not exists, raise an error
    if "/" not in path and "\\" not in path:
        raise ParameterError(f"Path '{path}' is not a valid path.")
    result: str = str(os.path.join(*path.split(os.sep)).replace('/', '\\'))
    # when the step at before removes the \\, add it.
    if path.startswith(r"\\") and not result.startswith(r"\\"):
        result = r"\\" + result
    result = re.sub(r"(?<!/):(\\+)?", ":", result)
    result = re.sub(r"(?<!/):", r":\\", result)
    # deal with a long path
    if len(result) > WINDOWS_MAX_PATH:
        result = touncpath(result)
        if path.startswith(r"\\"):
            return result
    return result


def unix(path: str):
    if "/" not in path and "\\" not in path:
        raise ParameterError(f"Path '{path}' is not a valid path.")
    path = os.path.normpath(path).replace("\\", "/")
    return path


def adaptive(path: str):
    if PLATFORM == WINDOWS:
        return windows(path)
    return unix(path)


def is_filepath(anchor: str) -> bool:
    if os.path.exists(anchor):
        return True
    if PLATFORM == WINDOWS:
        rgx = r"(^(?:[a-zA-Z]:\\)|(?:\\\\\?\\UNC)|(?:\\\\[\w.?]+\\[\w.$?]+))(?:[\w\-]+\\)*[\w\-]+([\w\-.])+$"
    else:
        rgx = r"^(/)?([a-zA-Z0-9_.-]+(/)?)+$"
    return re.match(rgx, anchor) is not None
