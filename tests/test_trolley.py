from pathlib import Path
from unittest.mock import Mock

import pytest

from dicomtrolley.core import Series
from dicomtrolley.mint import MintQuery
from dicomtrolley.storage import FlatStorageDir
from dicomtrolley.trolley import Trolley
from tests.factories import (
    quick_dataset,
    quick_image_level_study,
)


@pytest.fixture
def a_trolley(a_mint, a_wado) -> Trolley:
    """Trolley instance that will not hit any server"""
    return Trolley(searcher=a_mint, downloader=a_wado, query_missing=False)


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
    a_trolley.downloader.get_dataset = Mock(
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
    a_trolley.downloader.datasets_async = Mock(
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


@pytest.fixture
def some_datasets():
    return [
        quick_dataset(
            StudyInstanceUID="st1",
            SeriesInstanceUID="se1",
            SOPInstanceUID="in1",
        ),
        quick_dataset(
            StudyInstanceUID="st2",
            SeriesInstanceUID="se2",
            SOPInstanceUID="in2",
        ),
        quick_dataset(
            SeriesInstanceUID="se3",  # missing StudyInstanceUID
            SOPInstanceUID="in3",
        ),
    ]


def test_trolley_download(
    a_trolley, tmpdir, a_mint_study_with_instances, some_datasets
):
    expected = (
        (Path(tmpdir) / "st1" / "se1" / "in1"),
        (Path(tmpdir) / "st2" / "se2" / "in2"),
        (Path(tmpdir) / "unknown" / "se3" / "in3"),
    )

    a_trolley.fetch_all_datasets = Mock(return_value=iter(some_datasets))
    for path in expected:
        assert not path.exists()

    a_trolley.download(objects=a_mint_study_with_instances, output_dir=tmpdir)

    for path in expected:
        assert path.exists()


def test_trolley_alternate_storage_download(
    tmpdir, a_mint_study_with_instances, some_datasets, a_mint, a_wado
):
    expected = (
        (Path(tmpdir) / "in1"),
        (Path(tmpdir) / "in2"),
        (Path(tmpdir) / "in3"),
    )
    trolley = Trolley(
        searcher=a_mint, downloader=a_wado, storage=FlatStorageDir(path=tmpdir)
    )
    trolley.fetch_all_datasets = Mock(return_value=iter(some_datasets))
    for path in expected:
        assert not path.exists()

    trolley.download(objects=a_mint_study_with_instances, output_dir=tmpdir)

    for path in expected:
        assert path.exists()


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
