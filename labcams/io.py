#! /usr/bin/env python
# Classes to save files from a multiprocessing queue

import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
from ctypes import c_long, c_char_p
from datetime import datetime
import time
import sys
from .utils import display
import numpy as np
import os
from os.path import join as pjoin
from tifffile import TiffWriter as twriter
VERSION = '0.1b'
class TiffWriter(Process):
    def __init__(self,inQ = None, loggerQ = None,
                 filename = 'dummy\\run',
                 dataName = 'eyecam',
                 dataFolder='C:\\data',#pjoin(os.path.expanduser('~'),'data'),
                 framesPerFile=256,
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
        self.filename = Array('u',' ' * 1024)
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
        self.logfile = None
        
    def setFilename(self,filename):
        self.write.clear()
        for i in range(len(self.filename)):
            self.filename[i] = ' '
        for i in range(len(filename)):
            self.filename[i] = filename[i]
        display('Filename updated: ' + self.getFilename())
    
    def getFilename(self):
        return str(self.filename[:]).strip(' ')
        
    def stop(self):
        self.write.clear()
        self.close.set()
        self.join()

    def closeFile(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None
    
    def openFile(self,nfiles = None):
        nfiles = self.nFiles
        folder = pjoin(self.dataFolder,self.dataName,self.getFilename())
        if not os.path.exists(folder):
            os.makedirs(folder)
        filename = pjoin(folder,'{0}_run{1:03d}_{2:08d}.tif'.format(
            self.today,
            self.runs.value,
            nfiles))
        if not self.fd is None:
            self.closeFile()
        self.fd = twriter(filename)
        # Create a log file
        if self.logfile is None:
            self.logfile = open(pjoin(folder,'{0}_run{1:03d}.camlog'.format(
                self.today,
                self.runs.value)),'w')
            self.logfile.write('# Camera: {0} log file'.format(self.dataName) + '\n')
            self.logfile.write('# Date: {0}'.format(datetime.today().strftime('%d-%m-%Y')) + '\n')
            self.logfile.write('# labcams version: {0}'.format(VERSION) + '\n')                
            self.logfile.write('# Log header:' + 'frame_id,timestamp' + '\n')
        self.nFiles += 1
        display('Opened: '+ filename)        
        self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + filename + '\n')
    def run(self):
        while not self.close.is_set():
            self.frameCount.value = 0
            self.nFiles = 0
            while self.write.is_set():
                if not self.inQ.empty():
                    buff = self.inQ.get()
                    try:
                        frame,(frameid,timestamp,) = buff
                    except:
                        display(buff)
                        continue
                    if np.mod(self.frameCount.value,self.framesPerFile)==0:
                        self.openFile()
                        display('Queue size: {0}'.format(self.inQ.qsize()))
                        self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - '
                                           + 'Queue: {0}'.format(self.inQ.qsize())
                                           + '\n')
                    self.fd.save(frame,
                                 compress=self.compression,
                                 description='id:{0};timestamp:{1}'.format(frameid,
                                                                           timestamp))
                    self.logfile.write('{0},{1}\n'.format(frameid,
                                                          timestamp))
                    
                    self.frameCount.value += 1
            # If queue is not empty, empty if to files.
            if not self.inQ.empty():
                while not self.inQ.empty():
                    buff = self.inQ.get()
                    try:
                        frame,(frameid,timestamp,) = buff
                    except:
                        display(buff)
                        continue
                    if np.mod(self.frameCount.value,self.framesPerFile)==0:
                        self.openFile()
                    self.fd.save(frame,compress=self.compression,
                                 description='id:{0};timestamp:{1}'.format(frameid,timestamp))
                    self.logfile.write('{0},{1}\n'.format(frameid,
                                                          timestamp))
                    self.frameCount.value += 1
                display('Queue is empty.')
            if not self.logfile is None:
                self.closeFile()
                self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' +
                                "Wrote {0} frames on {1} ({2} files).".format(
                                    self.frameCount.value,
                                    self.dataName,
                                    self.nFiles) + '\n')
                self.logfile.close()
                self.logfile = None
                self.runs.value += 1
            if not self.frameCount.value == 0:
                display("Wrote {0} frames on {1} ({2} files).".format(
                    self.frameCount.value,
                    self.dataName,
                    self.nFiles))
            # self.closeFile()
            # spare the processor just in case...
            time.sleep(self.sleepTime)
            
