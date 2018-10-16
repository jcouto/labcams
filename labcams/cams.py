
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
from .io import TiffWriter
from .utils import *
import ctypes
try:
    import Image
except:
    from PIL import Image
# 
# Has last frame on multiprocessing array
# 
class GenericCam(Process):
    def __init__(self, outQ = None,lock = None):
        Process.__init__(self)
        self.name = ''

    def initVariables(self,dtype=np.uint8):
        if dtype == np.uint8:
            self.frame = Array(ctypes.c_ubyte,np.zeros([self.h,self.w],dtype = dtype).flatten())
        else:
            self.frame = Array(ctypes.c_ushort,np.zeros([self.h,self.w],dtype = dtype).flatten())
    def stop_acquisition(self):
        self.stopTrigger.set()

    def stop(self):
        self.closeEvent.set()
        self.stopTrigger.set()
        
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
        while not self.closeEvent.is_set(): 
            # Acquire a frame and place in queue
            #display('running dummy cam {0}'.format(self.nframes.value))
            frame = (np.ones([self.h,self.w],
                             dtype = np.uint8)*np.mod(self.nframes.value,128)).astype(ctypes.c_ubyte)
            buf[:,:] = frame[:,:]
            self.nframes.value += 1
            time.sleep(1./30)
        display('Stopped...')

# Allied Vision Technologies cameras
try:
    from pymba import *
except:
    pass

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
        camsModel = []
        for cam in cams:
            try:
                cam.openCamera()
                
            except:
                camsModel.append('')
                continue
            camsModel.append(cam.DeviceModelName)
    return camsIds,camsModel

