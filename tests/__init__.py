"""Test utilities; use normal inherited permissions for temporary folders."""

from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4


@contextmanager
def temporary_directory():
    # Windows managed sandboxes can deny the private ACL set by mkdtemp.
    # Normal mkdir permissions keep disposable test output in the workspace.
    folder = Path(__file__).resolve().parent.parent / ".test-tmp" / uuid4().hex
    folder.mkdir(parents=True)
    try:
        yield folder
    finally:
        shutil.rmtree(folder)
