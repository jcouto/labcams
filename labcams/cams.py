#! /usr/bin/env python
# Camera classes for behavioral monitoring and single photon imaging.
# Creates separate processes for acquisition and queues frames
import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
import numpy as np
from datetime import datetime
import time
import sys
from .utils import *
import ctypes
try:
    import Image
except:
    from PIL import Image
import cv2

# 
# Has last frame on multiprocessing array
# 
class GenericCam(Process):
    def __init__(self, outQ = None,lock = None):
        Process.__init__(self)
        self.name = ''
        self.cam_id = None
        self.h = None
        self.w = None
        self.nchan = 1
        self.close_event = Event()
        self.start_trigger = Event()
        self.stop_trigger = Event()
        self.saving = Event()
        self.nframes = Value('i',0)
        self.queue = outQ
        self.cmd_queue = Queue()
        self.camera_ready = Event()
    def _init_variables(self,dtype=np.uint8):
        if dtype == np.uint8:
            cdtype = ctypes.c_ubyte
        else:
            cdtype = ctypes.c_ushort
        self.frame = Array(cdtype,np.zeros([self.h,self.w,self.nchan],dtype = dtype).flatten())
        self.img = np.frombuffer(
            self.frame.get_obj(),
            dtype = cdtype).reshape([self.h,self.w,self.nchan])

    def stop_acquisition(self):
        self.stop_trigger.set()

    def close(self):
        self.close_event.set()
        self.stop_acquisition()
        
# OpenCV camera; some functionality limited (like triggers)
class OpenCVCam(GenericCam):
    def __init__(self, camId = None, outQ = None,
                 frameRate = 30.,
                 triggered = Event(),
                 **kwargs):
        super(OpenCVCam,self).__init__(outQ = outQ)
        if camId is None:
            display('Need to supply a camera ID.')
        self.cam_id = camId
        self.frame_rate = float(frameRate)
        cam = cv2.VideoCapture(self.cam_id)
        if not self.frame_rate == float(0):
            res = cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            res = cam.set(cv2.CAP_PROP_EXPOSURE,1./self.frame_rate)
        else:
            res = cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        ret_val, frame = cam.read()
        frame = frame
        self.h = frame.shape[0]
        self.w = frame.shape[1]
        self.nchan = frame.shape[2]
        self.dtype = frame.dtype

        self._init_variables(dtype = self.dtype)
        display("Got info from camera (name: {0})".format(
            'openCV'))
        cam.release()
        self.triggered = triggered
        if self.triggered.is_set():
            display('[OpenCV {0}] Triggered mode ON.'.format(self.cam_id))
            self.triggerSource = triggerSource
    
    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = self.dtype).reshape([self.h,self.w,self.nchan])
        self.close_event.clear()
        
        while not self.close_event.is_set():
            self.nframes.value = 0
            lastframeid = -1
            cam = cv2.VideoCapture(self.cam_id)
            if not self.frame_rate == float(0):
                res = cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
                res = cam.set(cv2.CAP_PROP_EXPOSURE,1./float(self.frame_rate))
            else:
                res = cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            self.camera_ready.set()
            self.nframes.value = 0
            # Wait for trigger
            display('OpenCV camera [{0}] waiting for software trigger.'.format(self.cam_id))
            while not self.start_trigger.is_set():
                # limits resolution to 1 ms 
                time.sleep(0.001)
                if self.close_event.is_set():
                    break
            if self.close_event.is_set():
                break
            display('OpenCV [{0}] - Started acquisition.'.format(self.cam_id))
            self.camera_ready.clear()
            while not self.stop_trigger.is_set():
                frameID = self.nframes.value
                ret_val, frame = cam.read()
                timestamp = time.time()
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.nframes.value += 1
                if self.saving.is_set():
                    if not frameID == lastframeid :
                        self.queue.put((frame.copy(),(frameID,timestamp)))
                        lastframeid = frameID
                buf[...] = frame[...]
            cam.release()
            display('OpenCV [{0}] - Stopped acquisition.'.format(self.cam_id))
            self.saving.clear()
            self.start_trigger.clear()
            self.stop_trigger.clear()
            display('OpenCV {0} - Close event: {1}'.format(self.cam_id,
                                                           self.close_event.is_set()))
        
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
        for camid,cam in zip(camsIds,cams):
            try:
                cam.openCamera()
                
            except:
                camsModel.append('')
                continue
            camsModel.append('{0} {1} {2}'.format(cam.DeviceModelName,
                                                  cam.DevicePartNumber,
                                                  cam.DeviceID))
            #print(camsModel)
    return camsIds,camsModel

