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
                          https://bitbucket.org/jpcouto/labcams   

Multicamera control and acquisition.

This aims to facilitate video acquisition and automation of experimens, uses separate processes to record and store data.

### Supported cameras -  [see instructions here](./camera_instructions.md):

 * Allied Vision Technologies (via pymba)
 * PointGrey cameras (via PySpin)
 * QImaging cameras via the legacy driver (only windows)
 * PCO cameras (only windows)
 * Ximea cameras

### Features:

 *  Separates viewer, camera control/acquisition and file writer in different processes.
 *  Data from camera acquisition process placed on a cue.
 *  Display options: background subtraction; histogram equalization; pupil tracking via the [ mptracker ](https://bitbucket.org/jpcouto/mptracker).	
 *  Multiple buffers on Allied vision technologies cameras allows high speed data acquisition.
 * Online compression using ffmpeg (supports hardware acceleration)


## Instalation from pip (recommended but not the latest version):

``pip install labcams`` or add the ``--no-deps`` flag to install no dependencies.

## Instalation on Ubuntu 20.04

``sudo apt install python3-matplotlib ipython3 python3-opencv python3-pyqt5 python3-tqdm python3-pip python3-pyqtgraph python3-serial python3-zmq python3-natsort python3-pandas emacs git ssh``


``pip3 install labcams`` - this may end up in ``$HOME/.local/bin`` so add the following to the end of the ``.bashrc`` file: ``export PATH=$PATH:$HOME/.local/bin``

## Instalation - from git:

**Note:** On windows get the [ git bash terminal ](https://git-scm.com/downloads). I had issues running from cmd.exe when installed with conda.

1. Get [ anaconda ](https://conda.io/anaconda.html). Add conda to system PATH when asked. Open a terminal (use git bash if on windows) and type ``conda init bash``.
2. Clone the repository: ``git clone git@bitbucket.org:jpcouto/labcams.git``
3. Go into the cloned ``cd labcams`` folder.
4. Install the required packages, use e.g. ``pip install -r requirements.txt`` or conda install... 
5. Install ``labcams`` with ``python setup.py develop``
6. Follow the [camera specific instalation](./camera_instructions.md) and instructions for syncronization. Each camera must have a section in the ``~/labcams/default.json`` file that is created the first time you try to run the software with the command ``labcams`` from the terminal. Use a text editor to add the correct options. There are examples in the examples folder.

You can run ``labcams`` from the command terminal. Install *FFMPEG* if you need to save in compressed video formats.

## Usage:

Open a terminal and type ``labcams -h`` for help.

The first time you run ``labcams`` it will create a folder in the user home directory where the default preference file is stored.

### Command line options:

|       |  command     | description |
|-------|--------------|-------------|
| ``-w``| ``--wait``   | start with software trigger OFF |
| ``-t``| ``--triggered`` |  start with hardware trigger ON |
| ``-c X Y`` | ``--cam-select X Y``     |  start only some cameras ``-c 0 1`` |
| ``-d PATH`` | ``--make-config PATH``  |  create a configuration file |
| | ``--no-server`` | do not start the ZMQ nor the UDP server |


## Configuration files:

Configuration files ensure you always use the same parameters during your experiments.

The configuration files are simple ``json`` files. There are 2 parts to the files.

1. ``cams`` - **camera descriptions** - each camera has a section to store acquisition and recording parameters.

Available camera drivers:

 * `PCO` - install pco.sdk
 * `AVT` - install Vimba SDK and pymba
 * `QImaging` 
 * `pointgrey` - FLIR cameras - install Spinnaker
 * `openCV` - webcams and so on

Each camera has its own parameters, there are some parameters that are common to all:

* `recorder` - the type of recorder `tiff` `ffmpeg` `opencv` `binary`
 * `haccel` - `nvidia` or `intel` for use with ffmpeg for compression.

**NOTE:** You need to get ffmpeg compiled with `NVENC` from [here](https://developer.nvidia.com/ffmpeg) - precompiled versions are avaliable - `conda install ffmpeg` works. Make sure to have python recognize it in the path (using for example `which ffmpeg` to confirm from git bash)/


**NOTE** To use `intel` acceleration you need to download the [mediaSDK](https://software.intel.com/content/www/us/en/develop/tools/media-sdk.html).


2. **general parameters** to control the remote communication ports and general gui or recording parameters.

 * `recorder_frames_per_file` number of frames per file
 * `recorder_path` the path of the recorder, how to handle substitutions - needs more info.
 

3. Aditional parameters:

 * 'CamStimTrigger' - controls the arduino camera trigger, see the duino examples folder.


### UDP and ZMQ:

``labcams`` can listen for UDP or ZMQ commands.


To configure use the command ``"server":"udp"`` in the end of the config file.

The port can be configured with ``"server_port":9999``

The UDP commands are:

 * Set the experiment name ``expname=EXPERIMENT_NAME``
 * Software trigger the cameras ``softtrigger=1`` (multiple cameras are not in sync)
 * Hardware trigger mode and save ``trigger=1``
 * Start/stop saving ``manualsave=1``
 * Add a message to the log ``log=MESSAGE``
 * Quit ``quit``

**Please drop me a line for feedback and acknowledge if you use labcams in your work.**


Joao Couto - jpcouto@gmail.com

May 2017



## Debugging:

### FFMPEG recordings with (realtime) nvidia encoding.

To do this you need to have a version of ffmpeg compile with NVENC.

If you have the error:

   ``Unrecognized option 'cq:v'.``

Make sure you have the version with NVENC, check with ``which ffmpeg`` which version is running



