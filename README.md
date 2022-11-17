# dicomtrolley

[![CI](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Retrieve medical images via WADO, MINT, RAD69 and DICOM-QR

* Requires python 3.7, 3.8 or 3.9
* Uses `pydicom` and `pynetdicom`. Images and query results are `pydicom.Dataset` instances
* Multi-threaded downloading using `requests-futures`

![A trolley](docs/resources/trolley.png)

## Installation
```
pip install dicomtrolley
``` 

## Usage

### Basic example

```python
# Create a http session
session = create_session("https://server/login",user,password,realm)
                           
# Use this session to create a trolley using MINT and WADO
trolley = Trolley(searcher=Mint(session, "https://server/mint"),
                  wado=Wado(session, "https://server/wado"))

# find some studies (using MINT)
studies = trolley.find_studies(Query(PatientName='B*'))  

# download the fist one (using WADO)
trolley.download(studies[0], output_dir='/tmp/trolley')
```

### Finding studies

```python
studies = trolley.find_studies(Query(PatientName='B*'))
```

Basic query parameters can be found in [core.Query](dicomtrolley/core.py#L274). Valid include fields (which information gets sent back) can be found in [fields.py](dicomtrolley/fields.py):

```python
studies = trolley.find_studies(
    Query(modalitiesInStudy='CT*', 
               patientSex="F", 
               min_study_date=datetime(year=2015, month=3, day=1),
               max_study_date=datetime(year=2020, month=3, day=1),
               include_fields=['PatientBirthDate', 'SOPClassesInStudy']))
```

### Finding series and instance details
To include series and instance level information as well, use the `queryLevel` parameter

```python
studies = trolley.find_studies(      # find studies series and instances
    Query(studyInstanceID='B*', 
          query_level=QueryLevels.INSTANCE))

a_series = studies.series[0]         # studies now contain series    
an_instance = a_series.instances[0]  # and series contain instances
```

### Downloading data
Any study, series or instance can be downloaded
```python
studies = trolley.find_studies(Query(PatientName='B*',
                                     query_level=QueryLevels.INSTANCE))

path = '/tmp/trolley'
trolley.download(studies, path)                             # all studies
trolley.download(studies[0]), path                          # a single study
trolley.download(studies[0].series[0], path)                # a single series
trolley.download(studies[0].series[0].instances[:3], path)  # first 3 instances
```
More control over download: obtain `pydicom.Dataset` instances directly 

```python
studies = trolley.find_studies(              # find study including instances
    Query(PatientID='1234', 
          query_level=QueryLevels.INSTANCE)

for ds in trolley.get_dataset(studies):      # obtain Dataset for each instance
    ds.save_as(f'/tmp/{ds.SOPInstanceUID}.dcm')
```

Multi-threaded downloading

```python
trolley.download(studies, path, 
                 use_async=True,  # enable multi-threaded downloading 
                 max_workers=4)   # optionally set number of concurrent workers
                                  # defaults to None which lets python decide
```

Using WADO only, without search

```python
from dicomtrolley.wado import Wado
from dicomtrolley.core import InstanceReference

instance = InstanceReference(series_instance_uid='1.2.1', study_instance_uid='1.2.2', sop_instance_uid='1.2.3')

wado = Wado(session, wado_url)
for ds in wado.datasets([instance]):
  ds.save_as(f'/tmp/{ds.SOPInstanceUID}.dcm')
```

### DICOM-QR
`Trolley` can use DICOM-QR instead of MINT as a search method. See [dicom_qr.DICOMQuery](dicomtrolley/dicom_qr.py#L30) for query details.
```python
dicom_qr = DICOMQR(host,port,aet,aec)
trolley = Trolley(searcher=dicom_qr, downloader=wado)

# Finding is similar to MINT, but a DICOMQuery is used instead
trolley.find_studies(  
    query=DICOMQuery(PatientName="BAL*",   
                     min_study_date=datetime(year=2015, month=3, day=1),
                     max_study_date=datetime(year=2015, month=4, day=1),
                     include_fields=["PatientBirthDate", "SOPClassesInStudy"],
                     query_level=QueryRetrieveLevels.STUDY)) 
```

### RAD69
The [RAD69](https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set) protocol is an alternative to wado for downloading DICOM images.
```python
dicom_qr = DICOMQR(host,port,aet,aec)
trolley = Trolley(searcher=dicom_qr, 
                  downloader=Rad69(session=session,
                                   url="https://server/rad69"))

studies = trolley.find_studies(Query(PatientName="AB*"))
trolley.download(studies[0], path)  # rad69 download works exactly like wado 
trolley.download(studies[1], path,  
                 use_async=True)    # multi-threaded download is supported

```
#### Ignoring errors
By default, any error returned by a rad69 server will raise an exception. To ignore certain errors  and keep trying to download, pass the
exception class to the Rad69 constructor:

```python

from dicomtrolley.rad69 import XDSMissingDocumentError
trolley = Trolley(searcher=dicom_qr, 
                  downloader=Rad69(session=session,
                                   url="https://server/rad69",
                                   errors_to_ignore = [XDSMissingDocumentError]))

study = trolley.find_study(Query(PatientName="AB*"))
trolley.download(study, path) # will skip series raising XDSMissingDocumentError
```


### Download format
By default, trolley writes downloads to disk as `StudyID/SeriesID/InstanceID`, sorting files into separate
study and series folders. You can change this by passing a `DICOMDiskStorage` instance to trolley:

```python
from dicomtrolley.storage import FlatStorageDir

#  Creates no sub-folders, just write to single flat file
storage = FlatStorageDir(path=tmpdir)
trolley = Trolley(searcher=mint, downloader=wado,
                  storage=storage)
```

You can create your own custom storage method by subclassing 
[storage.DICOMDiskStorage](dicomtrolley/storage.py#L8):

```python
from dicomtrolley.storage import DICOMDiskStorage

class MyStorage(DICOMDiskStorage):
  """Saves to unique uid filename"""
  def save(self, dataset, path):    
    dataset.save_as(Path(path) / uuid.uuid4())

trolley = Trolley(searcher=mint, downloader=wado,
                  storage=MyStorage())
```
### Logging
Dicomtrolley uses the standard [logging](https://docs.python.org/3/howto/logging.html) module. The root logger is called "trolley". To print log messages, add the following to your code

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# get the root logger to set specific properties
root_logger = logging.getLogger('trolley')
```

### DICOM Query types
For most DICOM queries you can use a [Query](dicomtrolley/core.py#L322) instance:

```python
from dicomtrolley.core import QueryLevels 
trolley.find_studies(Query(PatientID='1234', 
                           query_level=QueryLevels.INSTANCE)
```

If you want to have more control over backend-specific options you can use a backend-specific
query like [MintQuery](dicomtrolley/mint.py#L140) or [DICOMQuery](dicomtrolley/dicom_qr.py#L38). The query then needs to match the backend:

```python
trolley = Trolley(searcher=Mint(session, "https://server/mint"),
                  wado=Wado(session, "https://server/wado"]))
trolley.find_studies(MintQuery(PatientID='1234', limit=5))
```

## Examples
* [Search for studies in MINT](examples/search_for_studies_mint.py) 
* [Search for studies in DICOM-QR](examples/search_for_studies_dicom_qr.py)
* [Find and download studies](examples/go_shopping.py)
* [Using WADO only](examples/use_wado_only.py)
* [Download studies with rad69](examples/go_shopping_rad69.py)

## Alternatives
* [dicomweb-client](https://github.com/MGHComputationalPathology/dicomweb-client) - Active library supporting QIDO-RS, WADO-RS and STOW-RS. 
* [pynetdicom](https://github.com/pydicom/pynetdicom) - dicomtrolley's DICOM-QR support is based on pynetdicom. Pynetdicom supports a broad range of DICOM networking interactions and can be used as a stand alone application.

## Caveats
Dicomtrolley has been developed for and tested on a Vitrea Connection 8.2.0.1 system. This claims to
be consistent with WADO and MINT 1.2 interfaces, but does not implement all parts of these standards. 

Certain query parameter values and restraints might be specific to Vitrea Connection 8.2.0.1. For example,
the exact list of DICOM elements that can be returned from a query might be different for different servers.


# Contributing
You can contribute in different ways

## Report bugs
Report bugs at https://github.com/sjoerdk/dicomtrolley/issues.

## Contribute code
### Get the code
Fork this repo, create a feature branch

### Set up environment
dicomtrolley uses [poetry](https://python-poetry.org/docs/) for dependency and package management 
* Install poetry (see [poetry docs](https://python-poetry.org/docs/#installation))
* Create a virtual env. Go to the folder where cloned dicomtrolley and use 
  ```  
  poetry install 
  ``` 
* Install [pre-commit](https://pre-commit.com) hooks.
  ```
  pre-commit install
  ```
  
### Add your code 
Make your code contributions. Make sure document and add tests for new features.
To automatically publish to pypi, increment the version number and push to master. See below. 

### Lint your code
* Run all tests
* Run [pre-commit](https://pre-commit.com):
  ```
  pre-commit run
  ```
### Publish
Create a pull request

### Incrementing the version number
A merged pull request will only be published to pypi if it has a new version number. 
To bump dicomtrolley's version, do the following.
* dicomtrolley uses [semantic versioning](https://semver.org/) Check whether your addition is a PATCH, MINOR or MAJOR version.
* Manually increment the version number:
  * `pyproject.toml` -> `version = "0.1.2"`
  
* Add a brief description of your updates new version to `HISTORY.md`
