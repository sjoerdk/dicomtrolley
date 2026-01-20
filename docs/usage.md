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

For details on Query parameters see [`Query`](concepts.md#query)

## Finding series and instance details
To include series and instance level information as well, use the [`queryLevel`](concepts.md#query_level) parameter

```python
studies = trolley.find_studies(      # find studies series and instances
    Query(StudyInstanceUID='B*', 
          query_level=QueryLevels.INSTANCE))

a_series = studies[0].series[0]         # studies now contain series    
an_instance = a_series.instances[0]     # and series contain instances
```
Data sent back by the server is parsed in a DICOM object hierarchy. Each object stores its additional data in the 
`data` field. This field is a [pydicom.Dataset](
https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.dataset.Dataset.html) 
object and can be addressed as such:
```python
an_instance.data            # {pydicom.Dataset} instance
an_instance.data.Rows       # {int} 100
an_instance.data["Rows"]    # {DataElement} instance
```
!!! note
    The information sent back for each DICOM object level depends on the [query_level](concepts.md#query_level) and
    [include_fields](concepts.md#include_fields) parameters, as well as on the server type and configuration
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

## Choosing a searcher
Something that can search for DICOM studies. Dicomtrolley includes the following 
[Searcher][dicomtrolley.core.Searcher] classes:

### DICOM-QR
```python 
searcher = DICOMQR(host="hostname", port="123",aet="DICOMTROLLEY", aec="ANY-SCP")
```
DICOM query retrieve ([dicomtrolley.dicom_qr.DICOMQR][]). This method does not use a http connection but 
uses the DICOM protocol directly. 

In addition to the standard [`Query`][dicomtrolley.core.Query], DICOMQR instances accept [dicomtrolley.dicom_qr.DICOMQuery][] queries

### MINT
```python 
searcher = Mint(requests.session(), "http://server/mint")
```
See [dicomtrolley.mint.Mint][] 

In addition to the standard [`Query`][dicomtrolley.core.Query], Mint instances accept [dicomtrolley.mint.MintQuery][] queries

### QIDO-RS
```python 
searcher = QidoRS(session=session, url="http://server/qido")
```
See [dicomtrolley.qido_rs.QidoRS][]

In addition to the standard [`Query`][dicomtrolley.core.Query], QidoRS instances accept both
[dicomtrolley.qido_rs.RelationalQuery][] and [dicomtrolley.qido_rs.HierarchicalQuery][] instances


## Choosing a downloader
Something that can download DICOM images. Dicomtrolley includes the following [Downloader][dicomtrolley.core.Downloader] 
classes:

### WADO-URI
```python
downloader = WadoURI(requests.session(), "https://server/wado")
```
See [DICOM part18 chapter 9](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/chapter_9.html). 
API reference: [dicomtrolley.wado_uri][]

### RAD69
```python
searcher = Rad69(session=requests.session(), url="https://server/rad69")
```

Based on [this document](https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set). 
API reference: [dicomtrolley.rad69][]

### WADO-RS
```python
searcher = WadoRS(session=requests.session(), url="https://server/wadors")
```
[WADO-RS](https://www.dicomstandard.org/using/dicomweb/retrieve-wado-rs-and-wado-uri/)
to download full DICOM datasets
 
API reference: [dicomtrolley.wado_rs.WadoRS][]

### WADO-RS Metadata
```python
searcher = WadoRSMetadata(session=requests.session(), url="https://server/wadors")
```
[WADO-RS](https://www.dicomstandard.org/using/dicomweb/retrieve-wado-rs-and-wado-uri/)
 to download metadata-only. This means all DICOM elements except for PixelData.

API reference: [dicomtrolley.wado_rs.WadoRSMetaData][]


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
## Caching
You can add caching to any [`Searcher`](concepts.md#searcher) by wrapping it with
a [CachedSearcher][dicomtrolley.caching.CachedSearcher] instance:

```python
from dicomtrolley.caching import CachedSearcher, DICOMObjectCache

searcher = CachedSearcher(searcher=a_searcher, 
                          cache=DICOMObjectCache(expiry_seconds=300))

trolley = Trolley(searcher=searcher, downloader=a_downloader)
```

[CachedSearcher][dicomtrolley.caching.CachedSearcher] is a [Searcher][dicomtrolley.core.Searcher]
and can be used like any other. It will return cached results to any of its function
calls for up to `expiry_seconds` seconds.

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
# trolley.download() # will now skip series raising XDSMissingDocumentError
```

## Authentication
See [authentication](authentication.md)
