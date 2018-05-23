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
Connect the Ethernet cable to your computer.
Typically, Vimba Viewer recognizes the camera, but you can not record.
If this is the case then you have to change your IP address. 
On Windows: Control Panel -> Network & Internet -> Network connections -> right-click Ethernet -> Properties -> Networking: Select IPv4 -> Properties -> Use the following IP address. Then change it to a value close to the one of the camera (accessible in the Vimba Viewer in the “information” tab on the right). In my case I used 168.254.100.0 for the IP address and 255.255.0.0 for the subnet mask.



### Triggering box for AVT cameras
We designed a triggering box to power cameras; record the triggers and to be able to trigger AVT cameras with TTL signals.

####Info

Schematics and PCB were done on KiCad. [Design files](pcb/)

PCB printing was outsourced to [Eurocircuits](https://www.eurocircuits.com).

#### Circuit diagram

Power is on the left, camera interface on top and Arduino interface on bottom.
Only 2 outputs are used: the GC can only use 1, and while the Mako can use up to 3, there is no likely scenario where 3 outputs are needed.

The two main components of the board are the 74HCT14 (Hex Inverter with Schmitt trigger) and the LM7805 (Voltage regulator which outputs 5V).
We only want the Hex Inverter to put the signals to 5V, without inverting, so we invert the signals twice.
The LM7805 is used instead of a voltage divider because it will still supply 5V with a 24V input (it will overheat), allowing a potentially connected Arduino board to survive.

![picture](images/trigger_box_schematic.svg)

##### PCB design

* There is an indicating LED for each connection Cam-Due.
* The 1k Resistors (U3 and U4) are the pull up/down resistors for the camera outputs, and can be connected either to 5V (GC) or GND (Mako).
* Some pins are doubled (e.g. 12V, GND) to allow a mechanically stable juxtaposition of several trigger boxes.
This allows several boards to share the same power supply and the same trigger source.
* The LM7805 is placed in a way that allows it to be bent forward or backward.
* The two big holes have an M6 diameter.

![picture](images/trigger_box_avt.png)

##### Connections for the GC camera

We are only using the first 5 pins of the camera.

Camera Signal|Wire Color|Trigger box pin
------------ | -------- | --------------
Camera GND|Blue|GND
Camera Power|Red|PWR 12V
In 1| Pink|IN
Out 1|Gray|OUT1
Isolated IO GND|Yellow|GND

GC Hirose HR10A-10R-12PB connector [Complete table](images/gc_conn.png)
 
##### Connections for the Mako

We are using 7 pins of the camera (all except Out3).

Camera Signal|Wire Color|Trigger box pin
------------ | -------- | --------
Out 1|Yellow dot Red|OUT1
Out 2|Yellow dot Black|OUT2
In 1|Grey dot Black|IN
Isolated In GND|Pink dot Black|GND
Isolated Out Power|Pink dot Red|USER PWR 5V
Camera power|Orange dot Black|PWR 12V
Camera GND|Orange dot Red|GND


Mako Hirose HR25-7TR-8PA(73) connector [Complete table](images/mako_conn.png)