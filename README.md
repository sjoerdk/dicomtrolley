# dicomtrolley

[![CI](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/sjoerdk/dicomtrolley/actions/workflows/build.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dicomtrolley)](https://pypi.org/project/dicomtrolley/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Retrieve medical images using DICOM WADO and MINT.
Requires python 3.7, 3.8 or 3.9
Represents images as `pydicom` Datasets.

![A trolley](docs/resources/trolley.png)

## Usage
```
from import dicomtrolley import Trolley

trolley = Trolley(url='https://server/login',
                  user='user',
                  password='pass',
                  realm='realm')

trolley.download_study(study_uid='1234', path='/tmp/study1234')
```

## Caveats
Dicomtrolley has been developed for and tested on a Vitrea Connection 8.2.0.1 system. This claims to
be consistent with WADO and MINT 1.2 interfaces, but does not implement all parts of these standards. 

Certain query parameter values and restraints might be specific to Vitrea Connection 8.2.0.1. For example,
the exact list of DICOM elements that can be returned from a query might be different for different servers.