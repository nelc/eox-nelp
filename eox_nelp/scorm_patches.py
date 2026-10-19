"""
Patches for openedx-scorm-xblock.

openedx-scorm-xblock 19.0.5 starts `ScormXBlock.get_file_path` with
`if not self.storage.exists(root): return None`. `root` is a folder, and on
Google Cloud Storage a folder is not an object, so `exists()` is always False.
Every Studio upload then fails with
"Invalid package: could not find 'imsmanifest.xml' file".

The patch drops that check and keeps the try/except around `listdir`, which
already handles a missing folder. It is applied only while the upstream method
is the exact 19.0.5 source, so a new upstream version is never overwritten.
Remove this module once upstream ships the fix.
"""
import hashlib
import inspect
import logging
import os

logger = logging.getLogger(__name__)

# sha256 of inspect.getsource(ScormXBlock.get_file_path) in openedx-scorm-xblock 19.0.5.
UPSTREAM_GET_FILE_PATH_SHA256 = "1bb0e955109c2d0b9be2d8e366dd26f5c74f72c790992fb9a90f8c6f58cd85e6"


def get_file_path(self, filename, root):
    """
    Same as `find_file_path`, but don't raise error on file not found.
    """
    try:
        subfolders, files = self.storage.listdir(root)
    except (FileNotFoundError, OSError):
        return None
    for f in files:
        if f == filename:
            return os.path.join(root, filename)
    for subfolder in subfolders:
        path = self.get_file_path(filename, os.path.join(root, subfolder))
        if path is not None:
            return path
    return None


def upstream_get_file_path_sha256(scorm_xblock_class):
    """Return the sha256 of the installed `get_file_path` source."""
    source = inspect.getsource(scorm_xblock_class.get_file_path)
    return hashlib.sha256(source.encode()).hexdigest()


def patch_scorm_get_file_path():
    """
    Replace `ScormXBlock.get_file_path` with the version above when the
    installed upstream method is the known broken one.
    """
    try:
        from openedxscorm.scormxblock import ScormXBlock  # pylint: disable=import-outside-toplevel
    except ImportError:
        return

    if upstream_get_file_path_sha256(ScormXBlock) != UPSTREAM_GET_FILE_PATH_SHA256:
        logger.warning(
            "ScormXBlock.get_file_path differs from openedx-scorm-xblock 19.0.5; "
            "eox-nelp patch not applied. Check whether it is still needed."
        )
        return

    ScormXBlock.get_file_path = get_file_path
