#! /usr/bin/env python
# Classes to save files from a multiprocessing queue

import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
from datetime import datetime
import time
import sys
from .utils import display

class TiffWriter(Process):
    def __init__(self,inQ = None, loggerQ = None,
                 expName = 'dummy',dataName = 'eyecam',
                 dataFolder='~/data/',
                 framesPerFile=1000,
                 incrementRuns=True):
        Process.__init__(self)
        self.frameCount = Value('i',0)
        self.write = Event()
        self.close = Event()
        self.sleepTime = 1./30 # seconds
        self.framesPerFile = framesPerFile
        self.expName = expName
        self.dataName = dataName
        self.folderName = None
        self.fileName = None
        self.incrementRuns = incrementRuns
        self.run = 0
        self.compression = None
        self.fd = None
        self.inQ = inQ
    def stop(self):
        self.write.clear()
        self.close.set()
        
    def run():
        while not self.close.is_set():
            self.frameCount.value = 0
            self.nFiles = 0
            while self.write.is_set():
                while not self.inQ.is_empty():
                    buff = self.inQ.get()
                    if frame is None:
                        display('Got none frame.')
                        continue
                    frame,timestamp = buff
                    self.frameCount.value += 1
                    if np.mod(self.frameCount.value,self.framesPerFile):
                        self.closeFile()
                        self.nFiles += 1
                    if self.fd is None:
                        self.openFile()
                    self.write_image(frame,compression=self.compression)
                time.sleep(self.sleepTime)
            # If queue is not empty, empty if to file.
            while not self.inQ.is_empty():
                buff = self.inQ.get()
                if frame is None:
                    display('Got an empty frame ?!?')
                    continue
                frame,timestamp = buff
                self.frameCount.value += 1
                if np.mod(self.frameCount.value,self.framesPerFile):
                    self.closeFile()
                    self.nFiles += 1
                if self.fd is None:
                    self.openFile()
                self.write_image(frame,compression=self.compression)
                display("Wrote {0} frames on {1} ({2} files).".format(
                self.frameCount.value,
                self.dataName,
                self.nFiles))
            self.closeFile()
            if self.incrementRuns:
                self.run += 1
            # spare the processor just in case...
            time.sleep(self.sleepTime)


            
# Add 2 photosensors, one for the queues and one for the lap; queue positions are logged as well and all is good. This is the easiest way to get both as long as the belt does is always at the same position, to do that put the encoder just after the animal with holes so the belt does not slip.
        
