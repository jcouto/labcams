
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

# 
# Has last frame on multiprocessing array
# 
class GenericCam(Process):
    name = None
    h = None
    w = None
    frameCount = Value('i',0)
    close = Event()
    def __init__(self, outQ = None, trigger='software'):
        Process.__init__(self)
        self.queue = outQ
        self.acquiring = Event()
        self.trigger = trigger
        # Image dimensions
    def initVariables(self):
        self.lastframe = Array('i',[self.h,self.w])

    def stop_acquisition(self):
        self.close.set()

    def run(self):
        # Open camera and do all settings magic
        # Start and stop the process between runs?
        display('Set {0} camera properties'.format(self.name))
        self.frameCount.value = 0
        while not self.close.is_set(): 
            # Acquire a frame and place in queue
            print('{0} - frame {1}'.format(self.frameCount))
            self.frameCount.value += 1

class DummyCam(GenericCam):
    def __init__(self,outQ = None):
        super(DummyCam,self).__init__()
        self.h = 400
        self.w = 500
        self.initVariables()

from pymba import *
class AVTCam(Process):
    def __init__(self, camera = 0, outQ = None):
        super(AVTCam,self).__init__()        
        self.vimba = Vimba()
        self.vimba.startup()
        system = vimba.getSystem()
        if system.GeVTLIsPresent:
            system.runFeatureCommand("GeVDiscoveryAllOnce")
        time.sleep(0.2)
        cameraIds = vimba.getCameraIds()
        self.camera = vimba.getCamera(cameraIds[0])
            
        display("Connected to AVT camera (name: {0}, uid: {1})".format(
            self.camera.DeviceModelName, self.camera.uid))
        # Get the frame shape
        # Get the frame rate, exposure and all that jazz
        
            
debug = True
if not debug:
    class QCam(GenericCam):
        def __init__(self, outQ = None):
            GenericCam.__init__(self)
        
        

    from pvapi import Camera as PvCam
    from pvapi import PvAPI

    def listAVTCams():
        driver = PvAPI(libpath=os.path.dirname(sys.modules[__name__].__file__))
        for d in driver.camera_list():
            display(str(d))
    

    class AVTCam(Process):
        def __init__(self, camera = 0, outQ = None):
            self.driver = PvAPI(libpath=os.path.dirname(
                    sys.modules[__name__].__file__))
            self.camera = PvCam(self.driver, camera)
            display("Connected to PvAPI camera (name: {0}, uid: {1})".format(
                    self.camera.name, self.camera.uid))
            # Get the frame shape
            # Get the frame rate, exposure and all that jazz
            self.w,self.h = self.camera.attr_uint32_get("ImageSize")
            
            GenericCam.__init__(self)

        
        
