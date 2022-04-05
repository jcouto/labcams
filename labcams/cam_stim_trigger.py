#  labcams - https://jpcouto@bitbucket.org/jpcouto/labcams.git
# Copyright (C) 2020 Joao Couto - jpcouto@gmail.com
#
#  This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Class to interface with the teensy for controlling LED gating
#
import serial
import time
import sys
from multiprocessing import Process,Queue,Event,Value,Array
from ctypes import c_char_p,c_longdouble,c_long
import numpy as np
import re

import os
from os.path import join as pjoin
import csv
from datetime import datetime

import sys
from .utils import display
if sys.version_info >= (3, 0):
    long = lambda x: int(x)

# SERIAL MESSAGES
ERROR='E'
ARM = 'N'
QUERY_CAP = 'Q'
STX='@'
SEP = '_'
ETX=serial.LF.decode()
DISARM = 'S'
SET_MODE = 'M'
SYNC = 'T'
SYNC1 = 'U'
#SET_PARAMETERS = 'P'
FRAME = 'F'
NCHAN = 'C'
# Class to talk to arduino  using a separate process.
class CamStimInterface(Process):
    def __init__(self,
                 port=None,
                 baudrate=2000000,
                 inQ = None,
                 outQ=None,
                 saving = None,
                 timeout=0.1):
        Process.__init__(self)
        if port is None:
            raise(ValueError(
                'Camera stim trigger needs a serial port connection.'))
        if inQ is None:
            inQ = Queue()
        self.inQ = inQ
        self.outQ = outQ
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        if saving is None:
            self.is_saving = Event()
        else:
            self.is_saving = saving
        try:
            self.ino = serial.Serial(port=self.port,
                                     baudrate=self.baudrate,
                                     timeout = self.timeout)
        except serial.serialutil.SerialException:
            raise(serial.serialutil.SerialException('''
Could not open teensy on port {0}

            Try logging out and back in to clear the port.'''.format(self.port)))
        self.ino.write((STX + DISARM + ETX).encode())
        self.ino.flushInput()
        tread,message = self.ino_read()
        self.ino.write((STX + QUERY_CAP + ETX).encode())
        tread,message = self.ino_read()
        msg = message.split('_')
        self.nchannels = Value('i',1)
        self.modes = []
        if STX+QUERY_CAP in msg:
            if "NCHANNELS" in message:
                arg = msg.index("NCHANNELS")
                if not arg is None:
                    self.nchannels.value = int(msg[arg+1].strip('\n'))
#                    print('Got {0} channels from capabilities.'.format(self.nchannels.value))
            if "MODES" in message:         
                arg = msg.index("MODES")
                if not arg is None:
                    self.modes = msg[arg+1].strip('\n').split(":")
        self.ino.close()
        display('Probed port {0}.'.format(port))

        self.corrupt_messages = 0
        self.exit = Event()        
        self.mode = Value('i',3)
        self.frame_count = Value('i',0)
        self.last_led = Value('i',0)
        self.last_time = Value('f',0)

        self.sync_frame_count = Value('i',0)
        self.sync_count = Value('i',0)
        self.sync = Value('i',0)
        self.last_sync_time = Value('f',0)

        #self.start()
    def close(self):
        self.exit.set()

    def display(self,msg):
        print('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg)
        
    def ino_write(self, data):
        self.ino.write((STX + data + ETX).encode())
    
    def ino_read(self):
        msg = self.ino.readline().decode()
        return time.time(),msg

    def check_nchannels(self):
        self.inQ.put(NCHAN)
        
    def arm(self):
        self.inQ.put(ARM)

    def disarm(self):
        self.inQ.put(DISARM)

    def set_mode(self, mode = None):
        if len(self.modes):
            if mode is None:
                mode = self.mode.value
            self.mode.value = mode
            self.inQ.put(SET_MODE + SEP + str(mode))
        
    def process_message(self, tread, msg):
        #treceived = long((tread - self.expStartTime.value)*1000)
        #print(msg)
        if msg.startswith(STX) and msg[-1].endswith(ETX):
            msg = msg.strip(STX).strip(ETX)
            if msg[0] == ARM:
                display('Stimulation is armed.')
            elif msg[0] == DISARM:
                display('Stimulation is disarmed.')
            elif msg[0] == SET_MODE:
                tmp = msg.split(SEP)
                self.mode.value = int(tmp[1])
            elif msg[0] == SYNC:
                tmp = msg.split(SEP)
                self.sync_frame_count.value = int(tmp[1])
                sync_count = int(tmp[2])
                if sync_count == self.sync_count.value:
                    self.sync.value = 0
                else:
                    self.sync.value = 1
                self.sync_count.value = sync_count
                self.last_sync_time.value = float(tmp[3])
                return(['#SYNC:{0},{1},{2}'.format(self.sync_count.value,
                                                   self.sync_frame_count.value,
                                                   self.last_sync_time.value)])
            elif msg[0] == SYNC1:
                tmp = msg.split(SEP)
                return(['#SYNC1:{0},{1},{2}'.format(int(tmp[2]),
                                                   int(tmp[1]),
                                                   float(tmp[3]))])    
            elif msg[0] == FRAME:
                tmp = msg.split(SEP)
                self.frame_count.value = int(tmp[2])
                self.last_led.value = int(tmp[1])
                self.last_time.value = float(tmp[3])
                return(['#LED:{0},{1},{2}'.format(self.last_led.value,
                                                  self.frame_count.value,
                                                  self.last_time.value)])
            elif msg[0] == NCHAN:
                tmp = msg.split(SEP)
                self.nchannels.value = int(tmp[1])
            else:
                print('[CamStimTrigger] Unknown message: ' + msg)
        else:
            self.corrupt_messages += 1
            display('Error on msg [' + str(self.corrupt_messages) + ']: '+ msg.strip(STX).strip(ETX))
            return ['#ERROR {0}'.format(msg)]
        return None

    def run(self):
        self.ino = serial.Serial(port=self.port,
                                 baudrate=self.baudrate,
                                 timeout = self.timeout)
        self.ino.flushInput()
        time.sleep(0.5) # So that the first cued orders get processed
        while not self.exit.is_set():
            # Write whatever needed
            if not self.inQ.empty():
                message = self.inQ.get()
                self.ino_write(message)
            # Read whatever is there
            if (self.ino.inWaiting() > 0):
                tread,message = self.ino_read()
                try:
                    toout = self.process_message(tread,message)
                except Exception as m:
                    display('ERROR with: ' + message)
                    print(m)
                finally:
                    if (not toout is None) and (self.is_saving.is_set()):
                        if not self.outQ is None:
                            self.outQ.put(toout)
        self.ino.close()        
        display('[CamStimTrigger] Ended communication with arduino.')

    def close(self):
        display('[CamStimTrigger] Calling exit.')
        self.exit.set()
