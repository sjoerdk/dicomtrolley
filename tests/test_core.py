from pathlib import Path
from unittest.mock import Mock

import pytest

from dicomtrolley.core import DICOMStorageDir, Trolley
from dicomtrolley.query import Query
from tests.factories import quick_dataset


@pytest.fixture
def a_trolley(a_mint, a_wado) -> Trolley:
    """Trolley instance that will not hit any server"""
    return Trolley(mint=a_mint, wado=a_wado)


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
def test_storage_dir_generate_path(dataset, expected_path):
    storage = DICOMStorageDir("/tmp")
    assert storage.generate_path(dataset) == Path("/tmp") / expected_path


def test_storage_dir_write(tmpdir):
    """Make sure writing to disk works. Seems slight overkill. But coverage."""
    expected_path = Path(str(tmpdir)) / "unknown/unknown/unknown"
    assert not expected_path.exists()
    DICOMStorageDir(str(tmpdir)).save(quick_dataset())
    assert expected_path.exists()


def test_trolley_find(a_trolley, some_studies):
    a_trolley.mint.find_studies = Mock(return_value=some_studies)
    assert a_trolley.find_studies(query=Query()) == some_studies


def test_trolley_download_study(a_trolley, some_studies, tmpdir):
    a_trolley.mint.find_studies = Mock(return_value=some_studies[:1])
    a_trolley.wado.get_dataset = Mock(
        return_value=quick_dataset(
            StudyInstanceUID="foo",
            SeriesInstanceUID="baz",
            SOPInstanceUID="bimini",
        )
    )

    expected_path = Path(str(tmpdir)) / "foo/baz/bimini"
    assert not expected_path.exists()
    a_trolley.download_study(study_instance_uid="1", output_dir=tmpdir)
    assert expected_path.exists()


def test_trolley_get_dataset(a_trolley, some_studies, tmpdir):
    a_trolley.mint.find_studies = Mock(return_value=some_studies)
    a_trolley.wado.get_dataset = Mock(
        return_value=quick_dataset(
            StudyInstanceUID="foo",
            SeriesInstanceUID="baz",
            SOPInstanceUID="bimini",
        )
    )

    datasets = list(a_trolley.fetch_all_datasets(some_studies))
    assert len(datasets) == 28
    assert datasets[0].SOPInstanceUID == "bimini"