class AVTCam(GenericCam):
    def __init__(self, camId = None, outQ = None,exposure = 29000,
                 frameRate = 30., gain = 10,frameTimeout = 100,
                 nFrameBuffers = 3,triggered = Event(),
                 triggerSource = 'Line1',
                 triggerMode = 'LevelHigh',
                 triggerSelector = 'FrameStart',
                 acquisitionMode = 'Continuous',
                 nTriggeredFrames = 1000):
        super(AVTCam,self).__init__()
        self.h = None
        self.w = None
        self.closeEvent = Event()
        self.startTrigger = Event()
        self.stopTrigger = Event()
        self.saving = Event()
        self.nframes = Value('i',0)
        if camId is None:
            display('Need to supply a camera ID.')
        self.camId = camId
        self.exposure = (1000000/int(frameRate)) - 150
        self.frameRate = frameRate
        self.gain = gain
        self.frameTimeout = frameTimeout
        self.triggerSource = triggerSource
        self.triggerSelector = triggerSelector
        print(triggerSelector)
        self.acquisitionMode = acquisitionMode
        self.nTriggeredFrames = nTriggeredFrames 
        self.nbuffers = nFrameBuffers
        self.queue = outQ
        self.dtype = np.uint8
        self.triggerMode = triggerMode
        with Vimba() as vimba:
            system = vimba.getSystem()
            if system.GeVTLIsPresent:
                system.runFeatureCommand("GeVDiscoveryAllOnce")
            time.sleep(0.2)
            cam = vimba.getCamera(camId)
            cam.openCamera()
            names = cam.getFeatureNames()
            # get a frame
            cam.acquisitionMode = 'SingleFrame'
            cam.AcquisitionFrameRateAbs = self.frameRate
            cam.ExposureTimeAbs =  self.exposure
            cam.GainRaw = self.gain 
            cam.TriggerSource = 'FixedRate'
            cam.TriggerMode = 'Off'
            cam.TriggerSelector = 'FrameStart'
            frame = cam.getFrame()
            frame.announceFrame()
            cam.startCapture()
            frame.queueFrameCapture()
            cam.runFeatureCommand('AcquisitionStart')
            frame.waitFrameCapture()
            cam.runFeatureCommand('AcquisitionStop')
            self.h = frame.height
            self.w = frame.width
            self.initVariables()
            framedata = np.ndarray(buffer = frame.getBufferByteData(),
                                   dtype = np.uint8,
                                   shape = (frame.height,
                                            frame.width)).copy()
            buf = np.frombuffer(self.frame.get_obj(),
                                dtype = np.uint8).reshape([self.h,self.w])

            buf[:,:] = framedata[:,:]
            cam.endCapture()
            cam.revokeAllFrames()
            display("Got info from camera (name: {0})".format(
                cam.DeviceModelName))
        self.cameraReady = Event()
        self.triggered = triggered
        if self.triggered.is_set():
            display('Triggered mode ON.')
            self.triggerSource = triggerSource
    
    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = np.uint8).reshape([self.h,self.w])
        self.closeEvent.clear()
        while not self.closeEvent.is_set():
            self.nframes.value = 0
            recorded_frames = []
            with Vimba() as vimba:
                system = vimba.getSystem()
                if system.GeVTLIsPresent:
                    system.runFeatureCommand("GeVDiscoveryAllOnce")
                time.sleep(0.2)
                # prepare camera
                cam = vimba.getCamera(self.camId)
                cam.openCamera()
                # cam.EventSelector = 'FrameTrigger'
                cam.EventNotification = 'On'
                cam.PixelFormat = 'Mono8'
                cameraFeatureNames = cam.getFeatureNames()
                #display('\n'.join(cameraFeatureNames))
                cam.AcquisitionFrameRateAbs = self.frameRate
                cam.ExposureTimeAbs =  self.exposure
                cam.GainRaw = self.gain
                cam.SyncOutSelector = 'SyncOut1'
                cam.SyncOutSource = 'FrameReadout'#'Exposing'
                if self.triggered.is_set():
                    cam.TriggerSource = self.triggerSource#'Line1'#self.triggerSource
                    cam.TriggerMode = 'On'
                    #cam.TriggerOverlap = 'Off'
                    cam.TriggerActivation = self.triggerMode #'LevelHigh'##'RisingEdge'
                    cam.AcquisitionMode = self.acquisitionMode
                    cam.TriggerSelector = self.triggerSelector
                    if self.acquisitionMode == 'MultiFrame':
                        cam.AcquisitionFrameCount = self.nTriggeredFrames
                        cam.TriggerActivation = self.triggerMode #'LevelHigh'##'RisingEdge'
                else:
                    print('Using no trigger.')
                    cam.AcquisitionMode = 'Continuous'
                    cam.TriggerSource = 'FixedRate'
                    cam.TriggerMode = 'Off'
                    cam.TriggerSelector = 'FrameStart'
                # create new frames for the camera
                frames = []
                for i in range(self.nbuffers):
                    frames.append(cam.getFrame())    # creates a frame
                    frames[i].announceFrame()
                cam.startCapture()
                for f,ff in enumerate(frames):
                    try:
                        ff.queueFrameCapture()
                    except:
                        #display('Queue frame error while getting cam ready: '+ str(f))
                        continue                    
                self.cameraReady.set()
                self.nframes.value = 0
                # Wait for trigger
                display('Camera waiting for software trigger.')
                while not self.startTrigger.is_set():
                    # limits resolution to 1 ms 
                    time.sleep(0.001)
                    if self.closeEvent.is_set():
                        break
                if self.closeEvent.is_set():
                    cam.endCapture()
                    try:
                        cam.revokeAllFrames()
                    except:
                        display('Failed to revoke frames.')
                    cam.closeCamera()
                    break

                cam.runFeatureCommand("GevTimestampControlReset")
                cam.runFeatureCommand('AcquisitionStart')
                if self.triggered.is_set():
                    cam.TriggerSelector = self.triggerSelector
                    cam.TriggerMode = 'On'
                    print(cam.TriggerSelector)
                    print(self.triggerSelector)
                #tstart = time.time()
                display('Started acquisition.')
                lastframeid = [-1 for i in frames]
                while not self.stopTrigger.is_set():
                    # run and acquire frames
                    for ibuf,f in enumerate(frames):
                        avterr = f.waitFrameCapture(timeout = self.frameTimeout)
                        if avterr == 0:
                            timestamp = f._frame.timestamp
                            frameID = f._frame.frameID
                            if not frameID in recorded_frames:
                                recorded_frames.append(frameID)
                                frame = np.ndarray(buffer = f.getBufferByteData(),
                                                   dtype = np.uint8,
                                                   shape = (f.height,
                                                            f.width)).copy()
                                newframe = frame.copy()
                                #display("Time {0} - {1}:".format(str(1./(time.time()-tstart)),self.nframes.value))
                                #tstart = time.time()
                            try:
                                f.queueFrameCapture()
                            except:
                                display('Queue frame failed: '+ str(f))
                                continue
                            self.nframes.value += 1
                            if self.saving.is_set():
                                if not frameID in lastframeid :
                                    self.queue.put((frame.copy(),(frameID,timestamp)))
                                    lastframeid[ibuf] = frameID
                            buf[:,:] = frame[:,:]
                        elif avterr == -12:
                            #display('VimbaException: ' +  str(avterr))        
                            break

                
                cam.runFeatureCommand('AcquisitionStop')
                display('Stopped acquisition.')
                # Check if all frames are done...
                for ibuf,f in enumerate(frames[::-1]):
                    try:
                        f.waitFrameCapture(timeout = 100)
                        timestamp = f._frame.timestamp
                        frameID = f._frame.frameID
                        frame = np.ndarray(buffer = f.getBufferByteData(),
                                           dtype = np.uint8,
                                           shape = (f.height,
                                                    f.width)).copy()
                        #f.queueFrameCapture()
                        if self.saving.is_set():
                            if not frameID in lastframeid :
                                self.queue.put((frame.copy(),(frameID,timestamp)))
                                lastframeid[ibuf] = frameID
                        self.nframes.value += 1
                        self.frame = frame
                    except VimbaException as err:
                        #display('VimbaException: ' + str(err))
                        pass
                display('{4} delivered:{0},dropped:{1},queued:{4},time:{2}'.format(
                    cam.StatFrameDelivered,
                    cam.StatFrameDropped,
                    cam.StatTimeElapsed,
                    cam.DeviceModelName,
                    self.nframes.value))
                cam.runFeatureCommand('AcquisitionStop')
                cam.endCapture()
                try:
                    cam.revokeAllFrames()
                except:
                    display('Failed to revoke frames.')
                cam.closeCamera()
                self.saving.clear()
                self.cameraReady.clear()
                self.startTrigger.clear()
                self.stopTrigger.clear()
                time.sleep(1.)
                display('Close event: {0}'.format(self.closeEvent.is_set()))

