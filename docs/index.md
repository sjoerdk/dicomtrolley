# dicomtrolley


[![CI](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![Code Climate](https://codeclimate.com/github/sjoerdk/dicomtrolley/badges/gpa.svg)](https://codeclimate.com/github/sjoerdk/dicomtrolley)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Retrieve medical images via WADO-URI, WADO-RS, QIDO-RS, MINT, RAD69 and DICOM-QR

* Uses `pydicom` and `pynetdicom`. Images and query results are `pydicom.Dataset` instances
* Query and download DICOM Studies, Series and Instances
* Integrated search and download - automatic queries for missing series and instance info

![A trolley](resources/trolley.png)

## Installation
```
pip install dicomtrolley
```

## Basic usage
```python
# Create a http session
session = requests.Session()

# Use this session to create a trolley using MINT and WADO
trolley = Trolley(searcher=Mint(session, "https://server/mint"),
                  downloader=WadoURI(session, "https://server/wado_uri"))

# find some studies (using MINT)
studies = trolley.find_studies(Query(PatientName='B*'))

# download the fist one (using WADO)
trolley.download(studies[0], output_dir='/tmp/trolley')
```
## Documentation
see [dicomtrolley docs on readthedocs.io](https://dicomtrolley.readthedocs.io)

## Examples
Example code can be found [on github](https://github.com/sjoerdk/dicomtrolley/tree/master/examples)

## Alternatives
* [dicomweb-client](https://github.com/MGHComputationalPathology/dicomweb-client) - Active library supporting QIDO-RS, WADO-RS and STOW-RS. 
* [pynetdicom](https://github.com/pydicom/pynetdicom) - dicomtrolley's DICOM-QR support is based on pynetdicom. Pynetdicom supports a broad range of DICOM networking interactions and can be used as a stand alone application.

## Caveats
Dicomtrolley has been developed for and tested on a Vitrea Connection 8.2.0.1 system. This claims to
be consistent with WADO and MINT 1.2 interfaces, but does not implement all parts of these standards. 

Certain query parameter values and restraints might be specific to Vitrea Connection 8.2.0.1. For example,
the exact list of DICOM elements that can be returned from a query might be different for different servers.

## Contributing
See [Contributing](contributing.md)