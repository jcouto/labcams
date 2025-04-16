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
                 name = '',
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,                 
                 out_q = None,
                 binning = 1,
                 readout_port = 2,
                 gain = 1,
                 trigger_mode = "Internal Trigger",
                 exposure_out_mode = "All Rows",
                 buffer_frame_count=4000,
                 exposure = 16,
                 dtype = None,
                 use_camera_parameters = True,
                 trigger_source = np.uint16(2),
                 hardware_trigger = None,
                 dllpath = None,
                 recorderpar = None,
                 **kwargs):
        super(PVCam,self).__init__(cam_id = cam_id,
                                   name = name,
                                   out_q = out_q,
                                   start_trigger = start_trigger,
                                   stop_trigger = stop_trigger,
                                   save_trigger = save_trigger,
                                   recorderpar=recorderpar)
        self.drivername = 'PVCam'
        self.trigerMode = 0
        self.exposure = exposure
        self.readout_port = readout_port
        self.gain = gain
        self.binning = binning
        self.exp_mode = trigger_mode
        self.exp_out_mode = exposure_out_mode
        self.buffer_frame_count = buffer_frame_count
        self.binning = binning
        self.dtype = dtype
        self._cam_init()
        self.iframe = 0
        ###
        frame = self.get_one()
        
        self.camclose()
        self.cam = None
        self.h.value = frame.shape[0]
        self.w.value = frame.shape[1]
        if dtype is None:
            dtype = frame.dtype
            print('[PVCam] - dtype is: {0}'.format(dtype))
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
        self.cam.readout_port = self.readout_port
        self.cam.gain = self.gain
        self.cam.binning = self.binning
        self.cam.exp_mode = self.exp_mode
        self.cam.exp_out_mode = self.exp_out_mode
        self.cam.exp_time = self.exposure
        self.cam.meta_data_enabled = True
        self.cam.clear_mode = "Auto"
        print(self.cam.clear_modes)
        self.cam.speed_table_index = 0
        self.camera_ready.set()
        self.nframes.value = 0
        self.datestart = datetime.now()
        
    def _cam_startacquisition(self):
        display('PCO [{0}] - Started acquisition.'.format(self.cam_id))
        self.cam.start_live(exp_time = self.exposure, buffer_frame_count=100)
        self.tstamp = 0
    def _cam_stopacquisition(self, clean_buffers = True):
        self.cam.finish()
        
    def _cam_loop(self):
        f, fps, frame_count = self.cam.poll_frame(oldestFrame=True,
                                                  copyData=False)
        frame = f['pixel_data'].copy()
        frameID = int(f['meta_data']['frame_header']['frameNr'])
        tstamp = int(f['meta_data']['frame_header']['timestampBOF'])
        if frameID != self.iframe+1:
            print('The number of buffers can needs to be increased??\n Got frame {0}; expected {1}!'.format(self.iframe,frameID))
        self.iframe = frameID

        return frame,(frameID,tstamp)
        return None,(None,None)
    
    def _cam_close(self):
        display('PVCam [{0}] - Closing camera.'.format(self.cam_id))
        self.cam.finish()
        self.camclose()
        self.save_trigger.clear()
        if self.was_saving:
            self.was_saving = False
            self.queue.put(['STOP'])
