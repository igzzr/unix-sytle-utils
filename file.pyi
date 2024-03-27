from typing import overload, List, Set, Union, Dict, Type

F_NOSET: int
F_FORCE: int  # -f --force. default mode when file exists replace it.
F_IGNORE: int  # -i. ignore same file when recursive. BTW, in unix this arg for prompt.
F_RECURSIVE: int  # -r --recursive. copy directories recursively
F_UPDATE: int  # -u --update. when file is same and newer, replace it
F_TARGET_DIRECTORY: int  # -t --target-directory.

F_RM_DIR: int  # for only remove directory
F_RM_FILE: int  # for only remove file
F_RM_EMPTY: int  # -d --dir. remove empty
F_REPLACE: int
Paths: Type[Union[str, List, Set]]

VALUE2NAME: Dict[int, str]
NAME2VALUE: Dict[str, int]

@overload
def copy(src: str, dest: str, mode: int = F_FORCE) -> None: ...


@overload
def copy(src: List, dest: str, mode: int = F_FORCE) -> None: ...


@overload
def copy(src: Set, dest: str, mode: int = F_FORCE) -> None: ...


@overload
def remove(src: str, mode: int = F_NOSET) -> None: ...


@overload
def remove(src: List, mode: int = F_NOSET) -> None: ...


@overload
def remove(src: Set, mode: int = F_NOSET) -> None: ...


@overload
def move(src: str, dest: str, mode: int = F_FORCE) -> None: ...


@overload
def move(src: List, dest: str, mode: int = F_FORCE) -> None: ...


@overload
def move(src: Set, dest: str, mode: int = F_FORCE) -> None: ...
