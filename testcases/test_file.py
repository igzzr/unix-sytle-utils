import logging
import os
import re
import time
import unittest
import uuid
from typing import Dict, Sequence

from ust.defines import PLATFORM, WINDOWS, UNIX
from ust.errors import InvalidArgType
from ust.file import copy, F_FORCE, F_UPDATE, F_IGNORE, F_RECURSIVE, grep, remove


def str2timestamp(s: str) -> float:
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


def timestamp2str(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def get_uuid():
    # Generate a random UUID
    return str(uuid.uuid4())


def is_sequence_same(s1: Sequence, s2: Sequence) -> bool:
    if len(s1) != len(s2):
        return False
    # sum the hash code
    hash1 = 0
    hash2 = 0
    for c1, c2 in zip(s1, s2):
        hash1 += hash(c1)
        hash2 += hash(c2)
    return hash1 == hash2


class BasicCopyTest(unittest.TestCase):
    if PLATFORM == UNIX:
        HomePath = os.getenv("HOME")
    elif PLATFORM == WINDOWS:
        HomePath = os.getenv("USERPROFILE")
    else:
        assert False, "Unknown platform"

    Root = os.path.join(HomePath, "tmp")
    Data = {}

    def tearDown(self):
        if os.path.exists(self.Root):
            import shutil
            shutil.rmtree(self.Root)

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


class TestCopyFile(BasicCopyTest):
    """
        Test cases for the copy function in the file module.
    """
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


class TestRecurCopyFile(BasicCopyTest):
    Data = {
        "cp -rf": {
            "src": {
                "basedir": "source",
                "files": [
                    {
                        "filename": "1.txt",
                        "content": get_uuid()
                    },
                    {
                        "filename": "sub/2.txt",
                        "content": get_uuid()
                    },
                    {
                        "filename": "sub/inner/3.txt",
                        "content": get_uuid()
                    }
                ]
            },
            "dest": {
                "basedir": "destination",
                "files": [{
                    "filename": "1.txt",
                    "content": get_uuid()
                }]
            },
            "expect": {
                "basedir": "destination",
                "files": [
                    {
                        "filename": "1.txt",  # same to destination/1.txt
                    },
                    {
                        "filename": "sub/2.txt",  # same to source/sub/2.txt
                    },
                    {
                        "filename": "sub/inner/3.txt",  # same to source/sub/inner/3.txt
                    }
                ]
            },
        }
    }

    def generate(self, testdata: Dict) -> str:
        basedir = os.path.join(self.Root, testdata.get("basedir"))
        file_items = testdata.get("files")

        for item in file_items:
            filepath = os.path.join(self.Root, basedir, item.get("filename"))

            if not os.path.exists(filepath):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as fp:
                fp.write(item.get("content", ""))
                logging.info("Write file: %s", filepath)
                logging.info("Content: %s", item.get("content"))

        return basedir

    def test_recursive_force_copyfile_when_dest_exists(self):
        testdata = self.Data.get("cp -rf")
        src = self.generate(testdata.get("src"))
        dst = self.generate(testdata.get('dest'))
        expect = dst

        copy(src, dst, mode=F_FORCE | F_RECURSIVE)

        cnt = 0
        for root, folder, files in os.walk(expect):
            for file in files:
                filename = os.path.join(root, file)
                content = self.readfile(filename)
                assert content == self.readfile(filename.replace(dst, src))
                cnt += 1
        assert cnt == len(testdata.get("expect").get("files"))


class TestGrep(BasicCopyTest):
    Data = {
        "grep file by regex string": {
            "filename": "1.txt",
            "content": "Hello World",
            "regex": r'o\w',
            'expect': ['or']
        },
        "grep file by pattern": {
            "filename": "1.txt",
            "content": "Hello World",
            "regex": re.compile(r'o\s?\w+'),
            'expect': ['o World']
        },
        "grep file but file not found": {
            "filename": "1.txt",
            "content": "Hello World",
            "regex": re.compile(r'o\s?\w+'),
            'expect': ['o World']
        },
        'grep file but anchor is a dir': {
            "filename": "tmp/",
            "content": "Hello World",
            "regex": re.compile(r'o\s?\w+'),
            'expect': ['o World']
        },
        'grep file multi': {
            "filename": "1.txt",
            "content": "To be or not to be.",
            "regex": re.compile(r'[TtOo]{2}'),
            'expect': ['To', 'to', 'ot']
        },
        'grep string multi': {
            "content": "To be or not to be\n That is a question.",
            "regex": re.compile(r'[TtOo]{2}'),
            'expect': ['To', 'to', 'ot']
        }
    }

    def test_grep_file_by_regex_string(self):
        testdata = self.Data.get("grep file by regex string")
        filepath = self.generate(testdata)

        found = grep(filepath, testdata.get("regex"))

        self.assertEqual(found, testdata.get('expect'))

    def test_grep_file_by_pattern(self):
        testdata = self.Data.get("grep file by pattern")
        filepath = self.generate(testdata)
        found = grep(filepath, testdata.get("regex"))

        self.assertEqual(found, testdata.get('expect'))

    def test_grep_file_but_file_not_found(self):
        testdata = self.Data.get("grep file by pattern")
        filepath = self.generate(testdata)
        with self.assertRaises(InvalidArgType):
            remove(filepath)
            grep(filepath, testdata.get("regex"))

    def test_grep_file_but_is_a_dir(self):
        testdata = self.Data.get("grep file but anchor is a dir")
        filepath = self.generate(testdata)
        with self.assertRaises(InvalidArgType):
            grep(filepath, testdata.get("regex"))

    def test_grep_file_multi(self):
        testdata = self.Data.get("grep file multi")
        filepath = self.generate(testdata)
        found = grep(filepath, testdata.get("regex"), index=-1)

        self.assertTrue(is_sequence_same(found, testdata.get('expect')))

    def test_grep_string_multi(self):
        testdata = self.Data.get("grep string multi")
        found = grep(testdata.get('content'), testdata.get('regex'), index=-1)
        self.assertTrue(is_sequence_same(found, testdata.get('expect')))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
