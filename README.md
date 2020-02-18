
                                            MMM
                                           MMMMMM
    MMM:               .MMMM             MMMM MMMMMMMM
    MMM:               .MMMM            MMMMM MMMMMMMM      
    MMM:               .MMMM             MMMM  MMMMMM        MM 
    MMM:  :MMMMMMMMM.  .MMMMOMMMMMM       MN     MMM      MMMMM 
    MMM:  :M     MMMM  .MMMMM?+MMMMM    MMMMMMMMMMMMMMM7MMMMMMM  
    MMM:         OMMM  .MMMM    MMMM    MMMMMMMMMMMMMMMMMMMMMMM 
    MMM:  .MMMMMMMMMM  .MMMM    ?MMM    MMMMMMMMMMMMMMMMMMMMMMM 
    MMM:  MMMM  .8MMM  .MMMM    ZMMM    MMMMMMMMMMMMMMMMMMMMMMM 
    MMM:  MMM=...8MMM  .MMMM    MMMM    MMMMMMMMMMMMMMM.MMMMMMM  
    MMM:  MMMMMMMMMMM  .MMMMMMMMMMM                        MMMM 
    MMM:   MMMMM 8MMM  .MMMM:MMMMZ                            M 

         MMMMMMN  =MMMMMMMM     MMMM.MMMM$ .+MMMM      MMMMMMM: 
       MMMMMMMMM  +MMMMMMMMM$   MMMMMMMMMMMMMMMMMM   MMMMMMMMM8 
      MMMM               MMMM   MMMM   MMMM    MMM+  MMM8       
      MMMZ          OMMMMMMMM   MMMM   NMMM    MMM?  MMMMMMM$   
      MMMI        MMMMM  MMMM   MMMM   NMMM    MMM?   ZMMMMMMMM 
      MMMM       7MMM    MMMM   MMMM   NMMM    MMM?        MMMM 
       MMMMD+7MM  MMMN   MMMM   MMMM   NMMM    MMM?  MM$:.7MMMM   
        MMMMMMMM  ZMMMMMOMMMM   MMMM   NMMM    MMM?  MMMMMMMM+





Multicamera control and acquisition. Uses separate processes to record from multiple cameras at high speed.

Supported cameras:
------------------
	- Allied Vision Technologies (via pymba)
	- PointGrey cameras (via PySpin)
	- QImaging cameras via the legacy driver (only windows)
	- PCO cameras (only windows)
	- Ximea cameras
Features:
---------
	- Separates viewer, camera control/acquisition and file writer in different processes.
	- Data from camera acquisition process placed on a cue.
	- Display options: background subtraction; histogram equalization; pupil tracking via the [ mptracker ](https://bitbucket.org/jpcouto/mptracker).	
	- Multiple buffers on Allied vision technologies cameras allows high speed data acquisition.


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

