# coding: utf-8

"""
    Turbinia API Server

    Turbinia is an open-source framework for deploying, managing, and running distributed forensic workloads

    The version of the OpenAPI document: 1.0.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from setuptools import setup, find_packages  # noqa: H301

# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools
NAME = "turbinia-api-lib"
VERSION = "1.0.0"
PYTHON_REQUIRES = ">=3.7"
REQUIRES = [
    "urllib3 >= 1.25.3, < 2.1.0",
    "python-dateutil",
    "pydantic >= 1.10.5, < 2",
    "aenum"
]

setup(
    name=NAME,
    version=VERSION,
    description="Turbinia API Server",
    author="OpenAPI Generator community",
    author_email="team@openapitools.org",
    url="",
    keywords=["OpenAPI", "OpenAPI-Generator", "Turbinia API Server"],
    install_requires=REQUIRES,
    packages=find_packages(exclude=["test", "tests"]),
    include_package_data=True,
    license="Apache License 2.0",
    long_description_content_type='text/markdown',
    long_description="""\
    Turbinia is an open-source framework for deploying, managing, and running distributed forensic workloads
    """,  # noqa: E501
    package_data={"turbinia_api_lib": ["py.typed"]},
)
