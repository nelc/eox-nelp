"""Tests for eox_nelp.scorm_patches."""
import sys

from django.test import TestCase
from mock import patch
from openedxscorm.scormxblock import ScormXBlock

from eox_nelp import scorm_patches
from eox_nelp.scorm_patches import (
    UPSTREAM_GET_FILE_PATH_SHA256,
    get_file_path,
    patch_scorm_get_file_path,
    upstream_get_file_path_sha256,
)


class ObjectStorage:
    """Object store like GCS: exists() is False for a folder, listdir() still lists it."""

    def __init__(self, paths):
        self.paths = set(paths)

    def exists(self, name):
        """Only files are objects."""
        return name in self.paths

    def listdir(self, name):
        """List the folders and files directly under `name`."""
        prefix = name.rstrip("/") + "/"
        dirs, files = set(), set()
        for path in self.paths:
            if path.startswith(prefix):
                head, _, tail = path[len(prefix):].partition("/")
                (dirs if tail else files).add(head)
        return sorted(dirs), sorted(files)


class MissingFolderStorage:
    """Like FileSystemStorage on a folder that does not exist."""

    def listdir(self, name):
        """The folder is missing."""
        raise FileNotFoundError(name)


class Block:
    """Holds only what get_file_path needs."""

    get_file_path = get_file_path

    def __init__(self, storage):
        self.storage = storage


class GetFilePathTestCase(TestCase):
    """Test the patched get_file_path."""

    def test_finds_files_on_object_storage(self):
        """Files are found although exists() is False for every folder."""
        block = Block(ObjectStorage([
            "scorm/block/sha1/imsmanifest.xml",
            "scorm/block/sha1/story_content/index.html",
        ]))

        self.assertEqual(
            block.get_file_path("imsmanifest.xml", "scorm/block/sha1"),
            "scorm/block/sha1/imsmanifest.xml",
        )
        self.assertEqual(
            block.get_file_path("index.html", "scorm/block/sha1"),
            "scorm/block/sha1/story_content/index.html",
        )

    def test_missing_file(self):
        """A file that is not in the package returns None."""
        block = Block(ObjectStorage(["scorm/block/sha1/imsmanifest.xml"]))

        self.assertIsNone(block.get_file_path("index.html", "scorm/block/sha1"))

    def test_missing_folder(self):
        """A folder that does not exist returns None instead of raising."""
        block = Block(MissingFolderStorage())

        self.assertIsNone(block.get_file_path("imsmanifest.xml", "scorm/block/sha1"))


class PatchScormGetFilePathTestCase(TestCase):
    """Test patch_scorm_get_file_path."""

    def setUp(self):
        self.original = ScormXBlock.get_file_path

    def tearDown(self):
        ScormXBlock.get_file_path = self.original

    def test_upstream_method_unchanged(self):
        """Fails when the installed openedx-scorm-xblock changes get_file_path.

        When this fails: check whether the new upstream version still has the
        storage.exists(root) bug. If it is fixed, delete eox_nelp/scorm_patches.py
        and this test. If not, update the patch and UPSTREAM_GET_FILE_PATH_SHA256.
        """
        self.assertEqual(upstream_get_file_path_sha256(ScormXBlock), UPSTREAM_GET_FILE_PATH_SHA256)

    def test_patch_applied(self):
        """The known upstream method is replaced."""
        patch_scorm_get_file_path()

        self.assertIs(ScormXBlock.get_file_path, get_file_path)

    @patch.object(scorm_patches, "upstream_get_file_path_sha256", return_value="changed")
    def test_patch_skipped_when_upstream_differs(self, _sha256_mock):
        """A different upstream method is left alone and a warning is logged."""
        with self.assertLogs(scorm_patches.logger, level="WARNING"):
            patch_scorm_get_file_path()

        self.assertIs(ScormXBlock.get_file_path, self.original)

    def test_xblock_not_installed(self):
        """Nothing happens when openedx-scorm-xblock is not installed."""
        with patch.dict(sys.modules, {"openedxscorm.scormxblock": None}):
            patch_scorm_get_file_path()

        self.assertIs(ScormXBlock.get_file_path, self.original)
