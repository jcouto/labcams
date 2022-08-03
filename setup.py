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
    version = '0.6.0',
    author = 'Joao Couto',
    author_email = 'jpcouto@gmail.com',
    description = 'Multicamera video acquisition,online compression and automation',
    long_description = longdescription,
    long_description_content_type='text/markdown',
    license = 'GPL',
    install_requires = requirements,
    url = "https://bitbucket.org/jpcouto/labcams",
    packages = ['labcams'],
    python_requires='>3.8',
    entry_points = {
        'console_scripts': [
            'labcams = labcams.gui:main',
        ]
    },
)


