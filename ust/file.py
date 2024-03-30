"""
This module provides functions for file and directory operations.

It includes functions for copying, moving, and removing files or directories.
The functions support various modes of operation, such as replacing existing files, updating files, and ignoring files.

Functions:
    copy(src: Paths, dest: str, mode: int = F_REPLACE) -> None:
        Copies a file or directory from a source path to a destination path.

    move(src: Paths, dest: str, mode: int = F_FORCE) -> None:
        Moves a file or directory from a source path to a destination path.

    remove(src: Paths, mode: int = F_NOSET) -> None:
        Removes a file or directory from a source path.
"""
import glob
import logging
import os
import re
import shutil
import stat
from typing import Callable
from typing import List, Set, Union

from .defines import PLATFORM, WINDOWS, UNIX, WINDOWS_MAX_PATH
from .errors import FileRemoveError, UnsupportedModeError, FileMoveError, InvalidArgType
from .path import adaptive, is_filepath

# region cp rm mv global defines
F_NOSET = 0
F_FORCE = 1  # -f --force. default mode when file exists replace it.
F_IGNORE = 2  # -i. ignore same file when recursive. BTW, in unix this arg for prompt.
F_RECURSIVE = 4  # -r --recursive. copy directories recursively
F_UPDATE = 8  # -u --update. when file is same and newer, replace it
F_TARGET_DIRECTORY = 16  # -t --target-directory.

F_RM_DIR = 32  # for only remove directory
F_RM_FILE = 64  # for only remove file
F_RM_EMPTY = 128  # -d --dir. remove empty
F_REPLACE = F_FORCE

VALUE2NAME = {
    F_NOSET: 'F_NOSET',
    F_FORCE: 'F_FORCE',
    F_IGNORE: 'F_IGNORE',
    F_RECURSIVE: 'F_RECURSIVE',
    F_UPDATE: 'F_UPDATE',
    F_TARGET_DIRECTORY: 'F_TARGET_DIRECTORY',
    F_RM_DIR: 'F_RM_DIR',
    F_RM_FILE: 'F_RM_FILE',
    F_RM_EMPTY: 'F_RM_EMPTY',
    F_REPLACE: 'F_REPLACE',
}
NAME2VALUE = {}
for k, v in VALUE2NAME.items():
    NAME2VALUE[v] = k

Paths = Union[str, List, Set]
Pattern = Union[str, re.Pattern]
# endregion cp rm mv global defines

# region cmp global defines
C_SHADOW = 1  # only compare file sign
C_BINARY = 2  # compare file as binaries
C_TEXT = 4  # compare file as text
C_IGNORE_BLANK_LINES = 8  # skip blank lines when compare text
C_IGNORE_CASE = 16  # ignore case when compare text
C_RECURSIVE = 32  # compare files recursively
BUFFER_SIZE = 1024 * 4  # 1 page

_cache = {}


# endregion cmp global defines

def _generate_dirs(path: str) -> None:
    """Generates directories for a given path.

    Args
        path (str): The path for which to generate directories.

    Returns
        None
    """
    # generate for '/tmp/not_exist_sub_dir/file' -> '/tmp/not_exist_sub_dir'
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
        logging.debug("Generate %s ok." % dirname)
    # generate for '/tmp/not_exist_sub_dir/' -> '/tmp/not_exist_sub_dir'
    if path.endswith(os.sep) and not os.path.exists(path):
        os.makedirs(path)
        logging.debug("Generate %s ok." % path)


def _copy_by_command(src: str, dest: str) -> None:
    """Copy file or directory by command.

    Args:
        src (str): The source file or directory path.
        dest (str): The destination path.

    Returns:
        None
    """
    if PLATFORM == WINDOWS:
        if os.path.isdir(src):
            cmd = f'xcopy "{src}" "{dest}" /s /e /y /k /o /q'
        else:
            cmd = f'xcopy "{src}" "{dest}" /y /q/ /f'
    else:
        cmd = f'cp -rf "{src}" "{dest}"'
    logging.info("Command: %s " % cmd)
    code = os.system(cmd)
    if code != 0:
        raise OSError(f"Can't copy file '{src}' to '{dest}'")


