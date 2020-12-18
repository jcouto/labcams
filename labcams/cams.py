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

# Camera classes for behavioral monitoring and single photon imaging.
# Creates separate processes for acquisition and queues frames
import time
import sys
import multiprocessing
try:
    multiprocessing.set_start_method('spawn')
except:
    pass
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
# Generic class for interfacing with the cameras
# Has last frame on multiprocessing array
# 
class GenericCam(Process):
    def __init__(self, outQ = None, recorderpar = None, refreshperiod = 1/20.):
        super(GenericCam,self).__init__()
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
        self.camera_ready = Event()
        self.eventsQ = Queue()
        self._init_controls()
        self._init_ctrevents()
        self.cam_is_running = False
        self.was_saving=False
        self.recorderpar = recorderpar
        self.recorder = None
        self.refresh_period = refreshperiod
        self._tupdate = time.time()
        self.daemon = True
        #self.memmanager = Manager()
        #self.memlist = self.memmanager.list()
        #self.memlist.append(None)
        self.lasttime = 0
    def get_img(self):
        return self.img#self.memlist[0]
    
    def stop_saving(self):
        # This will send a stop to stop saving and close the writer.
        #if self.saving.is_set():
        self.saving.clear()
        
    def _init_controls(self):
        return

    def _init_ctrevents(self):
        if hasattr(self,'ctrevents'):
            for c in self.ctrevents.keys():
                self.ctrevents[c]['call'] ='self.'+self.ctrevents[c]['function']    
    def _init_variables(self, dtype=np.uint8):
        if dtype == np.uint8:
            cdtype = ctypes.c_ubyte
        else:
            cdtype = ctypes.c_ushort
        self.frame = Array(cdtype,np.zeros([self.h,self.w,self.nchan],
                                           dtype = dtype).flatten())
        self.img = np.frombuffer(
            self.frame.get_obj(),
            dtype = cdtype).reshape([self.h, self.w, self.nchan])

    def _start_recorder(self):
        if not self.recorderpar is None:
            extrapar = {}
            if 'binary' in self.recorderpar['recorder'].lower():
                from .io import BinaryCamWriter as rec
            elif 'tiff' in self.recorderpar['recorder'].lower():
                from .io import TiffCamWriter as rec
            elif 'ffmpeg' in self.recorderpar['recorder'].lower():
                from .io import FFMPEGCamWriter as rec
                if 'hwaccel' in self.recorderpar:
                    extrapar['hwaccel'] =  self.recorderpar['hwaccel']
            else:                
                display('Recorder {0} not implemented'.format(
                    self.recorderpar['recorder']))
            if 'rec' in dir():
                self.recorder = rec(self,
                                    inQ = self.queue,
                                    filename = self.recorderpar['filename'],
                                    pathformat = self.recorderpar['pathformat'],
                                    dataname = self.recorderpar['dataname'],
                                    datafolder = self.recorderpar['datafolder'],
                                    framesperfile = self.recorderpar['framesperfile'],
                                    incrementruns = True,**extrapar)
            
    def run(self):
        self._init_ctrevents()
        self.img = np.frombuffer(self.frame.get_obj(),
                                 dtype = self.dtype).reshape(
                                     [self.h,self.w,self.nchan])
        self.close_event.clear()
        self._start_recorder()
        while not self.close_event.is_set():
            self._cam_init()
            if self.stop_trigger.is_set():
                break
            self._cam_waitsoftwaretrigger()
            if not self.stop_trigger.is_set():
                self._cam_startacquisition()
                self.cam_is_running = True
            while not self.stop_trigger.is_set():
                frame,metadata = self._cam_loop()
                self._handle_frame(frame,metadata)
                self._parse_command_queue()
                # to be able to pause acquisition on software trigger
                if not self.start_trigger.is_set() and not self.stop_trigger.is_set():
                    self._cam_stopacquisition()
                    self._cam_waitsoftwaretrigger()
                    if not self.stop_trigger.is_set():
                        self._cam_startacquisition()
                        self.cam_is_running = True
            display('[Camera] Stop trigger set.')
            self.start_trigger.clear()
            self._cam_close()
            self.cam_is_running = False
            if self.was_saving:
                self.was_saving = False
                if self.recorder is None:
                    display('[Camera] Sending stop signal to the recorder.')
                    self.queue.put(['STOP'])
                else:
                    self.recorder.close_run()
            self.stop_trigger.clear()
            if self.close_event.is_set():
                break

    def _handle_frame(self,frame,metadata):
        #display('loop rate : {0}'.format(1./(timestamp - self.lasttime)))
        if self.saving.is_set():
            self.was_saving = True
            if not frame is None:
                if not metadata[0] == self.lastframeid :
                    if not self.recorder is None:
                        self.recorder.save(frame,metadata)
                    else:
                        self.queue.put((frame,metadata))
        elif self.was_saving:
            if self.recorder is None:
                self.was_saving = False            
                display('[Camera] Sending stop signal to the recorder.')
                self.queue.put(['STOP'])
            else:
                self.was_saving = False            
                self.recorder.close_run()
        if not frame is None:
            frameID,timestamp = metadata[:2]
            if not frameID == self.lastframeid:
                t = time.time()
                if (t - self._tupdate) > self.refresh_period:
                    self._update_buffer(frame,frameID)
                    self._tupdate = t
                #self.nframes.value += 1
            self.lastframeid = frameID
            self.lasttime = timestamp
        
    def _update_buffer(self,frame,frameID):
        self.img[:] = np.reshape(frame,self.img.shape)[:]
        #self.memlist[0] = np.reshape(frame,[self.h,self.w,self.nchan])
    def _parse_command_queue(self):
        if not self.eventsQ.empty():
            cmd = self.eventsQ.get()
            if '=' in cmd:
                cmd = cmd.split('=')
                if hasattr(self,'ctrevents'):
                    self._call_event(cmd[0],cmd[1])
                if cmd[0] == 'filename':
                    if not self.recorder is None:
                        if hasattr(self,'recorder'):
                            self.recorder.set_filename(cmd[1])
                    self.recorderpar['filename'] = cmd[1]
                elif cmd[0] == 'log':
                    msg = '# {0},{1} - {2}'.format(
                        self.lastframeid,
                        self.lasttime,cmd[1])
                    if self.recorder is None:
                        self.queue.put([msg])
                    else:
                        self.recorder.logfile.write(msg)
                    
    def _call_event(self,eventname,eventvalue):
        if eventname in self.ctrevents.keys():
            val = eval(self.ctrevents[eventname]['type']+'('+str(eventvalue)+')')
            eval(self.ctrevents[eventname]['call']+'(val)')
            #print(self.ctrevents[eventname])