# QImaging cameras
try:
    import qimaging  as QCam
except:
    pass

class QImagingCam(GenericCam):
    def __init__(self, camId = None,
                 outQ = None,
                 exposure = 100000,
                 gain = 3500,frameTimeout = 100,
                 nFrameBuffers = 1,
                 binning = 2,
                 triggerType = 0,
                 triggered = Event()):
        '''
        Qimaging camera (tested with the Emc2 only!)
            triggerType (0=freerun,1=hardware,5=software)
        '''
        super(QImagingCam,self).__init__()
        self.h = None
        self.w = None
        self.closeEvent = Event()
        self.startTrigger = Event()
        self.stopTrigger = Event()
        self.saving = Event()
        self.nframes = Value('i',0)
        if camId is None:
            display('Need to supply a camera ID.')
            raise
        self.queue = outQ
        self.triggered = triggered
        self.triggerType = 0
        self.camId = camId
        self.estimated_readout_lag = 1257 # microseconds
        self.binning = binning
        self.exposure = exposure
        self.gain = gain
        self.dtype = np.uint16
        self.frameRate = 1./(self.exposure/1000.)
        self.frameTimeout = frameTimeout
        self.nbuffers = nFrameBuffers
        self.triggerType = triggerType
        QCam.ReleaseDriver()
        QCam.LoadDriver()
        cam = QCam.OpenCamera(QCam.ListCameras()[camId])
        if cam.settings.coolerActive:
            display('Qcam cooler active.')
        cam.settings.readoutSpeed=0 # 0=20MHz, 1=10MHz, 7=40MHz
        cam.settings.imageFormat = 'mono16'
        cam.settings.binning = self.binning
        cam.settings.emGain = gain
        cam.settings.triggerType = 0
        cam.settings.exposure = self.exposure - self.estimated_readout_lag
        cam.settings.blackoutMode=True
        cam.settings.Flush()
        cam.StartStreaming()
        frame = cam.GrabFrame()
        buf = np.frombuffer(frame.stringBuffer,dtype = np.uint16).reshape((frame.width,frame.height))
        self.h = frame.height
        self.w = frame.width

        cam.StopStreaming()
        cam.CloseCamera()
        QCam.ReleaseDriver()
        self.frame = Array(ctypes.c_ushort,np.zeros([self.w,self.h],dtype = np.uint16).flatten())

        framedata = np.ndarray(buffer = buf,
                               dtype = np.uint16,
                               shape = (self.w,
                                        self.h)).copy()
        buf[:,:] = framedata[:,:]
        #import pylab as plt
        #plt.imshow(buf)
        #plt.show()
        display("Got info from camera (name: {0})".format(camId))
        self.cameraReady = Event()

    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = np.uint16).reshape([self.w,self.h])
        QCam.ReleaseDriver()
        self.closeEvent.clear()
        while not self.closeEvent.is_set():
            self.nframes.value = 0
            QCam.LoadDriver()
            if not self.cameraReady.is_set():
                # prepare camera
                cam = QCam.OpenCamera(QCam.ListCameras()[self.camId])
                if cam.settings.coolerActive:
                    display('Qcam cooler active.')
                cam.settings.readoutSpeed=0 # 0=20MHz, 1=10MHz, 7=40MHz
                cam.settings.imageFormat = 'mono16'
                cam.settings.binning = self.binning
                cam.settings.emGain = self.gain
                cam.settings.exposure = self.exposure - self.estimated_readout_lag
                if self.triggered.is_set():
                    triggerType = self.triggerType
                else:
                    triggerType = 0
                cam.settings.triggerType = triggerType
                cam.settings.blackoutMode=True
                cam.settings.Flush()
                queue = QCam.CameraQueue(cam)
                display('Camera ready!')
                self.cameraReady.set()
                self.nframes.value = 0
                # Wait for trigger
            while not self.startTrigger.is_set():
                # limits resolution to 1 ms 
                time.sleep(0.001)
                if self.closeEvent.is_set():
                    break
            if self.closeEvent.is_set():
                queue.stop()
                del queue
                del cam
                break
            queue.start()
            #tstart = time.time()
            display('Started acquisition.')

            while not self.stopTrigger.is_set():
                # run and acquire frames
                try:
                    f = queue.get(True, 1)
                except queue.Empty:
                    continue
                self.nframes.value += 1
                frame = np.ndarray(buffer = f.stringBuffer,
                                   dtype = np.uint16,
                                   shape = (self.w,
                                            self.h)).copy()
                    
                #display("Time {0} - {1}:".format(str(1./(time.time()-tstart)),self.nframes.value))
                #tstart = time.time()
                timestamp = f.timeStamp
                frameID = f.frameNumber
                if self.saving.is_set():
                    self.queue.put((frame.reshape([self.h,self.w]),(frameID,timestamp)))
                buf[:,:] = frame[:,:]
                queue.put(f)

            queue.stop()
            del queue
            cam.settings.blackoutMode=False
            cam.settings.Flush()
            del cam
            self.saving.clear()
            self.cameraReady.clear()
            self.startTrigger.clear()
            self.stopTrigger.clear()
            QCam.ReleaseDriver()
            time.sleep(1)
            display('Stopped acquisition.')

    def stop(self):
        self.closeEvent.set()
        self.stop_acquisition()
