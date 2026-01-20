# Contributing
You can contribute to this library in different ways

## Report bugs
Report bugs at [https://github.com/sjoerdk/dicomtrolley/issues]()

## Contribute code
### Get the code
Fork this repo, create a feature branch

### Set up environment
dicomtrolley uses [uv](https://docs.astral.sh/uv) for dependency and package management 

* Install uv (see [uv docs](https://docs.astral.sh/uv/getting-started/installation/))

* Create a virtual env. Go to the folder where you cloned dicomtrolley and use 
  ```  
  uv sync 
  ``` 

* Install [pre-commit](https://pre-commit.com) hooks.
  ```
  pre-commit install
  ```
  
### Add your code 
Make your code contributions. Make sure document and add tests for new features.
To automatically publish to pypi, increment the version number and push to master. See below. 

### Lint your code
* Run all tests
* Run [pre-commit](https://pre-commit.com):
  ```
  pre-commit run
  ```
### Publish
Create a pull request: [https://github.com/sjoerdk/dicomtrolley/compare]()

### Incrementing the version number
A merged pull request will only be published to pypi if it has a new version number. 
To bump dicomtrolley's version, do the following:

* dicomtrolley uses [semantic versioning](https://semver.org/) Check whether your addition is a PATCH, MINOR or MAJOR version.

* Manually increment the version number: `pyproject.toml` -> `version = "0.1.2"`
  
* Add a brief description of your updates new version to `HISTORY.md`

### Updating docs
Docs are based on [mkdocs](https://www.mkdocs.org/), using the 
[Materials for mkdocs](https://squidfunk.github.io/mkdocs-material/) skin.

Docs are published on [readthedocs.org](https://about.readthedocs.com/). Docs build requirements are in 
pyproject.toml in the dependency-group `docs`. 

To edit the docs:

* Install docs dependencies: `uv sync --group docs` (by default uv sync does _not_ install the docs group)

* Edit content in `/docs`

* Try out your changes using `uv run mkdocs serve`

* To add docs requirements: `uv add --group dev <package to add>`. To remove `uv remove --group dev <package to add>` 
