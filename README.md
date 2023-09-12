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

![A trolley](docs/resources/trolley.png)

[dicomtrolley docs on readthedocs.io](https://dicomtrolley.readthedocs.io)

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
