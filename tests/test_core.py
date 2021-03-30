from pathlib import Path

import pytest

from dicomtrolley.core import DICOMStorageDir
from tests.factories import quick_dataset


@pytest.mark.parametrize(
    "dataset, expected_path",
    [
        (
            quick_dataset(
                StudyInstanceUID="A", SeriesInstanceUID="B", SOPInstanceUID="C"
            ),
            "/tmp/A/B/C",
        ),
        (
            quick_dataset(StudyInstanceUID="A", SeriesInstanceUID="B"),
            "/tmp/A/B/unknown",
        ),
        (quick_dataset(), "/tmp/unknown/unknown/unknown"),
    ],
)
def test_storage_dir(dataset, expected_path):
    storage = DICOMStorageDir("/tmp")
    assert storage.generate_path(dataset) == Path("/tmp") / expected_path
