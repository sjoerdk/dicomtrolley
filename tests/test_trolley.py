from pathlib import Path
from unittest.mock import Mock

import pytest

from dicomtrolley.exceptions import DICOMTrolleyError
from dicomtrolley.mint import MintQuery
from dicomtrolley.storage import FlatStorageDir
from dicomtrolley.trolley import (
    Trolley,
)

from tests.conftest import create_mint_study
from tests.factories import (
    StudyReferenceFactory,
    quick_dataset,
)


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
    a_trolley.searcher.find_study_by_id = Mock(
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


def test_trolley_get_dataset_async(a_mint, a_wado, some_mint_studies):
    a_wado.use_async = True
    a_trolley = Trolley(searcher=a_mint, downloader=a_wado)

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

    datasets = list(a_trolley.fetch_all_datasets(some_mint_studies))
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


def test_trolley_encapsulation_error(a_trolley):
    """Recreates issue #45. Uncaught ValueError during download"""

    # download will yield a dataset that recreates issue 45 when calling save_as
    the_error = ValueError(
        "(7FE0,0010) Pixel Data has an undefined length "
        "indicating that it's compressed, but the data isn't "
        "encapsulated as required. See "
        "pydicom.encaps.encapsulate() for more information"
    )

    a_dataset = quick_dataset(PatientID="Corrupt_Dataset")
    a_dataset.save_as = Mock(side_effect=the_error)
    a_trolley.fetch_all_datasets = Mock(return_value=iter([a_dataset]))

    # this should be caught an raised as a TrolleyError
    with pytest.raises(DICOMTrolleyError):
        a_trolley.download(StudyReferenceFactory(), output_dir="/tmp")
