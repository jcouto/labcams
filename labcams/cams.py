
#! /usr/bin/env python
# Camera classes for behavioral monitoring and single photon imaging.
# Creates separate processes for acquisition and saving to disk

import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
import numpy as np
from datetime import datetime
import time
import sys
from .io import CamWriter
from .utils import *
import ctypes
# 
# Has last frame on multiprocessing array
# 
class GenericCam(Process):
    name = None
    h = None
    w = None
    nframes = Value('i',0)
    close = Event()
    startTrigger = Event()
    stopTrigger = Event()
    saving = Event()

    def __init__(self, outQ = None,lock = None):
        Process.__init__(self)
        self.queue = outQ
    def initVariables(self):
        self.frame = Array('i',self.h*self.w)
    def stop_acquisition(self):
        self.close.set()

class DummyCam(GenericCam):
    def __init__(self,outQ = None,lock = None):
        super(DummyCam,self).__init__()
        self.h = 600
        self.w = 900
        self.frame = Array(ctypes.c_ubyte,
                           np.zeros([self.h,self.w],dtype = np.uint8).flatten())
    def run(self):
        # Open camera and do all settings magic
        # Start and stop the process between runs?
        display('Set {0} camera properties'.format(self.name))
        self.nframes.value = 0
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = np.uint8).reshape([self.h,self.w])
        while not self.close.is_set(): 
            # Acquire a frame and place in queue
            #display('running dummy cam {0}'.format(self.nframes.value))
            frame = (np.ones([self.h,self.w],dtype = np.uint8)*np.mod(self.nframes.value,128)).astype(ctypes.c_ubyte)
            buf[:,:] = frame[:,:]
            self.nframes.value += 1
            time.sleep(1./30)
        display('Stopped...')

'''
from pymba import *
def AVT_get_ids():
    with Vimba() as vimba:
        # get system object
        system = vimba.getSystem()
        # list available cameras (after enabling discovery for GigE cameras)
        if system.GeVTLIsPresent:
            system.runFeatureCommand("GeVDiscoveryAllOnce")
        time.sleep(0.2)
        camsIds = vimba.getCameraIds()
        cams = [vimba.getCamera(id) for id in camsIds]
        camsModel = [cam.deviceModelName() for cam in cams]
    return camsIds,camsModel

class AVTCam(Process):
    def __init__(self, camId = None, outQ = None,exposure = 29000,
                 frameRate = 30., gain = 10):
        super(AVTCam,self).__init__()
        if camId is None:
            display('Need to supply a camera ID.')
        self.camId = camId
        self.exposure = exposure
        self.frameRate = frameRate
        self.gain = gain
        with Vimba() as vimba:
            cam = vimba.getCamera(camId)
            # get a frame
            cam.acquisitionMode = 'SingleFrame'
            frame = cam.getFrame()
            frame.announceFrame()
            cam.startCapture()
            frame.queueFrameCapture()
            cam.runFeatureCommand('AcquisitionStart')
            cam.runFeatureCommand('AcquisitionStop')
            frame.waitFrameCapture()
            self.h = frame.height
            self.w = frame.width
            self.frame = frame.getBufferByteData()
            cam.endCapture()
            cam.revokeAllFrames()
            display("Got info from camera (name: {0}, uid: {1})".format(
                cam.DeviceModelName, cam.uid))
        self.initVariables()
        self.cameraReady = Event()
        
    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = np.uint8).reshape([self.h,self.w])
        with Vimba() as vimba:
            while not self.close.is_set():
                if not self.cameraReady.is_set():
                    # prepare camera
                    cam = vimba.getCamera(self.camId)
                    cam.EventSelector = 'FrameTrigger'
                    cam.EventNotification = 'On'
                    cam.PixelFormat = 'Mono8'
                    cameraFeatureNames = cam.getFeatureNames()
                    cam.AcquisitionMode = 'Continuous'
                    cam.AcquisitionFrameRateAbs = self.frameRate
                    cam.ExposureTimeAbs = self.exposureTime 
                    cam.GainRaw = self.gain 
                    cam.TriggerSource = 'FixedRate'
                    cam.TriggerMode = 'Off'
                    cam.TriggerSelector = 'FrameStart'
                    # create new frames for the camera
                    frames = [cam.getFrame() for f in xrange(100)]
                    for f in frames:
                        f.announceFrame()
                    self.cameraReady.set()
                    cam.startCapture()
                    for f in frames:
                        f.queueFrameCapture()
                    self.nframes.value = 0
                # Wait for trigger
                while not self.startTrigger.is_set():
                    time.sleep(0.001)
                cam.runFeatureCommand('AcquisitionStart')
                while not self.stopTrigger.is_set():
                    # run and acquire frames
                    for f in frames:
                        try:
                            f.waitFrameCapture(timeout = 10)
                            timestamp = ff._frame.timestamp
                            frameID = ff._frame.frameID
                            frame =  f.getBufferByteData()
                            f.queueFrameCapture()
                            if self.saving.is_set():
                                self.outQ.put([timestamp,frame])
                            buf[:,:] = frame[:,:]
                            self.nframe.value += 1
                        except VimbaException as err:
                            display('VimbaException: ' + err)
                cam.runFeatureCommand('AcquisitionStop')
                # Check if all frames are done...
                for f in frames:
                    try:
                        f.waitFrameCapture(timeout = 10)
                        timestamp = ff._frame.timestamp
                        frameID = ff._frame.frameID
                        frame =  f.getBufferByteData()
                        f.queueFrameCapture()
                        if self.saving.is_set():
                            self.outQ.put(frame)
                        self.frame = frame
                        self.nframe.value += 1
                    except VimbaException as err:
                display('VimbaException: ' + err)
                display('{4} delivered:{0},dropped:{1},saved:{4},time:{2}'.format(
                    cam.StatFrameDelivered,
                    cam.StatFrameDropped,
                    cam.StatTimeElapsed,
                    cam.DeviceModelName,
                    self.nframes.value))
                cam.endCapture()
                cam.revokeAllFrames()
                self.cameraReady.clear()
                self.startTrigger.clear()
                self.stopTrigger.clear()

class QCam(GenericCam):
    def __init__(self, outQ = None):
        super(GenericCam,self).__init__()
'''
