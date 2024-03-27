import logging
import os
import time
import unittest
from typing import Dict

from defines import PLATFORM, WINDOWS, UNIX
from file import copy, F_FORCE, F_UPDATE, F_IGNORE


def str2timestamp(s: str) -> float:
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


def timestamp2str(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


class TestCopyFile(unittest.TestCase):
    """
        Test cases for the copy function in the file module.
    """
    if PLATFORM == UNIX:
        HomePath = os.getenv("HOME")
    elif PLATFORM == WINDOWS:
        HomePath = os.getenv("USERPROFILE")
    else:
        assert False, "Unknown platform"

    Root = os.path.join(HomePath, "tmp")
    # region test data
    Data = {
        "cp": {
            'src': {
                'filename': '1.txt',
                'content': "Hello World"
            },
            'dest': {
                'filename': 'directory/'
            },
            'expected': {
                'filename': 'directory/1.txt',
            }
        },
        'cp -f': {
            'src': {
                'filename': '1.txt',
                'content': "Hello World For cp -f"
            },
            'dest': {
                'filename': 'directory/1.txt',
                'content': 'Hi cp -f'
            },
            'expected': {
                'filename': 'directory/1.txt',
            }
        },
        'cp -u': {
            'src': {
                'filename': '1.txt',
                'content': "Hello World",
                'mtime': '2020-01-02 00:00:00'
            },
            'dest': {
                'filename': 'directory/1.txt',
                'content': 'Hi',
                'mtime': '2020-01-01 00:00:00'
            },
            'expected': {
                'filename': 'directory/1.txt',
            }
        },
        'cp -u failed': {
            'src': {
                'filename': '1.txt',
                'content': "Hello World",
                'mtime': '2020-01-01 00:00:00'
            },
            'dest': {
                'filename': 'directory/1.txt',
                'content': 'Hi F_UPDATE Failed',
                'mtime': '2020-01-02 00:00:00'
            },
            'expected': {
                'filename': 'directory/1.txt',
            }
        },
        'cp -i': {
            'src': {
                'filename': '1.txt',
                'content': "Hello World",
            },
            'dest': {
                'filename': 'directory/1.txt',
                'content': 'Hi F_IGNORE',
            },
            'expected': {
                'filename': 'directory/1.txt',
            }
        },

    }
    # end region

    def tearDown(self):
        if os.path.exists(self.Root):
            import shutil
            shutil.rmtree(self.Root)

    def test_copyfile_when_dest_not_exists(self):
        testdata = self.Data.get("cp")
        src = self.generate(testdata.get("src"))
        dest = self.generate(testdata.get('dest'))

        copy(src, dest)

        content = self.readfile(testdata.get('expected').get('filename'))
        assert content == testdata.get("src").get("content")

    def test_force_copyfile_when_dest_exists(self):
        testdata = self.Data.get("cp -f")
        src = self.generate(testdata.get("src"))
        dest = self.generate(testdata.get('dest'))

        copy(src, dest, mode=F_FORCE)

        content = self.readfile(testdata.get('expected').get('filename'))
        assert content == testdata.get("src").get("content")

    def test_update_copyfile_when_dest_exists(self):
        testdata = self.Data.get("cp -u")
        src = self.generate(testdata.get("src"))
        dest = self.generate(testdata.get('dest'))

        copy(src, dest, mode=F_UPDATE)
        expect = os.path.join(self.Root, testdata.get('expected').get('filename'))
        content = self.readfile(expect)
        assert content == testdata.get("src").get("content")

        expect_time = timestamp2str(os.path.getmtime(expect))
        assert expect_time == testdata.get("src").get("mtime")

    def test_update_failed_copyfile_when_dest_exists(self):
        testdata = self.Data.get("cp -u failed")
        src = self.generate(testdata.get("src"))
        dest = self.generate(testdata.get('dest'))

        copy(src, dest, mode=F_UPDATE)

        expect = os.path.join(self.Root, testdata.get('expected').get('filename'))
        content = self.readfile(expect)
        assert content == testdata.get("dest").get("content")

        expect_time = timestamp2str(os.path.getmtime(expect))
        assert expect_time == testdata.get("dest").get("mtime")

    def test_ignore_copyfile_when_dest_exists(self):
        testdata = self.Data.get("cp -i")
        src = self.generate(testdata.get("src"))
        dest = self.generate(testdata.get('dest'))

        copy(src, dest, mode=F_IGNORE)

        content = self.readfile(testdata.get('expected').get('filename'))
        assert content == testdata.get("dest").get("content")

    def generate(self, testdata: Dict) -> str:
        filename = testdata.get("filename")
        filepath = os.path.join(self.Root, filename)

        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if filepath.endswith('\\') or filepath.endswith("/"):
            os.makedirs(filepath, exist_ok=True)
            return filepath

        with open(filepath, 'w', encoding='utf-8') as fp:
            fp.write(testdata.get("content", ""))
            logging.info("Write file: %s", filepath)
            logging.info("Content: %s", testdata.get("content"))
        if 'mtime' in testdata:
            os.utime(filepath, (str2timestamp(testdata.get("mtime")), str2timestamp(testdata.get("mtime"))))
        return filepath

    def readfile(self, filename: str) -> str:
        if self.Root not in filename:
            filename = os.path.join(self.Root, filename)
        with open(filename, 'r', encoding='utf-8') as fp:
            return fp.read()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()