import pytest

from dicomtrolley.core import (
    InstanceReference,
    SeriesReference,
    StudyReference,
)
from dicomtrolley.wado_rs import WadoRS


@pytest.mark.parametrize(
    "url,reference,result",
    [
        (
            "prot://test/",
            StudyReference(study_uid="1"),
            "prot://test/studies/1",
        ),
        (
            "prot://test/",
            SeriesReference(study_uid="1", series_uid="2"),
            "prot://test/studies/1/series/2",
        ),
        (
            "prot://test/",
            InstanceReference(study_uid="1", series_uid="2", instance_uid="3"),
            "prot://test/studies/1/series/2/instances/3",
        ),
        (
            "prot://test",
            StudyReference(study_uid="1"),
            "prot://test/studies/1",
        ),
    ],
)
def test_generate_uri(url, reference, result):
    a_wado = WadoRS(session=None, url=url)
    assert a_wado.wado_rs_instance_uri(reference) == result
