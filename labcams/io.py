#! /usr/bin/env python
# Classes to save files from a multiprocessing queue

import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
from datetime import datetime
import time
import sys
from .utils import display
import numpy as np
import os
from os.path import join as pjoin
from ctypes import c_long
from tifffile import TiffWriter as twriter

class TiffWriter(Process):
    def __init__(self,inQ = None, loggerQ = None,
                 expName = 'dummy',dataName = 'eyecam',
                 dataFolder=pjoin(os.path.expanduser('~'),'data'),
                 framesPerFile=500,
                 sleepTime = 1./30,
                 incrementRuns=True,
                 compression=None):
        Process.__init__(self)
        self.frameCount = Value(c_long,0)
        self.runs = Value('i',0)
        self.write = Event()
        self.close = Event()
        self.sleepTime = sleepTime # seconds
        self.framesPerFile = framesPerFile
        self.expName = expName
        self.dataFolder = dataFolder
        self.dataName = dataName
        self.folderName = None
        self.fileName = None
        self.incrementRuns = incrementRuns
        self.runs.value = 0
        self.compression = compression
        self.fd = None
        self.inQ = inQ
        self.today = datetime.today().strftime('%Y%m%d')

    def stop(self):
        self.write.clear()
        self.close.set()

    def closeFile(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None

    def openFile(self,nfiles = None):
        nfiles = self.nFiles
        folder = pjoin(self.dataFolder,self.dataName,self.expName)
        if not os.path.exists(folder):
            os.makedirs(folder)
        filename = pjoin(folder,'{0}_{1}_run{2:03d}_{3:08d}.tif'.format(
            self.today,
            self.expName,
            self.runs.value,
            nfiles))
        if not self.fd is None:
            self.closeFile()
        self.fd = twriter(filename)
        self.nFiles += 1
        display('Opened: '+ filename)
    def run(self):
        while not self.close.is_set():
            self.frameCount.value = 0
            self.nFiles = 0
#            if self.incrementRuns:
#                self.runs.value += 1
            
            while self.write.is_set():
                if self.fd is None:
                    self.openFile(self.nFiles) 
                while not self.inQ.empty():
                    buff = self.inQ.get()
                    try:
                        frame,(frameid,timestamp,) = buff
                    except:
                        print(buff)
                        continue
                    self.frameCount.value += 1
                    if np.mod(self.frameCount.value,self.framesPerFile)==0:
                        self.openFile()
                        display('Queue size: {0}'.format(self.inQ.qsize()))
                    self.fd.save(frame,compress=self.compression,
                                 description='id:{0};timestamp:{1}'.format(frameid,timestamp))
            # If queue is not empty, empty if to files.
            while not self.inQ.empty():
                buff = self.inQ.get()
                try:
                    frame,(frameid,timestamp,) = buff
                except:
                    print(buff)
                    continue
                self.frameCount.value += 1
                if np.mod(self.frameCount.value,self.framesPerFile)==0:
                    self.openFile()
                self.fd.save(frame,compress=self.compression,
                             description='id:{0};timestamp:{1}'.format(frameid,timestamp))

            self.closeFile()
            if not self.frameCount.value == 0:
                display("Wrote {0} frames on {1} ({2} files).".format(
                    self.frameCount.value,
                    self.dataName,
                    self.nFiles))
            #self.closeFile()
            # spare the processor just in case...
            time.sleep(self.sleepTime)

            
# Add 2 photosensors, one for the queues and one for the lap; queue positions are logged as well and all is good. This is the easiest way to get both as long as the belt does is always at the same position, to do that put the encoder just after the animal with holes so the belt does not slip.
        
