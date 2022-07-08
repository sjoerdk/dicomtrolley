from pathlib import Path

import pytest

from dicomtrolley.storage import FlatStorageDir, StorageDir
from tests.factories import quick_dataset


@pytest.mark.parametrize(
    "dataset, expected_path",
    [
        (
            quick_dataset(
                StudyInstanceUID="1", SeriesInstanceUID="2", SOPInstanceUID="3"
            ),
            "1/2/3",
        ),
        (
            quick_dataset(StudyInstanceUID="1", SeriesInstanceUID="2"),
            "1/2/unknown",
        ),
        (quick_dataset(), "unknown/unknown/unknown"),
    ],
)
def test_storage_dir_generate_path(dataset, expected_path):
    storage = StorageDir("/tmp")
    assert storage.generate_path(dataset) == Path(expected_path)


def test_storage_dir_write(tmpdir):
    """Make sure writing to disk works. Seems slight overkill. But coverage."""
    expected_path = Path(str(tmpdir)) / "unknown/unknown/unknown"
    assert not expected_path.exists()
    StorageDir(str(tmpdir)).save(quick_dataset())
    assert expected_path.exists()
    assert "tmp" in str(StorageDir("/tmp"))


def test_flat_storage_dir_write(tmpdir):
    """Make sure writing to disk works. Seems slight overkill. But coverage."""
    expected_path = Path(str(tmpdir)) / "unknown"
    assert not expected_path.exists()
    FlatStorageDir(str(tmpdir)).save(quick_dataset())
    assert expected_path.exists()
