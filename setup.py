import os

from setuptools import find_packages, setup

# Get version from pii_shield/__init__.py
version = {}
with open(os.path.join("pii_shield", "__init__.py")) as f:
    exec(f.read(), version)

# Read long description from README.md
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="pii-shield",
    version=version.get("__version__", "0.1.0"),
    author="PII Shield Contributors",
    author_email="pii.shield@mdigital.com.pl",
    description="Django package for selective data synchronization between secure networks and DMZ",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/krystianmagdziarz/PII-Shield",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Django :: 5.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.12",
    install_requires=[
        "Django>=5.2.1",
        "redis>=6.1.0",
        "cryptography>=42.0.0",
    ],
)
