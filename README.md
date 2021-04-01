# dicomtrolley

[![CI](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Retrieve medical images using DICOM WADO and MINT.
Requires python 3.7, 3.8 or 3.9
Represents images as `pydicom` Datasets.

![A trolley](docs/resources/trolley.png)

## Usage

### Basic example
```python
session = log_in_to(https://server/login)  # set up   
trolley = Trolley(mint=Mint(session, https://server/mint),
                  wado=Wado(session, https://server/wado]))
                  
studies = trolley.find_studies(
    Query(patientName='B*')  # find some studies

trolley.download_study(      # download a study by uid
    study_instance_uid=studies[0].uid,
    output_dir='/tmp/trolley')
```

### Finding studies

```python
studies = trolley.find_studies(       # simple find
    Query(patientName='B*')
```

Query parameters can be found in [mint.query.Query](dicomtrolley/query.py). Valid include fields (which information gets sent back) can be found in [include_fields.py](dicomtrolley/include_fields.py): 
```python
studies = trolley.find_studies(
    Query(modalitiesInStudy='CT*',
          patientSex="F",
          minStudyDate=datetime(year=2015, month=3, day=1),
          maxStudyDate=datetime(year=2020, month=3, day=1),                                                                         
          includeFields=['PatientBirthDate',
                         'SOPClassesInStudy']))
```

### Finding series and instance details
To include series and instance level information as well, use the `queryLevel` parameter 
```python
studies = trolley.find_studies(      # find studies series and instances
    Query(studyInstanceID='B*', 
          queryLevel=QueryLevels.INSTANCE)
 
a_series = studies.series[0]         # studies now contain series    
an_instance = a_series.instances[0]  # and series contain instances
```

### Downloading data
```python
trolley.download_study(              # simple download by uid
    study_instance_uid='123',  
    output_dir='/tmp/trolley')
```
More control over download   
```python
studies = trolley.find_studies(      # find study including instances
    Query(PatientID='1234',
          queryLevel=QueryLevels.INSTANCE)

instances = trolley.extract_instances(  
    studies.series[0])               # download only the first series 

for instance in instances:
    ds = trolley.get_dataset(instance)
    ds.save_as(
        f'/tmp/{ds.PatientID}')      # this is a pydicom dataset

```

## Caveats
Dicomtrolley has been developed for and tested on a Vitrea Connection 8.2.0.1 system. This claims to
be consistent with WADO and MINT 1.2 interfaces, but does not implement all parts of these standards. 

Certain query parameter values and restraints might be specific to Vitrea Connection 8.2.0.1. For example,
the exact list of DICOM elements that can be returned from a query might be different for different servers.