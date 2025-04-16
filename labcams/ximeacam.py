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

from ximea import xiapi
from .cams import *

class XimeaCam(GenericCam):
    def __init__(self,
                 cam_id = None,
                 name = '',
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,                 
                 out_q = None,
                 binning = 2,
                 exposure = 20000,
                 triggerSource = np.uint16(2),
                 outputs = ['XI_GPO_EXPOSURE_ACTIVE'],
                 hardware_trigger = None,
                 recorderpar = None,
                 **kwargs):
        super(XimeaCam,self).__init__(cam_id = cam_id,
                                      name = name,
                                      out_q = out_q,
                                      start_trigger = None,
                                      stop_trigger = None,
                                      save_trigger = None,
                                      recorderpar = recorderpar)
        self.drivername = 'Ximea'
        self.hardware_trigger = hardware_trigger
        if self.hardware_trigger is None:
            self.hardware_trigger = Event()
        self.outputs = outputs
        self.binning = binning
        self.exposure = exposure
        self.frame_rate = 1000./float(self.exposure)
        self.fs.value = self.frame_rate

        frame = self.get_one()

        self.h = frame.shape[0]
        self.w = frame.shape[1]
        self.nchannels = 1
        self.dtype = np.uint16
        self._init_variables(self.dtype)
        self.triggerSource = triggerSource
        self.img[:] = np.reshape(frame,self.img.shape)[:]

        display("[Ximea {0}] - got info from camera.".format(self.cam_id))

    def _init_controls(self):
        self.ctrevents = dict(
            exposure=dict(
                function = 'set_exposure',
                widget = 'float',
                variable = 'exposure',
                units = 'ms',
                type = 'int',
                min = 1,
                max = 10000000000,
                step = 10))
    
    def get_one(self):
        self._cam_init()
        self.cam.start_acquisition()
        self.cam.get_image(self.cambuf)
        frame = self.cambuf.get_image_data_numpy()
        self.cam.stop_acquisition()
        self.cam.close_device()
        self.cam = None
        self.cambuf = None
        return frame
    
    def set_exposure(self,exposure = 20000):
        '''Set the exposure time is in us'''
        self.exposure = exposure
        self.frame_rate = 1000./float(self.exposure)
        self.fs.value = self.frame_rate

        if not self.cam is None:
            if self.cam_is_running:
                self.start_trigger.set()
                self.stop_trigger.set()

    def _cam_init(self,set_gpio=True):
        self.cam = xiapi.Camera()
        #start communication
        self.cam.open_device()
        self.cam.set_acq_timing_mode('XI_ACQ_TIMING_MODE_FREE_RUN')
        self.cam.set_exposure(self.exposure)
        self.cam.set_binning_vertical(self.binning)
        self.cam.set_binning_horizontal(self.binning)
        # Set the GPIO
        self.cam.set_gpi_selector('XI_GPI_PORT1')
        self.cam.set_trigger_source('XI_TRG_OFF')

        if set_gpio:
            self.cam.set_gpo_selector('XI_GPO_PORT1')
            # for now set the GPO to blink in software (port1 will do that for sync purposes, the test cam does not support XI_GPO_EXPOSURE_PULSE)
            self.cam.set_gpo_mode('XI_GPO_ON'); #XI_GPO_EXPOSURE_PULSE
            if self.hardware_trigger.is_set():
                self.cam.set_gpi_mode('XI_GPI_TRIGGER')
                self.cam.set_trigger_source('XI_TRG_EDGE_RISING')
        self.cam.set_led_selector('XI_LED_SEL1')
        self.cam.set_led_mode('XI_LED_OFF')
        self.cam.set_led_selector('XI_LED_SEL2')
        self.cam.set_led_mode('XI_LED_OFF')
        self.cam.set_led_selector('XI_LED_SEL3')
        self.cam.set_led_mode('XI_LED_OFF')
        self.cambuf = xiapi.Image()
        self.lastframeid = -1
        self.nframes.value = 0
        self.camera_ready.set()

    def _cam_startacquisition(self):
        self.cam.start_acquisition()

    def _cam_loop(self):
        try:
            self.cam.get_image(self.cambuf)
        except xiapi.Xi_error:
            return None,(None,None)
        frame = self.cambuf.get_image_data_numpy()
        frameID = self.cambuf.nframe
        timestamp = self.cambuf.tsUSec
        self.cam.set_gpo_mode('XI_GPO_OFF'); #XI_GPO_EXPOSURE_PULSE
        time.sleep(0.001)
        self.cam.set_gpo_mode('XI_GPO_ON'); #XI_GPO_EXPOSURE_PULSE
        return frame,(frameID,timestamp)
        
    def _cam_close(self):
        self.cam.stop_acquisition()
        self.cam.close_device()
        self.cam = None        
