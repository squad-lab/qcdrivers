# Drivers 🔧
Repository for collecting and sharing QCoDeS drivers not available through the [qcodes](https://github.com/microsoft/qcodes), or the [contrib drivers](https://github.com/QCoDeS/Qcodes_contrib_drivers) repositories. May contain proprietary drivers made by the lab members, including those in conjunction with related companies.

## Installation:
This repository can be installed with: 

```bash
uv add git+https://gitlab.com/squad-lab/measurements/drivers.git
```
Generally, the pip packages have only been tested with `python>=3.12`. Please make sure to update your python installation before going on with installation. For the full list of app dependencies, check [pyproject.toml](pyproject.toml). [uv](https://docs.astral.sh/uv/)-based project management recommended.

## Directory Structure:
The repository is structured as follows:
```
.
├── LICENSE
├── README.md
├── pyproject.toml
├── setup.py
└── src
    └── company/university
        ├── __init__.py
        ├── package
            ├── __init__.py
            ├── README.md
            ├── contents
            └── helpers/
```
This structure must be followed when adding new drivers to the repostitory, the existing drivers should be taken as reference for contribution. For cleaner imports, you can pre-import the drivers in the `__init__.py` file of the respective driver directory. Check [the SQUAD folder](src/squad/__init__.py) for an example.

## Imports and Usage:
The drivers can be imported and used as follows:
```python
from drivers.company.package.package import driver
```
The README for specific drivers can be found in their respective driver directory. The extensive list of parameters can be listed through qcodes:
```python
driver_name = driver("driver_name", address="address", *args, **kwargs)
print(driver_name.parameters)
```

## Contributing:
To contribute to the repository, please follow the directory structure and create a pull request. The pull request will be reviewed by the maintainers and merged if it meets the requirements. The drivers should be well documented and tested before submission. Everyone is free to open an [issue](https://gitlab.com/squad-lab/measurements/drivers/-/issues) for any bugs or feature requests.