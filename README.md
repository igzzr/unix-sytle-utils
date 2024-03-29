# Unix Style Utils
Use python functions as you would with unix commands.
Such as cp -r; rm -rf and so on.
There are some const flags has been defined.
```python
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
```
You can use these flags, just like cp -rf
```
cp(src,dst, F_FORCE |F_RECURSIVE )
```
