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
        if len(frame.shape) > 2:
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
                buf[:] = frame[:]
            cam.release()
            display('OpenCV [{0}] - Stopped acquisition.'.format(self.cam_id))
            self.saving.clear()
            self.start_trigger.clear()
            self.stop_trigger.clear()
            display('OpenCV {0} - Close event: {1}'.format(self.cam_id,
                                                           self.close_event.is_set()))
        
