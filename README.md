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