#        else:
#            display('No event found {0} {1}'.format(eventname,eventvalue))

    def _cam_init(self):
        '''initialize the camera'''
        pass

    def _cam_startacquisition(self):
        '''start camera acq'''
        pass

    def _cam_stopacquisition(self):
        '''stop camera acq'''
        pass
    
    def _cam_close(self):
        '''close cam - release driver'''
        pass

    def _cam_loop(self):
        '''get a frame and move on, returns frame,(frameID,timestamp)'''
        pass
    
    def _cam_waitsoftwaretrigger(self):
        '''wait for software trigger'''
        display('[{0} {1}] waiting for software trigger.'.format(self.drivername,self.cam_id))
        while not self.start_trigger.is_set() or self.stop_trigger.is_set():
            # limits resolution to 1 ms 
            time.sleep(0.001)
            if self.close_event.is_set() or self.stop_trigger.is_set():
                break
            self._handle_frame(None,None) # to stop saving while waiting for triggers
        if self.close_event.is_set() or self.stop_trigger.is_set():
            return
        self.camera_ready.clear()

    def stop_acquisition(self):
        self.stop_trigger.set()

    def close(self):
        self.close_event.set()
        self.stop_acquisition()
        
# OpenCV camera; some functionality limited (like hardware triggers)
class OpenCVCam(GenericCam):    
    def __init__(self,
                 camId = None,
                 outQ = None,
                 frameRate = 0.,
                 triggered = Event(),
                 recorderpar = None,
                 **kwargs):
        super(OpenCVCam,self).__init__(outQ = outQ, recorderpar = recorderpar)
        self.drivername = 'openCV'
        if camId is None:
            display('Need to supply a camera ID.')
        self.cam_id = camId
        self.frame_rate = float(frameRate)
        self.cam = cv2.VideoCapture(self.cam_id)
        self.set_framerate(self.frame_rate)
        ret_val, frame = self.cam.read()
        frame = frame
        self.h = frame.shape[0]
        self.w = frame.shape[1]
        if len(frame.shape) > 2:
            self.nchan = frame.shape[2]
        self.dtype = frame.dtype

        self._init_variables(dtype = self.dtype)

        self.cam.release()
        self.cam = None
        self.triggered = triggered
        if self.triggered.is_set():
            display('[OpenCV {0}] Triggered mode ON.'.format(self.cam_id))
            self.triggerSource = triggerSource
    def _init_controls(self):
        self.ctrevents = dict(
            framerate=dict(
                function = 'set_framerate',
                widget = 'float',
                variable = 'frame_rate',
                units = 'fps',
                type = 'float',
                min = 0.0,
                max = 1000,
                step = 0.1))

    def set_framerate(self,framerate = 30.):
        '''Set frame rate in seconds'''
        self.frame_rate = float(framerate)
        if not self.cam is None:
            if not float(self.frame_rate) == float(0):
                res = self.cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                res = self.cam.set(cv2.CAP_PROP_EXPOSURE,1./self.frame_rate)
                res = self.cam.set(cv2.CAP_PROP_FPS,self.frame_rate)
            else:
                display('[OpenCV] Setting auto exposure.')
                res = self.cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                self.cam.set(cv2.CAP_PROP_EXPOSURE, 100) 

            if self.cam_is_running:
                self.stop_trigger.set()
                self.start_trigger.set()

            display('[OpenCV {0}] Set frame_rate to: {1}.'.format(self.cam_id,
                                                                  self.frame_rate))
            
    def _cam_init(self):
        self.nframes.value = 0
        self.lastframeid = -1
        self.cam = cv2.VideoCapture(self.cam_id)
        self.set_framerate(self.frame_rate)        
        self.camera_ready.set()
        self.nframes.value = 0
    def _cam_loop(self):
        frameID = self.nframes.value
        self.nframes.value = frameID + 1 

        ret_val, frame = self.cam.read()
        if not ret_val:
            return
        timestamp = time.time()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame,(frameID,timestamp)

    def _cam_close(self):
        self.cam.release()
        display('[OpenCV {0}] - Stopped acquisition.'.format(self.cam_id))
        
