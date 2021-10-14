from pathlib import Path
from unittest.mock import Mock

import pytest

from dicomtrolley.core import Series
from dicomtrolley.mint import MintQuery
from dicomtrolley.trolley import DICOMStorageDir, Trolley
from tests.factories import (
    quick_dataset,
    quick_image_level_study,
)


@pytest.fixture
def a_trolley(a_mint, a_wado) -> Trolley:
    """Trolley instance that will not hit any server"""
    return Trolley(searcher=a_mint, wado=a_wado, query_missing=False)


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


def test_trolley_find(a_trolley, some_mint_studies):
    a_trolley.searcher.find_studies = Mock(return_value=some_mint_studies)
    assert a_trolley.find_studies(query=MintQuery()) == some_mint_studies


def test_trolley_download_study(a_trolley, some_mint_studies, tmpdir):
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
    a_trolley.download(some_mint_studies, output_dir=tmpdir)
    assert expected_path.exists()


def test_trolley_get_dataset(a_trolley, some_mint_studies, tmpdir):
    a_trolley.searcher.find_studies = Mock(return_value=some_mint_studies)
    a_trolley.wado.get_dataset = Mock(
        return_value=quick_dataset(
            StudyInstanceUID="foo",
            SeriesInstanceUID="baz",
            SOPInstanceUID="bimini",
        )
    )

    datasets = list(a_trolley.fetch_all_datasets(some_mint_studies))
    assert len(datasets) == 14
    assert datasets[0].SOPInstanceUID == "bimini"


def test_trolley_get_dataset_async(a_trolley, some_mint_studies):
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

    datasets = list(a_trolley.fetch_all_datasets_async(some_mint_studies))
    assert len(datasets) == 3
    assert datasets[0].SOPInstanceUID == "bimini"


def test_trolley_download(
    a_trolley, tmpdir, a_mint_study_with_instances, monkeypatch
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
    a_trolley.download(a_mint_study_with_instances, tmpdir)
    assert storage.save.called


def test_trolley_ensure_instances(a_trolley, some_studies):
    """When downloading a study object that has been retrieved at study or series
    querylevel, information about instanceqs, required for download, is missing.
    This should be queried separately by qTrolley on download.
    """
    # searching for more info will return mock study 'Study2'
    a_trolley.searcher.find_studies = Mock(
        return_value=[quick_image_level_study("Study2")]
    )

    enriched = a_trolley.ensure_instances(some_studies)
    assert not some_studies[1].series  # there were none
    assert enriched[1].series  # now they have been added


def test_trolley_ensure_instances_series(
    a_trolley, an_image_level_study, an_image_level_series
):
    """If a series is passed, due to querying constraints, the whole study has to
    be queried. In the return value however we want to have the same series, not a
    study
    """
    # searching for more info will return mock study
    a_trolley.searcher.find_studies = Mock(
        return_value=[quick_image_level_study("Study1")]
    )

    # we query for a single series without instances
    series = an_image_level_series
    series.instances = ()

    enriched = a_trolley.ensure_instances([series])[0]
    assert isinstance(enriched, Series)
    assert isinstance(series, Series)
    assert enriched.instances
    assert not series.instances


def test_trolley_ensure_instances_query(
    a_trolley,
    an_image_level_study,
    an_image_level_series,
    another_image_level_series,
):
    """When ensuring instances for a series, the entire study is renewed. Make sure
    no unneeded queries are done if two series from the same study are ensured
    """
    # searching for more info will return mock study
    a_trolley.searcher.find_studies = Mock(return_value=an_image_level_study)

    series1 = an_image_level_series
    series1.instances = ()
    series2 = another_image_level_series
    series2.instances = ()

    assert not a_trolley.searcher.find_studies.called
    _ = a_trolley.ensure_instances([series1, series2])
    # both series are from Study1. The study-level query for series1 should also yield
    # the results for series2. Therefore there should only be one call made, not two
    assert a_trolley.searcher.find_studies.call_count == 1
