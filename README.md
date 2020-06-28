labcams
=======

Multicamera control and acquisition. Uses separate processes to record from multiple cameras at high speed.

Supported cameras:
------------------

 * Allied Vision Technologies (via pymba)
 * PointGrey cameras (via PySpin)
 * QImaging cameras via the legacy driver (only windows)
 * PCO cameras (only windows)
 * Ximea cameras

Features:
---------

 *  Separates viewer, camera control/acquisition and file writer in different processes.
 *  Data from camera acquisition process placed on a cue.
 *  Display options: background subtraction; histogram equalization; pupil tracking via the [ mptracker ](https://bitbucket.org/jpcouto/mptracker).	
 *  Multiple buffers on Allied vision technologies cameras allows high speed data acquisition.
 * Online compression using ffmpeg (supports hardware acceleration)


Instalation:
------------

**Note:** On windows I suggest getting the [ git bash terminal ](https://git-scm.com/downloads).

1. Get [ miniconda ](https://conda.io/miniconda.html) (I suggest Python 2.7 x64) 
2. ``conda install pyqt pyzmq scipy numpy matplotlib future tqdm``
3. ``conda install -c menpo opencv3``
3. ``conda install -c conda-forge tifffile``
4. Follow the [camera specific instalation](./camera_instructions.md)  and syncronization instructions.
5. Clone the repositoty: ``git clone git@bitbucket.org:jpcouto/labcams.git``
6. Go into that folder``cd labcams`` and finally ``python setup.py develop``. The develop instalation makes that changes to the code take effect immediately.


Another way is to install conda and do ``pip install -r requirements.txt`` followed by ``python setup.py develop``

Usage:
------
Open a terminal and type ``labcams -h`` for help.

The first time you run ``labcams`` it will create a folder in the user home directory where the default preference file is stored.

Command line options:
+++++++++++++++++++++

| Short | Long command | Function |
|-------|--------------|----------|
| ``-w``| ``--wait`` - start with software trigger off |
| ``-t``| ``--triggered`` |  start with hardware trigger ON |
| ``-c X Y`` | ``--cam-select X Y``     |  start only some cameras ``-c 0 1`` |
| ``-d PATH`` | ``--make-config PATH``  |  create a configuration file |
| | ``--no-server`` | do not start the ZMQ nor the UDP server |
 

Configuration files:
--------------------
Configuration files ensure you always use the same parameters during your experiments.



**Please let me know whether this works for you and acknowledge if you use it in a publication.**

UDP and ZMQ:
------------

labcams can listen for UDP or ZMQ commands.


To configure use the command ``"server":"udp"`` in the end of the config file.

The port can be configured with ``"server_port":9999``

The UDP commands are:
    - Set the experiment name ``expname=EXPERIMENT_NAME``
    - Software trigger the cameras ``softtrigger=1`` (multiple cameras are not in sync)        
    - Hardware trigger mode and save ``trigger=1``
    - Start/stop saving ``manualsave=1``
    - Add a message to the log ``log=MESSAGE``
    - Quit ``quit``

Joao Couto - jpcouto@gmail.com
May 2017