def _copy_recursively(src: str, dest: str, mode: int = F_REPLACE) -> None:
    """Recursively copy files from source directory to destination directory.

    Args:
        src (str): The source directory path.
        dest (str): The destination directory path.
        mode (int): The mode of copying.

    Returns:
        None
    """
    if not os.path.isdir(src):
        return
    for root, folders, files in os.walk(src):
        for folder in folders:
            src_folder = os.path.join(root, folder)
            dest_folder = os.path.join(dest, os.path.relpath(src_folder, src))
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)
        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest, os.path.relpath(src_file, src))
            _copyfile(src_file, dest_file, mode)


def entry(src: Paths,
          dest: str,
          mode: int = F_REPLACE,
          *,
          unsupported_mode: int,
          enter_func: Callable[[str, str, int], None]) -> None:
    """Entry function for file operations.

    This function serves as an entry point for file operations such as copy, move, and remove.
    It checks the mode of operation and the type of source path, and then calls the appropriate function.

    Args:
        src (Paths): The source file or directory path.
        dest (str): The destination path.
        mode (int, optional): The mode of operation. Defaults to F_REPLACE.
        unsupported_mode (int): The mode that is not supported by the operation.
        enter_func (Callable[[str, str, int], None]): The function to be called for the operation.

    Raises:
        UnsupportedModeError: If the mode of operation is not supported.
        InvalidArgType: If the type of source path is not valid.
        TypeError: If the type of 'src' is not one of Paths.
    """
    if mode & unsupported_mode:
        raise UnsupportedModeError(
            f"Unsupported mode: '{VALUE2NAME.get(unsupported_mode, 'Unknown')}:{unsupported_mode}'")

    if mode & F_TARGET_DIRECTORY and not (isinstance(src, (List, Set))):
        raise InvalidArgType("Only List or Set type is allowed when F_TARGET_DIRECTORY is set.")

    if isinstance(src, str):
        if "*" in src or "?" in src:
            paths = glob.glob(src, recursive=bool(mode & F_RECURSIVE))
        else:
            paths = [src]
    elif isinstance(src, List):
        paths = src
    elif isinstance(src, Set):
        paths = list(src)
    else:
        raise TypeError(f"The type of 'src' must be one of {Paths}")
    for p in paths:
        enter_func(p, dest, mode)


def copy(src: Paths, dest: str, mode: int = F_REPLACE) -> None:
    """Copies a file or directory from a source path to a destination path.

    For src is a normal string.
        '~/file' -> '/tmp/file'.
            Skipping copy when F_IGNORE is set .

        '~/file' -> '/tmp/file'.
            Replacing it by '~/file' when F_REPLACE is set.

        '~/file' -> '/tmp/file'.
            Replacing it by '~/file' when F_UPDATE is set and '~/file' is the new one

        '~/folder/'-> '/tmp/folder/'.
            Replace '/tmp/folder/' when F_REPLACE is set but F_RECURSIVE is not set.

        '~/folder' -> '/tmp/folder/'.
            Recursively replace each file but skip the same name file. when both F_IGNORE and F_RECURSIVE are set.

        '~/folder' -> '/tmp/folder/'.
            Recursively replace each file with the same name when both F_REPLACE and F_RECURSIVE are set.

        '~/folder' -> '/tmp/folder/'.
            Recursively update each file with the same name when both F_UPDATE and F_RECURSIVE are set.

    For src is a glob string.
        call 'glob.glob("/path/to/find/*.txt")' to search files, and iteratively copy them to 'dest'

    For src is a List or Set.
        [file1, file2,file3] -> '/tmp/folder/'.
         F_TARGET_DIRECTORY must be set. Iteratively copy them to 'dest'. just like cp -t DEST

    Args:
        src (str): The source file or directory path to copy.
        dest (str): The destination path where to copy the source file or directory.
        mode (int, optional): The mode of copying. Defaults to F_REPLACE.
        It means if the destination file or directory already exists, it will be replaced.

    Raises:
        TypeError: if the src is not one of Paths Type.
        PermissionError: If the source or destination paths are not accessible.
        ValueError: If the source and destination paths are the same.

    Returns:
        None
    """
    return entry(src, dest, mode, unsupported_mode=F_RM_DIR | F_RM_FILE | F_RM_EMPTY, enter_func=_copy)


