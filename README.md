# dicomtrolley

[![CI](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Retrieve medical images via WADO, MINT and DICOM-QR

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
# Create a logged-in http session
session = VitreaConnection(
    "https://server/login").log_in(user,password,realm)
                           
# Use this session to create a trolley using MINT and WADO
trolley = Trolley(searcher=Mint(session, "https://server/mint"),
                  wado=Wado(session, "https://server/wado"]))

# find some studies (using MINT)
studies = trolley.find_studies(MintQuery(patientName='B*'))  

# download the fist one (using WADO)
trolley.download(studies[0], output_dir='/tmp/trolley')
```

### Finding studies

```python
studies = trolley.find_studies(MintQuery(patientName='B*'))
```

Query parameters can be found in [mint.Query](dicomtrolley/mint.py#L122). Valid include fields (which information gets sent back) can be found in [fields.py](dicomtrolley/fields.py):

```python
studies = trolley.find_studies_mint(
    MintQuery(modalitiesInStudy='CT*', 
              patientSex="F", 
              minStudyDate=datetime(year=2015, month=3, day=1),
              maxStudyDate=datetime(year=2020, month=3, day=1),
              includeFields=['PatientBirthDate', 'SOPClassesInStudy']))
```

### Finding series and instance details
To include series and instance level information as well, use the `queryLevel` parameter

```python
studies = trolley.find_studies(  # find studies series and instances
    MintQuery(studyInstanceID='B*', 
              queryLevel=QueryLevels.INSTANCE)

a_series = studies.series[0]  # studies now contain series    
an_instance = a_series.instances[0]  # and series contain instances
```

### Downloading data
Any study, series or instance can be downloaded
```python
studies = trolley.find_studies(MintQuery(patientName='B*',
                                         queryLevel=QueryLevels.INSTANCE))

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
          queryLevel=QueryLevels.INSTANCE)

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
from dicomtrolley.wado import InstanceReference, Wado

instance = InstanceReference(
    series_instance_uid='1.2.1',
    study_instance_uid='1.2.2',
    sop_instance_iud='1.2.3')


wado = Wado(session, wado_url)
for ds in wado.datasets([instance]):
    ds.save_as(f'/tmp/{ds.SOPInstanceUID}.dcm')
```

### DICOM-QR
`Trolley` can use DICOM-QR instead of MINT as a search method. See [dicom_qr.DICOMQuery](dicomtrolley/dicom_qr.py#L30) for query details.
```python
dicom_qr = DICOMQR(host,port,aet,aec)
trolley = Trolley(searcher=dicom_qr, wado=wado)

# Finding is similar to MINT, but a DICOMQuery is used instead
trolley.find_studies(  
    query=DICOMQuery(PatientName="BAL*",   
                     minStudyDate=datetime(year=2015, month=3, day=1),
                     maxStudyDate=datetime(year=2015, month=4, day=1),
                     includeFields=["PatientBirthDate", "SOPClassesInStudy"],
                     QueryRetrieveLevel=QueryRetrieveLevels.STUDY)) 
```
## Examples
* [Search for studies in MINT](examples/search_for_studies_mint.py) 
* [Search for studies in DICOM-QR](examples/search_for_studies_dicom_qr.py)
* [Find and download studies](examples/go_shopping.py)
* [Using WADO only](examples/use_wado_only.py)

## Alternatives
* [dicomweb-client](https://github.com/MGHComputationalPathology/dicomweb-client) - Active library supporting QIDO-RS, WADO-RS and STOW-RS. 
* [pynetdicom](https://github.com/pydicom/pynetdicom) - dicomtrolley's DICOM-QR support is based on pynetdicom. Pynetdicom supports a broad range of DICOM networking interactions and can be used as a stand alone application.

## Caveats
Dicomtrolley has been developed for and tested on a Vitrea Connection 8.2.0.1 system. This claims to
be consistent with WADO and MINT 1.2 interfaces, but does not implement all parts of these standards. 

Certain query parameter values and restraints might be specific to Vitrea Connection 8.2.0.1. For example,
the exact list of DICOM elements that can be returned from a query might be different for different servers.
