import json
from io import BytesIO
from pathlib import Path

import pytest
from pydicom.dataset import Dataset

from dicomtrolley.storage import FlatStorageDir, StorageDir, make_writable
from tests.factories import quick_dataset
from tests.mock_responses import WADO_RESPONSE_METADATA_INSTANCE


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


def test_metadata_result_file_writing():
    """Parsed results from WADO-RS /metadata calls turn out to sometimes have illegal
    elements that cause errors when writing to disk. Check whether this can be
    handled correctly.
    """
    ds = Dataset.from_json(json.loads(WADO_RESPONSE_METADATA_INSTANCE.text)[0])
    file = BytesIO()
    with pytest.raises(ValueError):
        ds.save_as(file)

    ds = make_writable(ds)
    ds.save_as(file)
