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
from glob import glob
from os.path import join as pjoin
from tifffile import TiffWriter as twriter
from tifffile import imread,TiffFile
import pandas as pd

VERSION = '0.2'
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
        self.fd = None
        self.inQ = inQ
        self.today = datetime.today().strftime('%Y%m%d')
        self.logfile = None
        self.tracker = None
        self.trackerpar = None
        self.trackerfile = None
        self.trackerFlag = Event()

        if not compression is None:
            if compression > 0:
                self.compression = compression
        
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
            self.logfile.write('# Camera: {0} log file'.format(
                self.dataName) + '\n')
            self.logfile.write('# Date: {0}'.format(
                datetime.today().strftime('%d-%m-%Y')) + '\n')
            self.logfile.write('# labcams version: {0}'.format(
                VERSION) + '\n')                
            self.logfile.write('# Log header:' + 'frame_id,timestamp' + '\n')
        self.nFiles += 1
        display('Opened: '+ filename)        
        self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + filename + '\n')
        if self.trackerFlag.is_set():
            # MPTRACKER hack
            display('Running eye tracker.')
            if self.tracker is None:
                import cv2
                cv2.setNumThreads(1)
                from mptracker import MPTracker
                self.tracker = MPTracker()
                self._updateTrackerPar()
            if self.trackerfile is None:
                self.trackerfile = open(pjoin(
                    folder,
                    '{0}_run{1:03d}.eyetracker'.format(
                        self.today,
                        self.runs.value)),'w')
                self.trackerfile.write('# [' +
                                       datetime.today().strftime(
                                           '%y-%m-%d %H:%M:%S')+'] - ' +
                                       'opening file.')

        else:
            self.tracker = None
            self._close_trackerfile()
            
    def _close_trackerfile(self):
        if not self.trackerfile is None:
            self.trackerfile.write('# [' +
                                   datetime.today().strftime(
                                       '%y-%m-%d %H:%M:%S')+'] - ' +
            'closing file.')
            self.trackerfile.close()
            self.trackerfile = None
    def _updateTrackerPar(self):
        if not self.trackerpar is None and not self.tracker is None:
            print('Updating eye tracker parameters.')
            for k in self.trackerpar:
                self.tracker.parameters[k] = self.trackerpar[k]
    def getFromQueueAndSave(self):
        buff = self.inQ.get()
        if buff[0] is None:
            # Then parameters were passed to the queue
            if type(buff[1]) is dict():
                self.trackerpar = buff[1]
                self._updateTrackerPar()
            return None,None
        frame,(frameid,timestamp,) = buff
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
        return frameid,frame
    def closeRun(self):
        if not self.logfile is None:
            self.closeFile()
            self.logfile.write('# [' +
                               datetime.today().strftime(
                                   '%y-%m-%d %H:%M:%S')+'] - ' +
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
        if not self.trackerfile is None:
            self._close_trackerfile()

    def run(self):
        while not self.close.is_set():
            self.frameCount.value = 0
            self.nFiles = 0
            while self.write.is_set():
                if not self.inQ.empty():
                    frameid,frame = self.getFromQueueAndSave()
                    if not frameid is None and not self.tracker is None:
                        res = self.tracker.apply(frame)
            # If queue is not empty, empty if to files.
            if not self.inQ.empty():
                frameid,frame = self.getFromQueueAndSave()
                if not frame is None and not self.tracker is None:
                    res = self.tracker.apply(frame)
                    #(outimg,(maxL[0] + x1,
                    #         maxL[1] + y1),pupil_pos,
                    # (short_axis/2.,long_axis/2.),
                    # (short_axis,long_axis,phi))
            #display('Queue is empty.')
            self.closeRun()
            # self.closeFile()
            # spare the processor just in case...
            time.sleep(self.sleepTime)
            
def parseCamLog(fname,convertToSeconds = True):
    logheaderkey = '# Log header:'
    comments = []
    with open(fname,'r') as fd:
        for line in fd:
            if line.startswith('#'):
                line = line.strip('\n').strip('\r')
                comments.append(line)
                if line.startswith(logheaderkey):
                    columns = line.strip(logheaderkey).strip(' ').split(',')

    logdata = pd.read_csv(fname,names = columns, 
                          delimiter=',',
                          header=None,
                          comment='#',
                          engine='c')
    if convertToSeconds and '1photon' in comments[0]:
        logdata['timestamp'] /= 10000.
    return logdata,comments


class TiffStack(object):
    def __init__(self,filenames):
        if type(filenames) is str:
            filenames = np.sort(glob(pjoin(filenames,'*.tif')))
        
        assert type(filenames) in [list,np.ndarray], 'Pass a list of filenames.'
        self.filenames = filenames
        for f in filenames:
            assert os.path.exists(f), f + ' not found.'
        # Get an estimate by opening only the first and last files
        framesPerFile = []
        self.files = []
        for i,fn in enumerate(self.filenames):
            if i == 0 or i == len(self.filenames)-1:
                self.files.append(TiffFile(fn))
            else:
                self.files.append(None)                
            f = self.files[-1]
            if i == 0:
                dims = f.series[0].shape
                self.shape = dims
            elif i == len(self.filenames)-1:
                dims = f.series[0].shape
            framesPerFile.append(np.int64(dims[0]))
        self.framesPerFile = np.array(framesPerFile, dtype=np.int64)
        self.framesOffset = np.hstack([0,np.cumsum(self.framesPerFile[:-1])])
        self.nFrames = np.sum(framesPerFile)
        self.curfile = 0
        self.curstack = self.files[self.curfile].asarray()
        N,self.h,self.w = self.curstack.shape[:3]
        self.dtype = self.curstack.dtype
        self.shape = (self.nFrames,self.shape[1],self.shape[2])
    def getFrameIndex(self,frame):
        '''Computes the frame index from multipage tiff files.'''
        fileidx = np.where(self.framesOffset <= frame)[0][-1]
        return fileidx,frame - self.framesOffset[fileidx]
    def __getitem__(self,*args):
        index  = args[0]
        if not type(index) is int:
            Z, X, Y = index
            if type(Z) is slice:
                index = range(Z.start, Z.stop, Z.step)
            else:
                index = Z
        else:
            index = [index]
        img = np.empty((len(index),self.h,self.w),dtype = self.dtype)
        for i,ind in enumerate(index):
            img[i,:,:] = self.getFrame(ind)
        return np.squeeze(img)
    def getFrame(self,frame):
        ''' Returns a single frame from the stack '''
        fileidx,frameidx = self.getFrameIndex(frame)
        if not fileidx == self.curfile:
            if self.files[fileidx] is None:
                self.files[fileidx] = TiffFile(self.filenames[fileidx])
            self.curstack = self.files[fileidx].asarray()
            self.curfile = fileidx
        return self.curstack[frameidx,:,:]
    def __len__(self):
        return self.nFrames
