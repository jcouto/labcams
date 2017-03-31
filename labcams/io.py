#! /usr/bin/env python
# Classes to save files from a multiprocessing queue

import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
from datetime import datetime
import time
import sys

class CamWriter(Process):
    frameCount = Value('i',0)
    log = Event()
    close = Event()
    def __init__(self,inQ = None, loggerQ = None):
        Process.__init__(self)

    def display(self,msg):
        print('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg)

    def stop(self):
        self.close.set()

    def run():
        while not self.close.is_set():
            pass

# Add 2 photosensors, one for the queues and one for the lap; queue positions are logged as well and all is good. This is the easiest way to get both as long as the belt does is always at the same position, to do that put the encoder just after the animal with holes so the belt does not slip.
        