class AVTCam(GenericCam):
    def __init__(self, camId = None, outQ = None,exposure = 29000,
                 frameRate = 30., gain = 10,frameTimeout = 100,
                 nFrameBuffers = 10,
                 triggered = Event(),
                 triggerSource = 'Line1',
                 triggerMode = 'LevelHigh',
                 triggerSelector = 'FrameStart',
                 acquisitionMode = 'Continuous',
                 nTriggeredFrames = 1000,
                 frame_timeout = 100):
        super(AVTCam,self).__init__()
        if camId is None:
            display('Need to supply a camera ID.')
        self.cam_id = camId
        self.exposure = (1000000/int(frameRate)) - 150
        self.frame_rate = frameRate
        self.gain = gain
        self.frameTimeout = frameTimeout
        self.triggerSource = triggerSource
        self.triggerSelector = triggerSelector
        self.acquisitionMode = acquisitionMode
        self.nTriggeredFrames = nTriggeredFrames 
        self.nbuffers = nFrameBuffers
        self.queue = outQ
        self.frame_timeout = frame_timeout
        self.triggerMode = triggerMode
        self.tickfreq = float(1.0)
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
            cam.AcquisitionFrameRateAbs = self.frame_rate
            cam.ExposureTimeAbs =  self.exposure
            self.tickfreq = float(cam.GevTimestampTickFrequency)
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
            self.dtype = frame.dtype
            self._init_variables(dtype = self.dtype)
            framedata = np.ndarray(buffer = frame.getBufferByteData(),
                                   dtype = self.dtype,
                                   shape = (frame.height,
                                            frame.width)).copy()
            buf = np.frombuffer(self.frame.get_obj(),
                                dtype = self.dtype).reshape([self.h,self.w])

            buf[:,:] = framedata[:,:]
            cam.endCapture()
            cam.revokeAllFrames()
            display("AVT [{1}] = Got info from camera (name: {0})".format(
                cam.DeviceModelName,self.cam_id))
        self.triggered = triggered
        if self.triggered.is_set():
            display('AVT [{0}] - Triggered mode ON.'.format(self.cam_id))
            self.triggerSource = triggerSource
    
    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = self.dtype).reshape([self.h,self.w])
        self.close_event.clear()
        while not self.close_event.is_set():
            self.nframes.value = 0
            recorded_frames = []
            with Vimba() as vimba:
                system = vimba.getSystem()
                if system.GeVTLIsPresent:
                    system.runFeatureCommand("GeVDiscoveryAllOnce")
                time.sleep(0.2)
                # prepare camera
                cam = vimba.getCamera(self.cam_id)
                cam.openCamera()
                # cam.EventSelector = 'FrameTrigger'
                cam.EventNotification = 'On'
                cam.PixelFormat = 'Mono8'
                cameraFeatureNames = cam.getFeatureNames()
                #display('\n'.join(cameraFeatureNames))
                cam.AcquisitionFrameRateAbs = self.frame_rate
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
                    display('[Cam - {0}] Using no trigger.'.format(self.cam_id))
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
                        display('Queue frame error while getting cam ready: '+ str(f))
                        continue                    
                self.camera_ready.set()
                self.nframes.value = 0
                # Wait for trigger
                display('AVT [{0}] - Camera waiting for software trigger.'.format(self.cam_id))
                while not self.start_trigger.is_set():
                    # limits resolution to 1 ms 
                    time.sleep(0.001)
                    if self.close_event.is_set():
                        break
                display('AVT [{0}] - Received software trigger.'.format(
                    self.cam_id))

                if self.close_event.is_set():
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
                #tstart = time.time()
                lastframeid = [-1 for i in frames]
                self.camera_ready.clear()
                while not self.stop_trigger.is_set():
                    # run and acquire frames
                    #sortedfids = np.argsort([f._frame.frameID for f in frames])
                    for ibuf in range(self.nbuffers):
                        f = frames[ibuf]
                        avterr = f.waitFrameCapture(timeout = self.frameTimeout)
                        if avterr == 0:
                            timestamp = f._frame.timestamp/self.tickfreq
                            frameID = f._frame.frameID
                            #print('Frame id:{0}'.format(frameID))
                            if not frameID in recorded_frames:
                                recorded_frames.append(frameID)
                                frame = np.ndarray(buffer = f.getBufferByteData(),
                                                   dtype = self.dtype,
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
                for ibuf in range(self.nbuffers):
                    f = frames[ibuf]
                    try:
                        f.waitFrameCapture(timeout = self.frame_timeout)
                        timestamp = f._frame.timestamp/self.tickfreq
                        frameID = f._frame.frameID
                        frame = np.ndarray(buffer = f.getBufferByteData(),
                                           dtype = self.dtype,
                                           shape = (f.height,
                                                    f.width)).copy()
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
                self.start_trigger.clear()
                self.stop_trigger.clear()
                time.sleep(0.2)
                display('AVT [{0}] - Close event: {1}'.format(
                    self.cam_id,
                    self.close_event.is_set()))

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
        if camId is None:
            display('Need to supply a camera ID.')
            raise
        self.queue = outQ
        self.triggered = triggered
        self.triggerType = 0
        self.cam_id = camId
        self.estimated_readout_lag = 1257 # microseconds
        self.binning = binning
        self.exposure = exposure
        self.gain = gain
        self.frame_rate = 1./(self.exposure/1000.)
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
        self.dtype = frame.dtype
        buf = np.frombuffer(frame.stringBuffer,dtype = self.dtype).reshape((frame.width,frame.height))
        self.h = frame.height
        self.w = frame.width

        cam.StopStreaming()
        cam.CloseCamera()
        QCam.ReleaseDriver()
        self.initVariables(dtype = self.dtype)

        display("Got info from camera (name: {0})".format(camId))
        self.camera_ready = Event()

    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = np.uint16).reshape([self.w,self.h])
        QCam.ReleaseDriver()
        self.close_event.clear()
        while not self.close_event.is_set():
            self.nframes.value = 0
            QCam.LoadDriver()
            if not self.camera_ready.is_set():
                # prepare camera
                cam = QCam.OpenCamera(QCam.ListCameras()[self.cam_id])
                if cam.settings.coolerActive:
                    display('Qcam - cooler active.')
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
                display('QCam - Camera ready!')
                self.camera_ready.set()
                self.nframes.value = 0
                # Wait for trigger
            while not self.start_trigger.is_set():
                # limits resolution to 1 ms 
                time.sleep(0.001)
                if self.close_event.is_set():
                    break
            if self.close_event.is_set():
                queue.stop()
                del queue
                del cam
                break
            queue.start()
            #tstart = time.time()
            display('QCam - Started acquisition.')
            self.camera_ready.clear()
            while not self.stop_trigger.is_set():
                # run and acquire frames
                try:
                    f = queue.get(True, 1)
                except queue.Empty:
                    continue
                self.nframes.value += 1
                frame = np.ndarray(buffer = f.stringBuffer,
                                   dtype = self.dtype,
                                   shape = (self.w,
                                            self.h)).copy()
                    
                #display("Time {0} - {1}:".format(str(1./(time.time()-tstart)),self.nframes.value))
                #tstart = time.time()
                timestamp = f.timeStamp
                frameID = f.frameNumber
                if self.saving.is_set():
                    self.queue.put((frame.reshape([self.h,self.w]),
                                    (frameID,timestamp)))
                buf[:,:] = frame[:,:]
                queue.put(f)

            queue.stop()
            del queue
            cam.settings.blackoutMode=False
            cam.settings.Flush()
            del cam
            self.saving.clear()
            self.start_trigger.clear()
            self.stop_trigger.clear()
            QCam.ReleaseDriver()
            time.sleep(1)
            display('QCam - Stopped acquisition.')

    def stop(self):
        self.close_event.set()
        self.stop_acquisition()