def _copy(src: str, dest: str, mode: int = F_REPLACE) -> None:
    """ Copies a file or directory from a source path to a destination path.

    Mainly function of copy

    Args:
        src (str): The source file or directory path to copy.
        dest (str): The destination path where to copy the source file or directory.
        mode (int): The mode of copying.

    Returns:
        None
    """
    src = adaptive(src)
    dest = adaptive(dest)
    if not os.access(src, os.R_OK):
        raise PermissionError(f"Permission denied: {src}")
    if not os.access(src, os.W_OK):
        raise PermissionError(f"Permission denied: {dest}")

    if src == dest:
        raise ValueError("Source and destination are the same file.")

    _generate_dirs(dest)

    # when target not exists, only two situations
    if not os.path.exists(dest):
        if os.path.isdir(src):
            return _copytree(src=src, dest=dest, mode=mode)
        return _copyfile(src=src, dest=dest, mode=mode)

    # when target exists, three situations
    if os.path.isdir(dest):
        # folder/* -> folder/
        if os.path.isdir(src):
            return _copytree(src=src, dest=dest, mode=mode)
        # file -> folder/
        return _copyfile(src=src, dest=dest, mode=mode)
    # file -> file
    return _copyfile(src=src, dest=dest, mode=mode)


def _copyfile(src: str, dest: str, mode: int = F_REPLACE) -> None:
    """ Copies a file from a source path to a destination path.

    Args:
        src (str): The source file or directory path to copy.
        dest (str): The destination path where to copy the source file or directory.
        mode (int): The mode of copying.

    Returns:
        None
    """
    src = adaptive(src)
    dest = adaptive(dest)
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(src))

    if os.path.exists(dest):
        if mode & F_REPLACE:
            os.remove(dest)
        elif mode & F_UPDATE:
            if os.path.getmtime(src) <= os.path.getmtime(dest):
                return
            os.remove(dest)
        elif mode & F_IGNORE:
            return
    try:
        shutil.copy2(src, dest)
    except (shutil.Error, PermissionError, OSError):
        _copy_by_command(src, dest)


def _copytree(src: str, dest: str, mode: int = F_REPLACE) -> None:
    """
    Copies a directory from a source path to a destination path.
    Args:
        src (str): The source file or directory path to copy.
        dest (str): The destination path where to copy the source file or directory.
        mode (int): The mode of copying.

    Returns:
        None
    """
    src = adaptive(src)
    dest = adaptive(dest)
    if os.path.exists(dest):
        if mode & F_RECURSIVE:
            _copy_recursively(src, dest, mode)
            return
        if mode & F_REPLACE:
            remove(dest)
        elif mode & F_UPDATE:
            if os.path.getmtime(src) <= os.path.getmtime(dest):
                return
            remove(dest)
        elif mode & F_IGNORE:
            return
    try:
        shutil.copytree(src, dest)
    except (shutil.Error, PermissionError):
        _copy_by_command(src, dest)


