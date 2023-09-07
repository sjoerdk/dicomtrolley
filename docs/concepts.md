# Concepts

Explains the building blocks dicomtrolley in more detail. For quick examples see [usage](usage.md)

## Trolley
Allows you to query for DICOM objects and download DICOM images. Contains a [Searcher](#searcher) and 
[Downloader](#downloader) instance:
```python
trolley = Trolley(searcher=Mint(a_session, "https://server/mint"),
                  downloader=WadoURI(a_session, "https://server/wado_uri"))
```

### Trolley search
You query for DICOM objects by calling [`Trolley.find_studies()`][dicomtrolley.trolley.Trolley.find_studies] with a 
[Query](#Query) instance. This will send back one or more [DICOMObjects](#dicomobject).
```python
studies = trolley.find_studies(Query(PatientName='B*'))
```
 
``` mermaid
sequenceDiagram
  autonumber
  User->>Trolley: find_studies(Query)
  Trolley->>DICOM server: send query  
  DICOM server->>Trolley: response
  Trolley->>User: DICOMObjects
```

### Trolley download
You download DICOM images by calling [`Trolley.download()`][dicomtrolley.trolley.Trolley.download] with one or more
[DICOMdownloadable](#dicomdownloadable) objects. This will write 
[pydicom Datasets](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.dataset.Dataset.html) to disk.

```python
trolley.download(StudyReference(study_uid='1.2'), '/tmp')
```

``` mermaid
sequenceDiagram
  autonumber
  User->>Trolley: download()
  Trolley->>DICOM server: request data
  DICOM server->>Trolley: response
  Trolley->>User: writes Dataset
```

### Trolley advantage
The [Searcher](#searcher) and [Downloader](#downloader) contained in a trolley can be used stand-alone. Using them 
together in a trolley has two advantages.

#### Integration
The first advantage is that search and download are integrated. Missing information for a download is queried for 
automatically. This means you can do this one-line download of a study `111` for example:
```python
trolley = Trolley(downloader=WadoURI(requests.session(), "https://server/wado_uri"),
                  searcher=Mint(requests.session(), "https://server/mint"))

trolley.download(StudyReference(study_uid='111'), '/tmp')
```
Most downloaders, including [WadoURI][dicomtrolleywado_uri], must download each slice individually. A download command 
therefore should include a series and instance UIDs for each slice in study. Trolley takes care of that automatically.
This is how the download command above is handled in trolley:
``` mermaid
sequenceDiagram
  autonumber
  User->>Trolley: download(study)
  Trolley->>Downloader: get datasets (study ID)  
  Downloader->>Trolley: Exception! I need instance IDs  
  Trolley->>Searcher: find instance IDs (study ID)  
  Searcher->>Trolley: instance IDs
  Trolley->>Downloader: get datasets (instance IDs)
  Downloader->>DICOM server: request data 
  DICOM server->>Downloader: response
  Downloader->>Trolley: Datasets
  Trolley->>User: writes Datasets
```
Trolley will catch exceptions and query for missing information. Query results are cached to avoid unneeded queries.

#### Interchangeable backends
The second advantage is that search and download backends can be switched around with minimal effort:

```python

# Two trollies with different backends
trolley = Trolley(searcher=DICOMQR("host","123","aet","aec"),
                  downloader=WadoURI(requests.session(), 
                                     "https://server/wado"))

# Switch to a different searcher. Trolley interface will not change
trolley.searcher = QidoRS(session=requests.session(), url="http://server/qido")
```

## Query
An information request to a DICOM server is done using a [`Query`][dicomtrolley.core.Query] object. For example
```python
studies = trolley.find_studies(
    Query(PatientName='Bak*',                
          min_study_date=datetime(year=2015, month=3, day=1),
          max_study_date=datetime(year=2020, month=3, day=1),
          include_fields=['PatientBirthDate', 'SOPClassesInStudy'],
          query_level="INSTANCE"))
```
!!! note
    String parameters (like `PatientName='Bak*'`) can include asterisk wildcards. The implementation of this is up to
    the DICOM server you are talking to, however. Dicomtrolley will pass the wildcard the server as-is and not transform 
    it in any way.

### Query parameters
The following parameters can be set for a [`Query`][dicomtrolley.core.Query]:
$pydantic: dicomtrolley.core.Query

Most of these parameters have string values, possibly containing a `*` wildcard that will be matched as part of the
query. More information on non-string parameters below: 

#### query_level
Depth of the search. One of [dicomtrolley.core.QueryLevels][]. Study, Series or Instance. Setting to 
instance will yield information on each slice in a series and make the query much slower.

#### include_fields
A list of valid DICOM field names to include in the query result. Examples of fields can be found in [dicomtrolley.fields][].
The fields that can be included depend on query level. For instance, asking for an instance-level field like `InstanceNumber`
makes no sense for a study-level query.

!!! note
    Fields returned from a query are determined by the specific DICOM server you are talking to. Many servers 
    will return a common subset of fields even without explicit 'include_fields' values. The DICOM server manual should
    describe which fields can be returned for which query level.


### Query subtypes
The base [`Query`][dicomtrolley.core.Query] object is acceptable to all [`Searchers`](concepts.md#Query). Some Searchers
accept specialized query subtypes. For example [MINT](#MINT) searcher can take a specialized 
[`MintQuery`][dicomtrolley.mint.MintQuery], which  allows an additional `limit`
parameter:
```python
session = requests.Session()
trolley = Trolley(searcher=Mint(session, "https://server/mint"),
                  downloader=WadoURI(session, "https://server/wado"))
trolley.find_studies(MintQuery(PatientID='1234', limit=5))
```
See [Searcher](#searcher) for all query subtypes

## DICOMObject
DICOM distinguishes four hierarchical levels of organisation for images. 
Patient, Study, Series or Instance: 

``` mermaid
graph LR
  A[Patient] --> B[Study];
  A --> C[Study];
  B --> E[Series];
  B --> F[Series];
  E --> H[Instance];
  E --> I[Instance];
```

A patient has one or more studies. A study contains one or more Series. Each series contains one or more instances.
As a first approximation, a study contains all data of a single scanning session, a series contains all data for a
single pass through a scanner, and an instance represents a single image or slice.

DICOM objects are represented by the [dicomtrolley.core.DICOMObject][] class. Trolley queries return 
[dicomtrolley.core.Study][] instances which are DICOMObjects. A study can contain series, and instances:
```python
studies = trolley.find_studies(Query(PatientName='B*',
                                     query_level=QueryLevels.INSTANCE))

studies                             # all studies
studies[0]                          # a single study
studies[0].series[0]                # a single series
studies[0].series[0].instances[:3]  # first 3 instances
```
!!! note
    dicomtrolley models up to the `Study` object and does not model the `Patient` object directly

## DICOMDownloadable
A reference to image data that can be downloaded by a trolley instance. 
There are two families of classes that implement [DICOMDownloadable][dicomtrolley.core.DICOMDownloadable]:

Firstly, You can download any [DICOM object](#dicomobject):
```python
studies = trolley.find_studies(Query(PatientName='B*',
                                    query_level=QueryLevels.INSTANCE))

trolley.download(studies, "/tmp")                             # all studies
trolley.download(studies[0], "/tmp")                          # a single study
trolley.download(studies[0].series[0], "/tmp")                # a single series
trolley.download(studies[0].series[0].instances[:3], "/tmp")  # first 3 instances
```
    
Secondly, a [dicomtrolley.core.DICOMObjectReference][] can be used without requiring a query first:
```python
trolley.download(StudyReference(study_uid="1.1"), "/tmp")
trolley.download(SeriesReference(study_uid="1.1", 
                                 series_uid='2.2'), "/tmp")
trolley.download(InstanceReference(study_uid="1.1", 
                                   series_uid='2.2', 
                                   instance_uid='3.3'), "/tmp")
```
  

## Searcher
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


## Downloader
Something that can download DICOM images. Dicomtrolley includes the following [Downloader][dicomtrolley.core.Downloader] 
classes:

### WADO-URI
```python
downloader = WadoURI(requests.session(), "https://server/wado")
```
See [DICOM part18 chapter 9](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/chapter_9.html). 
API reference: [dicomtrolleywado_uri][]

### RAD69
```python
searcher = Rad69(session=requests.session(), url="https://server/rad69")
```

Based on [this document](https://gazelle.ihe.net/content/rad-69-retrieve-imaging-document-set). 
API reference: [dicomtrolleyrad69][]

### WADO-RS
```python
searcher = WadoRS(session=requests.session(), url="https://server/wadors")
```

[WADO-RS description](https://www.dicomstandard.org/using/dicomweb/retrieve-wado-rs-and-wado-uri/). 
API reference: [dicomtrolleywado_rs][]