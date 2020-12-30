#!/usr/bin/env python
# Install script for labcams.
# Joao Couto - March 2017
import os
from os.path import join as pjoin
from setuptools import setup
from setuptools.command.install import install

with open("readme-pip.md", "r") as fh:
    longdescription = fh.read()

requirements = []
with open("requirements.txt","r") as f:
    requirements = f.read().splitlines()
    
data_path = pjoin(os.path.expanduser('~'), 'labcams')

setup(
    name = 'labcams',
    version = '0.2.1',
    author = 'Joao Couto',
    author_email = 'jpcouto@gmail.com',
    description = (longdescription),
    long_description = longdescription,
    license = 'GPL',
    install_requires = requirements,
    url = "https://bitbucket.org/jpcouto/labcams",
    packages = ['labcams'],
    entry_points = {
        'console_scripts': [
            'labcams = labcams.gui:main',
        ]
    },
)


