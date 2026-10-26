import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def library(tmp_path, monkeypatch):
    from tunimix.library import Library
    lib = Library(tmp_path / "lib")
    lib.import_seeds()
    return lib


@pytest.fixture
def seeds(library):
    return library.all()
