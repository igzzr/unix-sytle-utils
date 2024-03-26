import glob
import logging
import os
import re
import shutil
import stat
from typing import Callable
from typing import List, Set, Union

from defines import PLATFORM, WINDOWS, UNIX
from errors import FileRemoveError, UnsupportedModeError, FileMoveError, InvalidArgType
from path import adaptive

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
for k, v in VALUE2NAME:
    NAME2VALUE[v] = k

Paths = Union[str, List, Set]


def _generate_dirs(path: str) -> None:
    # generate for '/tmp/not_exist_sub_dir/file' -> '/tmp/not_exist_sub_dir'
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
        logging.debug(f"Generate {dirname} ok.")
    # generate for '/tmp/not_exist_sub_dir/' -> '/tmp/not_exist_sub_dir'
    if path.endswith(os.sep) and not os.path.exists(path):
        os.makedirs(path)
        logging.debug(f"Generate {path} ok.")


def _copy_by_command(src: str, dest: str) -> None:
    if PLATFORM == WINDOWS:
        if os.path.isdir(src):
            cmd = f'xcopy "{src}" "{dest}" /s /e /y /k /o /q'
        else:
            cmd = f'xcopy "{src}" "{dest}" /y /q/ /f'
    else:
        cmd = f'cp -rf "{src}" "{dest}"'
    logging.info(f"Command: {cmd}")
    code = os.system(cmd)
    if code != 0:
        raise OSError(f"Can't copy file '{src}' to '{dest}'")


def _copy_recursively(src: str, dest: str, mode: int = F_REPLACE) -> None:
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
    if mode & unsupported_mode:
        raise UnsupportedModeError(
            f"Unsupported mode: '{VALUE2NAME.get(unsupported_mode, 'Unknown')}:{unsupported_mode}'")

    if mode & F_TARGET_DIRECTORY and not (isinstance(src, List) or isinstance(src, Set)):
        raise InvalidArgType(f"Only List or Set type is allowed when F_TARGET_DIRECTORY is set.")

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
    src = adaptive(src)
    dest = adaptive(dest)
    if os.path.exists(dest):
        if mode & F_RECURSIVE:
            return _copy_recursively(src, dest, mode)
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


def move(src: Union[str, List, Set], dest: str, mode: int = F_FORCE) -> None:
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


if __name__ == '__main__':
    move("D:\\b", 'D:\\1\\', mode=F_FORCE | F_RECURSIVE)
