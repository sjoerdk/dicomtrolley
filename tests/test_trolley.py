from pathlib import Path
from unittest.mock import Mock

import pytest

from dicomtrolley.mint import MintQuery
from dicomtrolley.trolley import DICOMStorageDir, Trolley
from tests.factories import quick_dataset


@pytest.fixture
def a_trolley(a_mint, a_wado) -> Trolley:
    """Trolley instance that will not hit any server"""
    return Trolley(searcher=a_mint, wado=a_wado)


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
    assert "tmp" in str(DICOMStorageDir("/tmp"))


def test_trolley_find(a_trolley, some_studies):
    a_trolley.searcher.find_studies = Mock(return_value=some_studies)
    assert a_trolley.find_studies(query=MintQuery()) == some_studies


def test_trolley_download_study(a_trolley, some_studies, tmpdir):
    a_trolley.fetch_all_datasets = Mock(
        return_value=iter(
            [
                quick_dataset(
                    StudyInstanceUID="foo",
                    SeriesInstanceUID="baz",
                    SOPInstanceUID="bimini",
                )
            ]
        )
    )
    expected_path = Path(str(tmpdir)) / "foo/baz/bimini"
    assert not expected_path.exists()
    a_trolley.download(some_studies, output_dir=tmpdir)
    assert expected_path.exists()


def test_trolley_get_dataset(a_trolley, some_studies, tmpdir):
    a_trolley.searcher.find_studies = Mock(return_value=some_studies)
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


def test_trolley_get_dataset_async(a_trolley, some_studies):
    a_trolley.wado.datasets_async = Mock(
        return_value=iter(
            [
                quick_dataset(
                    StudyInstanceUID="foo",
                    SeriesInstanceUID="baz",
                    SOPInstanceUID="bimini",
                )
            ]
            * 3
        )
    )

    datasets = list(a_trolley.fetch_all_datasets_async(some_studies))
    assert len(datasets) == 3
    assert datasets[0].SOPInstanceUID == "bimini"


def test_trolley_download(
    a_trolley, tmpdir, a_study_with_instances, monkeypatch
):
    a_trolley.fetch_all_datasets = Mock(
        return_value=iter(
            [
                quick_dataset(PatientName="pat1", StudyDescription="a study"),
                quick_dataset(PatientName="pat2", StudyDescription="a study2"),
            ]
        )
    )
    storage = Mock(spec=DICOMStorageDir)

    monkeypatch.setattr(
        "dicomtrolley.trolley.DICOMStorageDir", Mock(return_value=storage)
    )
    a_trolley.download(a_study_with_instances, tmpdir)
    assert storage.save.called
