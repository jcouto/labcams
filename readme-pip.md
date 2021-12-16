# labcams

A package for video acquisition and automation of experimens, uses separate processes to record and store data.

## Usage

Open a terminal and type ``labcams -h`` for help.

The first time you run ``labcams`` it will create a folder in the user home directory where the default preference file is stored.

## Configuration files:

Configuration files ensure you always use the same parameters during your experiments.

The configuration files are simple ``json`` files. There are 2 parts to the files.

A section were each camera is specified and a part with general parameters.

Available camera drivers:

* `PCO` - install pco.sdk
* `AVT` - install Vimba SDK and pymba
* `QImaging` 
* `pointgrey` - FLIR cameras - install Spinnaker
* `openCV` - webcams and so on

Each camera has its own parameters, there are some parameters that are common to all:

* `recorder` - the type of recorder `tiff` `ffmpeg` `opencv` `binary`
* `haccel` - `nvidia` or `intel` for use with ffmpeg for compression.
* 'CamStimTrigger' - controls the arduino camera trigger, see the duino examples folder.


## UDP and ZMQ:

``labcams`` can listen for UDP or ZMQ commands.


To configure use the command ``"server":"udp"`` in the end of the config file.

The port can be configured with ``"server_port":9999``

The UDP commands are:

* Set the experiment name - ``expname=EXPERIMENT_NAME``
* Software trigger the cameras (this is software, multiple cameras are not in sync) - ``softtrigger=1``
* Hardware trigger mode and save - ``trigger=1``
* Start/stop saving - ``manualsave=1``
* Add a message to the log - ``log=MESSAGE``
* Quit - ``quit``
