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
import pco
from datetime import datetime
class PCOCam(GenericCam):
    def __init__(self,
                 cam_id = None,
                 name = '',
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,                 
                 out_q = None,
                 binning = None,
                 exposure = 100,
                 dtype = np.uint16,
                 trigger_source = np.uint16(2),
                 hardware_trigger = None,
                 roi = None,
                 recorderpar = None,
                 acquire_mode = 'auto', # external
                 debuglevel = 'off', # verbose
                 **kwargs):
        super(PCOCam,self).__init__(cam_id = cam_id,
                                    name = name,
                                    out_q = out_q,
                                    start_trigger = start_trigger,
                                    stop_trigger = stop_trigger,
                                    save_trigger = save_trigger,
                                    recorderpar = recorderpar)
        self.armed = False
        self.drivername = 'PCO'
        self.exposure = exposure
        self.binning = binning
        self.dtype = dtype
        self.roi = roi
        self.acquire_mode = acquire_mode
        self.debuglevel = debuglevel
        self._cam_init()
        
        self.cam.record(1)
        frame,info = self.cam.image()

        self.cam.close()
        self.cam = None
        self.h.value = frame.shape[0]
        self.w.value = frame.shape[1]
        display('PCO - size: {0} x {1}'.format(self.h.value,self.w.value))

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
        display("[PCO {0}] Got info from camera".format(
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

    def set_exposure_time(self,exposure):
        self.exposure = exposure
        self.cam.exposure_time = self.exposure/1000.
        
    
    def acquisitionstop(self):
        """
        Start recording
        :return: message from recording status
        """
        display('[PCO {0}] - Stopping acquisition.'.format(self.cam_id))
        return self.cam.stop()
    

    def _cam_init(self):
        self.cam = pco.Camera()
        self.cam.sdk.set_hot_pixel_correction_mode('on')
        self.cam.sdk.set_pixel_rate(max(self.cam.sdk.get_camera_description()['pixel rate']))
        try:
            self.cam.sdk.set_hwio_signal(index = 3,
                                         enabled = 'on',
                                         signal_type = 'TTL',
                                         filter_type = 'off',
                                         polarity='high level',
                                         selected = 0,
                                         parameter = [2,0,0,0])
            # this is not doing what I want yet..
        except:
            print('Could not set HWIO for line 4.')
        self.cam.set_acquire_mode = self.acquire_mode
        if not self.binning is None:
            self.cam.sdk.set_binning(self.binning,self.binning)
        sizes = self.cam.sdk.get_sizes()
        binning = self.cam.sdk.get_binning()
        if self.roi is None:
            self.roi = [1,1,int(sizes['x max']/binning['binning x']),
                        int(sizes['y max']/binning['binning y'])]
        self.cam.sdk.set_roi(*self.roi)

        self.cam.exposure_time = self.exposure/1000.
        self.cam.sdk.set_timestamp_mode('binary')
        self.camera_ready.set()
        self.nframes.value = 0
        self.lastframeid = -1
        self.datestart = datetime.now()
        
    def _cam_startacquisition(self):
        display('PCO [{0}] - Started acquisition.'.format(self.cam_id))
        self.cam.record(500, mode='ring buffer')
                
    def _cam_stopacquisition(self, clean_buffers = True):
        self.cam.sdk.set_recording_state('off')
        self.cam.stop()
        i = 0
        while clean_buffers:
            # check if there are any frame buffers missing.
            frame,metadata = self._cam_loop()
            if frame is None:
                break
            self._handle_frame(frame,metadata)
            i+=1
        display('[PCO {0}] - cleared {0} buffers.'.format(self.cam_id,i))
        
        
    def _cam_loop(self,poll_timeout=5e7):
        timestamp = 0
        message = 0
        num_acquired = 0
        status = self.cam.rec.get_status()
        #if not status['is running']:
        #    return None,(None,None)
        if status['dwProcImgCount'] == 0 or status['dwProcImgCount'] <= (self.lastframeid):
            return None,(None,None)

        frame,info = self.cam.image(-1)
        frameID = info['timestamp']['image counter']
        t = info['timestamp']
        ms,s = np.modf(t['second'])
        timestamp = datetime(year = t['year'],
                             month=t['month'],
                             day = t['day'],
                             hour=t['hour'],
                             minute = t['minute'],
                             second = int(s),
                             microsecond = int(ms*1e6))
        return frame,(frameID,timestamp)
    
    def _cam_close(self):
        ret = self.cam.close()
        display('PCO - returned {0} on close'.format(ret))
        self.save_trigger.clear()
        if self.was_saving:
            self.was_saving = False
            self.queue.put(['STOP'])
