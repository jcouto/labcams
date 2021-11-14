#  labcams - https://jpcouto@bitbucket.org/jpcouto/labcams.git
# Copyright (C) 2020 Joao Couto - jpcouto@gmail.com
#
#  This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pypylon import pylon

from .cams import *
# Adapted from the pylon examples

class BaslerCam(GenericCam):
    def __init__(self,
                 camId = None,
                 outQ = None,
                 binning = None,
                 frameRate = None,
                 exposure = None,
                 gain = None,
                 gamma = None,
                 roi = [],
                 pxformat = 'Mono8',
                 triggerSource = np.uint16(0),
                 outputs = [],
                 triggered = Event(),
                 hardware_trigger = None,
                 recorderpar=None,
                 **kwargs):
        super(BaslerCam,self).__init__(outQ = outQ, recorderpar=recorderpar)
        self.drivername = 'Basler'
        self.hardware_trigger = hardware_trigger
        if camId is None:
            display('[Basler] - Need to supply a camera ID.')
        self.drv = None
        self.cam_id = camId
        if not len(roi):
            roi = [None,None,None,None]
        self.pxformat = pxformat
        self.gamma = gamma
        self.triggered = triggered
        self.outputs = outputs
        self.binning = binning
        self.exposure = exposure
        self.frame_rate = frameRate
        self.gain = gain
        self.roi = roi
        frame = self.get_one()
        self.h = frame.shape[0]
        self.w = frame.shape[1]
        self.nchan = 1
        if len(frame.shape) == 3:
            self.nchan = frame.shape[2] 
        self.dtype = frame.dtype
        self._init_variables(self.dtype)

        self.img[:] = np.reshape(frame,self.img.shape)[:]
        display("[Basler {0}] - got info from camera.".format(self.cam_id))

    def cam_info(self,cam):
        pass
    def _init_controls(self):
        self.ctrevents = dict(
            gain=dict(
                function = 'set_gain',
                widget = 'float',
                variable = 'gain',
                units = 'db',
                type = 'float',
                min = 0,
                max = 20,
                step = 1),
            exposure=dict(
                function = 'set_exposure',
                widget = 'float',
                variable = 'exposure',
                units = 'us',
                type = 'float',
                min = 10,
                max = 20000000000000,
                step = 100))

    def get_one(self):
        self._cam_init()
        frame = self.cam.GrabOne(int(self.cam.ExposureTime.GetValue()*2))
        self.cam.Close()
        del self.cam
        return frame.Array
    
    def set_binning(self,binning = 1):
        if binning is None:
           return 
        self.binning = int(binning)
        if not self.cam is None:
            self.cam.BinningVertical = self.binning
            self.cam.BinningHorizontal = self.binning

    def set_exposure(self,exposure=None):
        '''Set the exposure time is in us'''        
        if exposure is None:
            if not self.cam is None:
                self.exposure = self.cam.ExposureTime.GetValue()
            return
        self.exposure = exposure
        if not self.cam is None:
            self.cam.ExposureTime = self.exposure
            
    def set_gain(self,gain = 1):
        '''Set the gain is in dB'''
        if gain is None:
            return
        self.gain = gain
        if not self.cam is None:
            self.cam.Gain.SetValue(self.gain)
            
    def _cam_init(self):
        self.cam = pylon.InstantCamera(
            pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.cam.Open()

        # Set the trigger and exposure off so to be able to set other parameters
        self.set_binning(self.binning)
        # reset size first
        self.set_exposure(self.exposure)
        self.set_gain(self.gain)
        self.lastframeid = -1
        self.nframes.value = 0
        self.camera_ready.set()
        self.prev_ts = 0
        self.lasttime = time.time()
        
    def _cam_startacquisition(self):
        display('Basler [{0}] - Started acquitition.'.format(self.cam_id))
        self.cam.StartGrabbing(pylon.GrabStrategy_OneByOne)
        
    def _cam_stopacquisition(self):
        '''stop camera acq'''
        if not self.hardware_trigger is None:
            #if 'out_line' in self.hardware_trigger:
            self.cam.StopGrabbing()

    def _cam_loop(self):
        if self.cam.IsGrabbing():
            res = self.cam.RetrieveResult(int(self.cam.ExposureTime.Value*1.1),
                                          pylon.TimeoutHandling_ThrowException)
            if res.GrabSucceeded():
                frame = res.Array
                frameID = res.GetImageNumber()
                timestamp = res.GetTimeStamp()
                linestat = self.cam.LineStatus()
            else:
                display('[Basler] - Grab failed?')
                res.Release()
                return None,(None,None,None)
            res.Release()
            self.nframes.value = frameID
            return frame,(frameID,timestamp,linestat)
        else:
            return None,(None,None,None)

    def _cam_close(self):
        if not self.cam is None:
            try:
                self._cam_stopacquisition()
                display('Basler [{0}] - Stopped acquitition.'.format(self.cam_id))          
            except:
                pass
            self.cam.Close()
            del self.cam            

