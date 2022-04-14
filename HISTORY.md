# History

## v1.1.0 (2022-04-14)
* Improves rad69 downloading. Can now handle chunked rad69 soap response stream with low memory use  

## v1.0.0 (2022-03-23)
* Adds Rad69 as download method 
* Replaces 'wado' argument to Trolley with abstract downloader. Abstract 'Downloader' class is implemented by both Wado and Rad69  

## v0.8.1 (2021-10-14)
* Adds PatientID to DICOM query parameters

## v0.8.0 (2021-10-14)

* Makes it possible to download series and studies without instance information. 
  Trolley will fire additional queries in the background to find missing instance info.
  This makes it much easier to select from a study or series level query and download only 
  selected without having to manually re-query at the image level

## v0.7.0 (2021-10-12)

* Adds additional search fields to DICOMQuery widening DICOM-QR search scope

## v0.6.0 (2021-09-27)

* Renames base exception DICOMTrolleyException to pep8 complient DICOMTrolleyError

## v0.5.4 (2021-06-23)

* Fix typo

## v0.5.3 (2021-06-23)

* Correct usage of dataclass
* DICOM-QR fix

## v0.5.2 (2021-04-12)

* Adds WADO-only examples 
* Improves readme

## v0.5.1 (2021-04-10)

* Adds DICOM-QR search
* Changes to Trolley method signatures

## v0.4.0 (2021-04-05)

* Added multi-threaded WADO downloads 
* Changes to Trolley method signatures


## v0.3.0 (2021-04-01)

* Added examples
* Improved readme
* Fixed bugs (date format for queries and wado download function) 


## v0.2.0 (2021-03-31)

* Added MINT 
* Added WADO 
* Added main trolley functions

## v0.1.0 (2021-03-12)

* Initial version