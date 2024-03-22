import glob
import logging
import os
import re
import shutil
from typing import NoReturn

from defines import PLATFORM, WINDOWS
from path import adaptive

F_REPLACE = 1  # default mode when file exists replace it.
F_IGNORE = 2  # ignore same file when recursive
F_RECURSIVE = 4  # copy directories recursively
F_UPDATE = 8  # when file is same and newer, replace it

F_FORCE = F_REPLACE
F_ONLY_REMOVE_EMPTY = 16


def _copy_by_command(src, dest):
    if PLATFORM == WINDOWS:
        if os.path.isdir(src):
            cmd = f'xcopy "{src}" "{dest}" /s /e /y /k /o /q'
        else:
            cmd = f'xcopy "{src}" "{dest}" /y /q/ /f'
    else:
        cmd = f'cp -rf "{src}" "{dest}"'
    logging.info(f"Command: {cmd}")
    code = os.system(cmd)
    logging.info(f"Copy folder return code: {code}")


def _copy_recursively(src: str, dest: str, mode: int = F_REPLACE) -> NoReturn:
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
            copyfile(src_file, dest_file, mode)


def copy(src: str, dest: str, mode: int = F_REPLACE) -> NoReturn:
    src = adaptive(src)
    dest = adaptive(dest)
    if not os.access(src, os.R_OK):
        raise PermissionError(f"Permission denied: {src}")
    if not os.access(src, os.W_OK):
        raise PermissionError(f"Permission denied: {dest}")

    if src == dest:
        raise ValueError("Source and destination are the same file.")

    if src.endswith("*"):
        return copytree(src[-1], dest, mode)

    dirname = os.path.dirname(dest)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)

    # dst is a folder and not exits
    if dest.endswith(os.sep) and not os.path.splitext(os.path.basename(dest))[1] and not os.path.exists(dest):
        os.makedirs(dest)

    # when target not exists, only two situations
    if not os.path.exists(dest):
        if os.path.isdir(src):
            return copytree(src=src, dest=dest, mode=mode)
        return copyfile(src=src, dest=dest, mode=mode)

    # when target exists, three situations
    if os.path.isdir(dest):
        # folder/* -> folder/
        if os.path.isdir(src):
            return copytree(src=src, dest=dest, mode=mode)
        # file -> folder/
        return copyfile(src=src, dest=dest, mode=mode)
    # file -> file
    return copyfile(src=src, dest=dest, mode=mode)


def copyfile(src: str, dest: str, mode: int = F_REPLACE) -> NoReturn:
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


def copytree(src: str, dest: str, mode: int = F_REPLACE) -> NoReturn:
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


def remove(src: str, mode: int = F_FORCE) -> NoReturn:
    paths = [src]
    if "*" in src or "?" in src:
        paths = glob.glob(src, recursive=bool(mode & F_RECURSIVE))
    elif not os.path.exists(src):
        return

    for tmp in paths:
        try:
            if os.path.isdir(tmp):
                shutil.rmtree(tmp)
            elif os.path.isfile(tmp):
                os.remove(tmp)
            else:
                raise OSError(f"Can't remove file '{tmp}'{os.stat(tmp)}")
        except (shutil.Error, OSError) as e:
            if PLATFORM == WINDOWS:
                if re.search(r'^[a-zA-Z]+:[/\\]+$', tmp):
                    logging.critical(f"Can't remove any storage driver '{tmp}'")
                if os.path.isdir(tmp):
                    cmd = f"rmdir /s /q {tmp}"
                else:
                    cmd = f"del {tmp}"
            else:
                if tmp == "/":
                    logging.critical("Can't remove / not")
                cmd = f"rm -rf {tmp}"
            logging.info(f"Command: {cmd}")
            code = os.system(cmd)
            if code != 0:
                logging.error(e)
            logging.info(f"Remove command return code: {code}")


def move(src: str, dest: str, mode: int = F_REPLACE) -> NoReturn:
    copy(src, dest, mode)
    remove(src, mode)
