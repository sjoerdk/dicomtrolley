from pathlib import Path
from unittest.mock import Mock

import pytest

from dicomtrolley.core import SeriesReference
from dicomtrolley.mint import MintQuery
from dicomtrolley.storage import FlatStorageDir
from dicomtrolley.trolley import CachedSearcher, Trolley
from tests.conftest import create_mint_study, set_mock_response
from tests.factories import quick_dataset
from tests.mock_responses import (
    MINT_SEARCH_INSTANCE_LEVEL_ANY,
    MINT_SEARCH_INSTANCE_LEVEL_IDS,
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


def test_trolley_get_dataset(a_trolley, some_mint_studies):
    """Downloading two studies (some_mint_studies). First one has
    complete instance info, second one has not, so requires extra query before
    download
    """
    # Search will yield full info for the missing study
    a_trolley.searcher.find_full_study_by_id = Mock(
        return_value=create_mint_study(
            uid="1.2.340.114850.2.857.2.793263.2.125336546.1"
        )
    )

    # Download just returns a single mock dataset
    a_trolley.downloader.get_dataset = Mock(
        return_value=quick_dataset(
            StudyInstanceUID="foo",
            SeriesInstanceUID="baz",
            SOPInstanceUID="bimini",
        )
    )

    datasets = list(a_trolley.fetch_all_datasets(some_mint_studies))
    assert len(datasets) == 28
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


def test_cached_searcher(a_mint, requests_mock):
    # set a single-study response for any mint call
    set_mock_response(requests_mock, MINT_SEARCH_INSTANCE_LEVEL_ANY)

    # a reference to the two series contained in response
    series_reference_1 = SeriesReference(
        study_uid=MINT_SEARCH_INSTANCE_LEVEL_IDS["study_uid"],
        series_uid=MINT_SEARCH_INSTANCE_LEVEL_IDS["series_uids"][0],
    )

    # a reference to a series contained in response
    series_reference_2 = SeriesReference(
        study_uid=MINT_SEARCH_INSTANCE_LEVEL_IDS["study_uid"],
        series_uid=MINT_SEARCH_INSTANCE_LEVEL_IDS["series_uids"][1],
    )

    searcher = CachedSearcher(searcher=a_mint)

    assert requests_mock.request_history == []  # no requests have been made

    # now ask for a series that is not in cached searcher
    instances = searcher.retrieve_instance_references(series_reference_1)
    assert len(instances) == 1  # this series has only one instance
    assert len(requests_mock.request_history) == 1  # a request has been made

    # ask for the other series
    instances = searcher.retrieve_instance_references(series_reference_2)
    assert len(instances) == 13
    # No extra requests as the whole study was retrieved
    assert len(requests_mock.request_history) == 1
