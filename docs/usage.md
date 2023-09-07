# Usage

Shows how to do things in code. For information on the structure see [concepts](concepts.md)

## Basic example
```python
# Create a http session
session = requests.Session()

# Use this session to create a trolley using MINT and WADO
trolley = Trolley(searcher=Mint(session, "https://server/mint"),
                  downloader=WadoURI(session, "https://server/wado_uri"))

# find some studies
studies = trolley.find_studies(Query(PatientName='B*'))

# download the first one
trolley.download(studies[0], output_dir='/tmp/trolley')
```

## Finding studies
```python
# Find all studies for patients starting with 'B'
studies = trolley.find_studies(Query(PatientName='B*'))
```

```python
# Find CT studies from the first three days of March 2020
# Include patient birth date and referring physician in results
studies = trolley.find_studies(
    Query(ModalitiesInStudy='CT*',                
          min_study_date=datetime(year=2020, month=3, day=1),
          max_study_date=datetime(year=2020, month=3, day=3),
          include_fields=['PatientBirthDate', 'ReferringPhysicianName']))
```

For details on Query parameters see [`Query`](concepts.md#Query)

## Finding series and instance details
To include series and instance level information as well, use the [`queryLevel`](concepts.md#query_level) parameter

```python
studies = trolley.find_studies(      # find studies series and instances
    Query(StudyInstanceUID='B*', 
          query_level=QueryLevels.INSTANCE))

a_series = studies[0].series[0]         # studies now contain series    
an_instance = a_series.instances[0]  # and series contain instances
```
## Downloading images
Any study, series or instance can be downloaded (see [DICOMObject](concepts.md#dicomobject)):
```python
studies = trolley.find_studies(Query(PatientName='B*',
                                     query_level=QueryLevels.INSTANCE))

trolley.download(studies, '/tmp')                             # all studies
trolley.download(studies[0], '/tmp')                          # a single study
trolley.download(studies[0].series[0], '/tmp')                # a single series
trolley.download(studies[0].series[0].instances[:3], '/tmp')  # first 3 instances
```

You can also download [DICOM object references][dicomtrolley.core.DICOMObjectReference] based on id directly:
```python
trolley.download(StudyReference(study_uid="1.1"), "/tmp")
trolley.download(SeriesReference(study_uid="1.1", 
                                 series_uid='2.2'), "/tmp")
trolley.download(InstanceReference(study_uid="1.1", 
                                   series_uid='2.2', 
                                   instance_uid='3.3'), "/tmp")
```

## Downloading datasets
More control over download: obtain `pydicom.Dataset` instances directly 

```python
studies = trolley.find_studies(                 # find study including instances
    Query(PatientID='1234', 
          query_level=QueryLevels.INSTANCE))

for ds in trolley.fetch_all_datasets(studies):  # obtain Dataset for each instance
    ds.save_as(f'/tmp/{ds.SOPInstanceUID}.dcm')
```

## Protocols
Have a look at the [downloader](concepts.md#downloader) and [searcher](concepts.md#searcher) implementations.  


## Download format
By default, trolley writes downloads to disk as `StudyID/SeriesID/InstanceID`, sorting files into separate
study and series folders. You can change this by passing a [DICOMDiskStorage][dicomtrolley.storage.DICOMDiskStorage] 
instance to trolley:

```python
from dicomtrolley.storage import FlatStorageDir

#  Creates no sub-folders, just write to single flat file
storage = FlatStorageDir(path='/tmp')

trolley = Trolley(searcher=a_searcher, downloader=a_downloader, storage=storage)
```

You can create your own custom storage method by subclassing 
[DICOMDiskStorage][dicomtrolley.storage.DICOMDiskStorage]:

```python
from dicomtrolley.storage import DICOMDiskStorage

class MyStorage(DICOMDiskStorage):
  """Saves to unique uid filename"""
  def save(self, dataset, path):    
    dataset.save_as(Path(path) / uuid.uuid4())

trolley = Trolley(searcher=a_searcher, downloader=a_downloader, storage=MyStorage())

```

## Logging
Dicomtrolley uses the standard [logging](https://docs.python.org/3/library/logging.html) module. The root logger is 
called `trolley`. To print log messages, add the following to your code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# get the root logger to set specific properties
root_logger = logging.getLogger('trolley')
```


## Ignoring RAD69 errors
By default, any error returned by a rad69 server will raise an exception, halting any further download. To ignore 
certain errors and continue the download, pass the exception class to the Rad69 constructor:

```python
from dicomtrolley.rad69 import XDSMissingDocumentError
trolley = Trolley(searcher=a_searcher, 
                  downloader=Rad69(session=requests.session(),
                                   url="https://server/rad69",
                                   errors_to_ignore = [XDSMissingDocumentError]))

study = trolley.find_study(Query(PatientName="AB*"))
trolley.download(study, '/tmp') # will skip series raising XDSMissingDocumentError
```

## Authentication
See [authentication](authentication.md)