def _remove(path: str, dest: str = "", mode: int = F_NOSET) -> None:
    """Removes a file or directory from a source path.
    Args:
        path (str): The source file or directory path to remove.
        dest (str): Redundant arg, not used.
        mode (int): The mode of removing.

    Returns:
        None
    """
    if dest:
        raise InvalidArgType("Unsupported arg 'dest'")
    # when remove mode not set, both file and directory will be removed.
    if not mode & F_RM_DIR and not mode & F_RM_FILE:
        mode = F_RM_FILE | F_RM_DIR

    # when use -d --dir, delete the path when it is dir and empty
    if mode & F_RM_EMPTY:
        mode = F_RM_EMPTY

    win_divers_pattern = re.compile(r'^[a-zA-Z]+:[/\\]+$')
    path = adaptive(path)
    if PLATFORM == WINDOWS and win_divers_pattern.search(path):
        raise FileRemoveError(f"Can't remove windows driver: '{path}'")
    if PLATFORM == UNIX and path.strip() == "/":
        raise FileRemoveError("Can't remove the unix root '/'")
    if os.path.isdir(path):
        if mode & F_RM_EMPTY and len(os.listdir(path)) == 0:
            os.remove(path)
            return
        if mode & F_RM_DIR:
            shutil.rmtree(path)
    elif os.path.isfile(path) and mode & F_RM_FILE:
        os.remove(path)
    else:  # link, maybe don't raise error?
        raise FileRemoveError(f"Can't remove file '{path}'{os.stat(path)}")


def remove(src: Paths, mode: int = F_NOSET) -> None:
    """Removes a file or directory from a source path.

    Both F_RM_DIR and F_RM_FILE are set by default.

    if F_RECURSIVE is set, it works like 'find $src -name 'xx'  -exec rm -rf {} +'

    If F_RM_DIR | F_RECURSIVE  is set, it works like 'find $src -name 'xx' -type d -exec rm -rf {} +'

    If F_RM_FILE | F_RECURSIVE is set, it works like 'find $src -name 'xx' -type f -exec rm -rf {} +'

    Args:
        src (str): The source file or directory path to remove.
        mode (int, optional): The mode of removing. Defaults to F_NOSET.

    Raises:
        FileRemoveError: If the source file or directory cannot be removed. Or trying to remove the root directory.

    Returns:
        None
    """
    return entry(src, "", mode, unsupported_mode=F_REPLACE | F_UPDATE | F_IGNORE, enter_func=_remove)


def _move(src: str, dest: str, mode: int = F_FORCE) -> None:
    """ Moves a file or directory from a source path to a destination path.

    Args:
        src (str): The source file or directory path to move.
        dest (str): The destination path where to move the source file or directory.
        mode (int): The mode of moving.

    Returns:
        None
    """

    def _sig(file):
        st = os.stat(file)
        return stat.S_IFMT(st.st_mode)

    if not mode & F_FORCE and os.path.exists(dest):
        raise FileMoveError(f"Can't move '{src}' to '{dest}': File exists.")

    # in the same directory
    if os.path.dirname(src) == os.path.dirname(dest):
        if _sig(src) != _sig(dest):
            if not mode & F_RECURSIVE:
                raise FileMoveError(f"Can't move '{src}' to '{dest}': Different file type.")
        _remove(dest, mode=mode)
        os.rename(src, dest)
        return
    _copy(src, dest, mode)
    _remove(src, dest, mode=mode)


def move(src: Paths, dest: str, mode: int = F_FORCE) -> None:
    """Moves a file or directory from a source path to a destination path.

    Args:
        src (str): The source file or directory path to move.
        dest (str): The destination path where to move the source file or directory.
        mode (int, optional): The mode of moving. Defaults to F_FORCE.
        It means if the destination file or directory already exists, it will be replaced.

    Raises:
        TypeError: if the src is not one of Paths Type.
        PermissionError: If the source or destination paths are not accessible.
        ValueError: If the source and destination paths are the same file.

    Returns:
        None
    """
    return entry(src, dest, mode, unsupported_mode=F_RM_DIR | F_RM_FILE | F_RM_EMPTY, enter_func=_move)


