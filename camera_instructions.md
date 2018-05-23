Camera instructions
===================

Allied Vision Technologies cameras (AVT):
----------------------------------------

Installing drivers and connecting cameras:
++++++++++++++++++++++++++++++++++++++++++

* Vimba drivers
* Pymba
* Jumbo packets
* Cable connections and diagram 
     general (camera, computer,ethernet,triggering box)

### Triggering box for AVT cameras
We designed a triggering box to power cameras; record the triggers and to be able to trigger AVT cameras with TTL signals.

####Info

Schematics and PCB were done on KiCad.

#### Circuit diagram

Power is on the left, camera interface on top and Arduino interface on bottom.
Only 2 outputs are used: the GC can only use 1, and while the Mako can use up to 3, there is no likely scenario where 3 outputs are needed.

The two main components of the board are the 74HCT14 (Hex Inverter with Schmitt trigger) and the LM7805 (Voltage regulator which outputs 5V).
We only want the Hex Inverter to put the signals to 5V, without inverting, so we invert the signals twice.
The LM7805 is used instead of a voltage divider because it will still supply 5V with a 24V input (it will overheat), allowing a potentially connected Due to survive.

![picture](images/trigger_box_schematic.svg)

##### PCB design

* There is an indicating LED for each connection Cam-Due.
* The 1k Resistors (U3 and U4) are the pull up/down resistors for the camera outputs, and can be connected either to 5V or GND, depending on the camera.
* Some pins are doubled (e.g. 12V, GND) to allow a mechanically stable juxtaposition of several trigger boxes.
This allows several boards to share the same power supply and the same trigger source.
* The LM7805 is placed in a way that allows it to be bent forward or backward.

![picture](images/trigger_box_avt.png)

##### Connections for the GC camera

We are using the first 5 pins of the camera.
* In1 (camera) on IN (board).
* Out1 on OUT1.
* Camera Power on PWR 12V.
* Camera GND and Isolated IO GND on GND.

GC Hirose HR10A-10R-12PB connector
-------
Signal|Color
Camera GND|Blue
Camera Power|Red
In 1| Pink
Out 1|Gray
Isolated IO GND|Yellow

[Complete table](images/gc_conn.png)
 
##### Connections for the Mako

We are using 7 pins of the camera (all except Out3).
* In1 (camera) on IN (board).
* Out1 on OUT1.
* Out2 on OUT2.
* Isolated Out Power on USER PWR 5V.
* Camera Power on PWR 12V.
* Camera GND and Isolated IN GND on GND.

Mako Hirose HR25-7TR-8PA(73) connector
-------
Signal|Color
Out 1|Yellow dot Red
Out 2|Yellow dot Black
In 1|Grey dot Black
Isolated In GND|Pink dot Black
Isolated Out Power|Pink dot Red
Camera power|Orange dot Black
Camera GND|Orange dot Red


[Complete table](images/mako_conn.png)