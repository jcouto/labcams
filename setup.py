
#!/usr/bin/env python
# Install script for labcams.
# Joao Couto - March 2017

import os
from os.path import join as pjoin
from setuptools import setup
from setuptools.command.install import install


longdescription = ''' Recorder for behavioral cameras and one-photon imaging.'''
data_path = pjoin(os.path.expanduser('~'), 'labcams')

setup(
  name = 'labcams',
  version = '0.0',
  author = 'Joao Couto',
  author_email = 'jpcouto@gmail.com',
  description = (longdescription),
  long_description = longdescription,
  license = 'GPL',
  packages = ['labcams'],
  entry_points = {
        'console_scripts': [
          'labcams = labcams.gui:main',
        ]
        },
#    data_files=[(data_path, [pjoin('configurations',
#                                   'spyking-circus-invivo.params')]),
#    ],

    )


