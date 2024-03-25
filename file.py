import glob
import logging
import os
import re
import shutil
from typing import Sequence, Union, Set, List

from defines import PLATFORM, WINDOWS, UNIX
from errors import FileRemoveError
from file import F_REPLACE, F_RECURSIVE, F_UPDATE, F_IGNORE, F_NOSET, F_RM_DIR, F_RM_FILE, F_FORCE, Paths
from path import adaptive


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
        [file1, file2,file3] -> '/tmp/folder/'. Iteratively copy them to 'dest'. just like cp -t DEST

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
        _copy(p, dest, mode)


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


def remove(src: str, mode: int = F_NOSET) -> None:
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
    paths = [src]
    if "*" in src or "?" in src:
        paths = glob.glob(src, recursive=bool(mode & F_RECURSIVE))
    elif not os.path.exists(src):
        return

    # when remove mode not set, both file and directory will be removed.
    if not mode & F_RM_DIR and not mode & F_RM_FILE:
        mode = F_RM_FILE | F_RM_DIR

    win_divers_pattern = re.compile(r'^[a-zA-Z]+:[/\\]+$')
    for p in paths:
        if PLATFORM == WINDOWS and win_divers_pattern.search(p):
            raise FileRemoveError(f"Can't remove windows driver: '{p}'")
        if PLATFORM == UNIX and p.strip() == "/":
            raise FileRemoveError("Can't remove the unix root '/'")
        if os.path.isdir(p) and mode & F_RM_DIR:
            shutil.rmtree(p)
        elif os.path.isfile(p) and mode & F_RM_FILE:
            os.remove(p)
        else:  # link, maybe don't raise error?
            raise FileRemoveError(f"Can't remove file '{p}'{os.stat(p)}")


def move(src: str, dest: str, mode: int = F_FORCE) -> None:
    if not os.path.exists(src):
        raise FileNotFoundError(src)
    if src == dest:
        return

    _generate_dirs(dest)

    if os.path.isfile(src):
        # file -> dir
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(src))
        if os.path.exists(dest) and mode & F_IGNORE:
            return
        return shutil.move(src, dest)
    # dir -> dir
    if os.path.exists(dest) and mode & F_IGNORE:
        return
    return shutil.move(src, dest)


def rec_move(src: str, dest: str, mode: int = F_FORCE):
    src = adaptive(src)
    dest = adaptive(dest)

    paths = [src]
    if "*" in src or "?" in src:
        paths = glob.glob(src, recursive=bool(mode & F_RECURSIVE))
    elif not os.path.exists(src):
        raise FileNotFoundError(src)
    for p in paths:
        move(p, dest)


if __name__ == '__main__':
    move("D:\\4.py", 'D:\\5.py')
