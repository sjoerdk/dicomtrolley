# dicomtrolley

[![CI](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![Code Climate](https://codeclimate.com/github/sjoerdk/dicomtrolley/badges/gpa.svg)](https://codeclimate.com/github/sjoerdk/dicomtrolley)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Retrieve medical images via WADO-URI, WADO-RS, QIDO-RS, MINT, RAD69 and DICOM-QR

* Requires python 3.7, 3.8 or 3.9
* Uses `pydicom` and `pynetdicom`. Images and query results are `pydicom.Dataset` instances
* Multi-threaded downloading using `requests-futures`

![A trolley](resources/trolley.png)

## Installation
```
pip install dicomtrolley
```

## Documentation
see [dicomtrolley github docs](https://github.com/sjoerdk/dicomtrolley/tree/master/docs)
