# History

## v3.0.2 (12-09-23)
* pydicom dataset.save_as ValueErrors are now changed to StorageErrors. Fixes #45

## v3.0.1 (12-09-23)
* Fixes build and documentation errors

## v3.0.0 (11-09-23)
* Adds WADO-RS and QIDO-RS support
* Reworks download mechanics. Fascilitates direct download when you know the ids by introducing DICOMObjectReference. This base for Series-, Study- and SOPInstanceReference can be downloaded directly
* Introduces CachedSearcher to avoid unneeded queries
* Simplifies and clears up trolley download methods by upgrading DICOMDownloadable to base class 
* Simplifies automatic querying for missing ids. Downloader instances can now raise Exceptions for insufficient download info (missing instance, series ids)
* Simplifies Query class structure. Removes BasicQuery class in favour of Query+Exception for unconvertible query parameters
* Updates docs: Moves from single github readme to separate readthedocs build
* All code examples in docs and /examples are now tested
* Main branch is now called main. Removes branch master.

## v2.2.0 (2023-03-23)
* DICOM-QR queries now use Study Root (QR class 1.2.840.10008.5.1.4.1.2.2.1) instead of Patient Root to simplify study-level queries. (#38)

## v2.1.8 (2023-03-07)
* Improves logging for queries and storage
* Adds SeriesInstanceUID to Query object

## v2.1.7 (2022-10-04)
* Add option to ignore certain download errors for robust download (#32)
* Adds logging

## v2.1.6 (2022-09-22)
* Fixes small-chunk performance issue(#28)
* Improves rad69 download stream processing

## v2.1.4 (2022-08-31)
* Splits rad69 requests by series by default. This reduces server load
 
## v2.1.3 (2022-08-02)
* Makes session timeout exceptions more informative for better debugging

## v2.1.2 (2022-07-16)
* Now re-raises underlying urllib3.exceptions.ProtocolError to dicom trolley exception
 
## v2.1.1 (2022-07-14)
* Rebrands some requests server exceptions to dicom trolley exceptions for easier handling

## v2.1.0 (2022-07-11)
* Adds VitreaAuth based on requests AuthBase for easier login and session timeout recovery

## v2.0.2 (2022-07-05)
* Fixes capitalization error in rad69 template

## v2.0.1 (2022-07-05)
* Works around exponential resource usage in pydantic 0.9 by pinning to 0.8

## v2.0.0 (2022-06-27)
* Introduces unified Query object that can be used for any backend. Changes parameter naming 
  and capitalisation for many queries so major version.

## v1.2.0 (2022-06-22)
* Introduces alternate disk storages for Trolley
* Adds FlatStorageDir class as alternate storage
* Adds test coverage configuration with .coveragerc

## v1.1.1 (2022-05-18)
* Adds jpeg lossless transfer syntax (1.2.840.10008.1.2.4.70) to rad-69 requests 

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
