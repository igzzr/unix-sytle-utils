from typing import overload, List, Set, Union

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

Paths = Union[str, List, Set]


@overload
def copy(src: str, dest: str, mode: int = F_FORCE) -> None:
    pass


@overload
def copy(src: List, dest: str, mode: int = F_FORCE) -> None:
    pass


@overload
def copy(src: Set, dest: str, mode: int = F_FORCE) -> None:
    pass


@overload
def remove(src: str, mode: int = F_NOSET) -> None:
    pass


@overload
def remove(src: List, mode: int = F_NOSET) -> None:
    pass


@overload
def remove(src: Set, mode: int = F_NOSET) -> None:
    pass


@overload
def move(src: str, dest: str, mode: int = F_FORCE) -> None:
    pass


@overload
def move(src: List, dest: str, mode: int = F_FORCE) -> None:
    pass


@overload
def move(src: Set, dest: str, mode: int = F_FORCE) -> None:
    pass