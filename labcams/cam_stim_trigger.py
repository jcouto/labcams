#! /usr/bin/env python
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
STX='@'
SEP = '_'
ETX=serial.LF.decode()
DISARM = 'S'
SET_MODE = 'M'
SET_PARAMETERS = 'P'
FRAME = 'F'
# Class to talk to arduino  using a separate process.
class CamStimInterface(Process):
    def __init__(self,port='COM3', baudrate=115200,
                 inQ = None, outQ=None, saving = None, timeout=0.1):
        Process.__init__(self)
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
        self.ino.flushInput()
        self.ino.close()
        display('Probed port {0}.'.format(port))

        self.corrupt_messages = 0
        self.exit = Event()        
        self.mode = Value('i',3)
        self.frame_count = Value('i',0)
        self.last_led = Value('i',0)
        self.last_time = Value('i',0)
        self.width = Value('i',13000)
        self.margin = Value('i',1000)
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

    def arm(self):
        self.inQ.put(ARM)

    def disarm(self):
        self.inQ.put(DISARM)

    def set_parameters(self, width = None, margin = None):
        if width is None:
            width = self.width.value
        if margin is None:
            margin = self.margin.value
        self.width.value = width
        self.margin.value = margin
        self.inQ.put(SET_PARAMETERS + SEP + str(width) + SEP + str(margin))

    def set_mode(self, mode = None):
        if mode is None:
            mode = self.mode.value
        self.mode.value = mode
        self.inQ.put(SET_MODE + SEP + str(mode))

    def print_parameters(self):
        msg = '''
        LED gating parameters:
             - mode {0}
             - width {1}
             - margin {2}
        '''.format(self.mode.value,
                   self.width.value,
                   self.margin.value)
        display(msg)
        
    def process_message(self, tread, msg):
        #treceived = long((tread - self.expStartTime.value)*1000)
        #print(msg)
        if msg.startswith(STX) and msg[-1].endswith(ETX):
            msg = msg.strip(STX).strip(ETX)
            if msg[0] == ARM:
                display('Stimulation is armed.')
            elif msg[0] == DISARM:
                display('Stimulation is disarmed.')
            elif msg[0] == SET_PARAMETERS:
                tmp = msg.split(SEP)
                self.width.value = int(tmp[1])
                self.margin.value = int(tmp[2])
                self.print_parameters()
            elif msg[0] == SET_MODE:
                tmp = msg.split(SEP)
                self.mode.value = int(tmp[1])
            elif msg[0] == FRAME:
                tmp = msg.split(SEP)
                self.frame_count.value = int(tmp[1])
                self.last_led.value = int(tmp[2])
                self.last_time.value = int(tmp[3])
                return(['#LED:{0},{1},{2}'.format(self.frame_count.value,
                                            self.last_led.value,
                                            self.last_time.value)])
            else:
                print('Unknown message: ' + msg)
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
        self.set_parameters()
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
        display('Ended communication with arduino.')

    def close(self):
        display('[CamStimTrigger] Calling exit.')
        self.exit.set()
