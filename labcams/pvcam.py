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

from .cams import *
from datetime import datetime
from pyvcam import pvc 
from pyvcam.camera import Camera

class PVCam(GenericCam):
    def __init__(self,
                 cam_id = None,
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,                 
                 out_q = None,
                 binning = None,
                 exposure = 100,
                 dtype = np.uint16,
                 use_camera_parameters = True,
                 trigger_source = np.uint16(2),
                 hardware_trigger = None,
                 dllpath = None,
                 recorderpar = None,
                 **kwargs):
        super(PVCam,self).__init__(cam_id = cam_id,
                                    out_q = out_q,
                                    start_trigger = start_trigger,
                                    stop_trigger = stop_trigger,
                                    save_trigger = save_trigger,
                                    recorderpar=recorderpar)
        self.armed = False
        self.drivername = 'PVCam'
        self.trigerMode = 0
        self.exposure = exposure
        self.binning = binning
        self.dtype = dtype
        self.camopen()

        ###
        frame = self.get_one()
        self.camclose()
        self.cam = None
        self.h.value = frame.shape[0]
        self.w.value = frame.shape[1]

        if len(frame.shape) == 2:
            self.nchan.value = 1
        else:
            self.nchan.value = frame.shape
        self.dtype = dtype
        self._init_variables(dtype)

        self.hardware_trigger = hardware_trigger
        if self.hardware_trigger is None:
            self.hardware_trigger = Event()

        self.trigger_source = trigger_source
        self.frame_rate = 1000.0/float(self.exposure)
        self.fs.value = self.frame_rate

        self._dll = None
        display("[PVCam {0}] Got info from camera".format(
             self.cam_id))

    def _init_controls(self):
        self.ctrevents = dict(
            exposure=dict(
                function = 'set_exposure_time',
                widget = 'float',
                variable = 'exposure',
                units = 'ms',
                type = 'float',
                min = 0.001,
                max = 100000,
                step = 10))

    def camopen(self,camid):
        '''Open PyVCAM camera'''
        pvc.init_pvcam()                        # Initialize PVCAM
        # use select_camera in the future
        self.cam = next(Camera.detect_camera()) # Use generator to find first camera. 
        self.cam.open()        
    
    def camclose(self):
        ''' Close camera'''
        self.cam.close()
        pvc.uninit_pvcam()

    def set_binning(self, h_bin, v_bin):
        pass
    
    def set_exposure_time(self, exp_time=100):
        pass

    def get_exposure_time(self):
        return 100

    def get_one(self, timeout = 500):
        """
        Snaps a single image
        """
        out = self.cam.get_frame(timeout_ms = int(timeout))
        return out

    def _cam_init(self):
        self.nframes.value = 0
        self.lastframeid = -1
        self.camopen(self.cam_id)
        self.cam.meta_data_enabled = True
        self.camera_ready.set()
        self.nframes.value = 0
        self.datestart = datetime.now()
        
    def _cam_startacquisition(self):
        display('PCO [{0}] - Started acquisition.'.format(self.cam_id))
        self.cam.start_live()
        self.tstamp = 0
    def _cam_stopacquisition(self, clean_buffers = True):
        self.cam.finish()
        i=0
        while clean_buffers:
            # check if there are any frame buffers missing.
            frame,metadata = self._cam_loop()
            if frame is None:
                break
            self._handle_frame(frame,metadata)
            i+=1
        display('[PCO {0}] - cleared {0} buffers.'.format(self.cam_id,i))

        self.disarm()
        
    def _cam_loop(self):
        frame, fps, frame_count = self.cam.poll_frame()
        self.out[:, :] = np.frombuffer(frame, dtype=np.uint16).reshape(self.out.shape)
        frameID = frame_count
        self.tstamp += fps
        print(tstamp)
        return self.out.copy(),(frameID,self.tstamp)
        return None,(None,None)
    
    def _cam_close(self):
        display('PVCam [{0}] - Closing camera.'.format(self.cam_id))
        self.cam.finish()
        self.camclose()
        self.save_trigger.clear()
        if self.was_saving:
            self.was_saving = False
            self.queue.put(['STOP'])
