
LabCams
=======

Software to acquire data from cameras. 
Current in alpha testing!

Supported hardware:
-------------------
	- Allied Vision Technologies via the Vimba driver (pymba).
	- QImaging cameras via the legacy driver.

Features:
---------
	- Separates viewer, camera control/acquisition and file writer in different processes.
	- Data from camera acquisition process placed on a cue.
	- Display options: background subtraction; histogram equalization; pupil tracking via the [ mptracker ](https://bitbucket.org/jpcouto/mptracker).	
	- Multiple buffers on Allied vision technologies cameras allows high speed data acquisition.
This uses separate processes to record from multiple cameras at high speed.

Instalation:
------------
 Works with python 2.7 - runs on python 3.x but without camera support.

**Note:** On windows I suggest getting the [ git bash terminal ](https://git-scm.com/downloads).

1. Get [ miniconda ](https://conda.io/miniconda.html) (I suggest Python 2.7 x64) 
2. ``conda install pyqt pyzmq scipy numpy matplotlib future tqdm``
3. ``conda install -c menpo opencv3``
3. ``conda install -c conda-forge tifffile``
4. Follow the [camera specific instalation](./camera_instructions.md)  and syncronization instructions.
5. Clone the repositoty: ``git clone git@bitbucket.org:jpcouto/labcams.git``
6. Go into that folder``cd labcams`` and finally ``python setup.py develop``. The develop instalation makes that changes to the code take effect immediately.

Usage:
------
Typing ``labcams -h`` for help.

Configuration files:
--------------------
Configuration files ensure you always use the same parameters during your experiments.

Here should be a description of options on the configuration files.



**Please let me know whether this works for you and acknowledge if you use it in a publication.**

Joao Couto - jpcouto@gmail.com
May 2017