def _grep_file(anchor: str, regex: Pattern, index: int, encoding='utf-8') -> List[str]:
    """
    Searches for a regex pattern within a file.

    Args:
        anchor (str): The path to the file to be searched.
        regex (Pattern): The regex pattern to search for.
        index (int): If positive, returns the matching group. If negative, returns all matches.

    Returns:
        List[str]: A list of matching strings.

    """
    found: List[str] = []

    pattern = regex
    if isinstance(regex, str):
        pattern = re.compile(regex)

    with open(anchor, 'r', encoding=encoding, errors='ignore') as fp:
        for line in fp:
            if index < 0:
                found.extend(pattern.findall(line))
                continue
            match = pattern.search(line)
            if not match:
                continue
            found.append(match.group(index))
    return found


def _grep_string(anchor: str, regex: Pattern, index: int) -> List[str]:
    """
    Searches for a regex pattern within a string.

    Args:
        anchor (str): The string to be searched.
        regex (Pattern): The regex pattern to search for.
        index (int): If positive, returns the matching group. If negative, returns all matches.

    Returns:
        List[str]: A list of matching strings.

    """
    found: List[str] = []

    pattern = regex
    if isinstance(regex, str):
        pattern = re.compile(regex)

    for line in anchor.splitlines():
        if index < 0:
            found.extend(pattern.findall(line))
            continue
        match = pattern.match(line)
        if not match:
            continue
        found.append(match.group(index))
    return found


def grep(anchor: str, regex: Pattern, index=0, encoding='utf-8') -> List[str]:
    """
    Searches for a regex pattern within a string or a file.

    If the anchor is a file path, it searches within the file. If the anchor is a string, it searches within the string.

    Args:
        anchor (str): The string or file path to be searched.
        regex (Pattern): The regex pattern to search for.
        index (int, optional): If positive, returns the matching group. If negative, returns all matches. Defaults to 0.
        encoding (str, optional): default utf-8
        
    Returns:
        List[str]: A list of matching strings.

    Raises:
        InvalidArgType: If the anchor is a file-path-like string, but the file does not exist or is not a file.

    """
    if len(anchor) > WINDOWS_MAX_PATH:
        anchor = anchor[:WINDOWS_MAX_PATH]
    if is_filepath(anchor):
        if os.path.isfile(anchor):
            return _grep_file(anchor, regex, index, encoding=encoding)
        raise InvalidArgType("The path '%s' is not a file or its not found." % anchor)
    return _grep_string(anchor, regex, index)


def _sig(file):
    st = os.stat(file)
    sign = (stat.S_IFMT(st.st_mode),
            st.st_size,
            st.st_mtime)
    _cache[file] = sign
    return sign


def cmpfile(file1, file2, mode: int) -> bool:
    if file1 == file2:
        return True
    s1 = _sig(file1)
    s2 = _sig(file2)
    if s1[0] != stat.S_IFREG or s2[0] != stat.S_IFREG:
        return False
    if s2 == s1 and mode & C_SHADOW and not mode & C_BINARY:
        return True
    if mode & C_BINARY:
        # when compare binary ,shadow means whether the file1 is inner file2
        return _cmp_binaries(file1, file2, bool(mode & C_SHADOW))
    if mode & C_TEXT:
        return _cmp_text(file1, file2, mode)

    return False


def _cmp_binaries(file1: str, file2: str, shadow=False) -> bool:
    s1 = _cache.get(file1)
    s2 = _cache.get(file2)
    len1 = s1[1]
    len2 = s2[1]
    if len1 != len2 and not shadow:
        return False
    if len1 > len2:
        return False

    with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
        index = 0
        while index < len1:
            b1 = f1.read(BUFFER_SIZE)
            b2 = f2.read(BUFFER_SIZE)
            if b1 != b2:
                return False
            if not b1:
                return True
            index += len(b1)


def _cmp_text(file1: str, file2: str, mode: int) -> bool:
    pass
