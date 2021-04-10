from pydicom.dataset import Dataset

from dicomtrolley.core import Instance, Series, Study


def test_objects():
    study = Study(uid="1", data=Dataset(), series=[])
    series = Series(uid="2", data=Dataset(), parent=study, instances=[])
    instance1 = Instance(uid="3", data=Dataset(), parent=series)
    instance2 = Instance(uid="4", data=Dataset(), parent=series)

    study.series = [series]
    series.instances = [instance1, instance2]

    assert len(study.all_instances()) == 2
    assert len(series.all_instances()) == 2
    assert len(instance1.all_instances()) == 1

    assert str(study) == "Study 1"
