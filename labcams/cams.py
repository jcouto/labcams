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
from multiprocessing import set_start_method
try:
    set_start_method("spawn")
except:
    pass
from multiprocessing import Process, Queue, Event, Array, Value, Lock
from multiprocessing.shared_memory import SharedMemory # this breaks compatibility with python < 3.8
if (sys.maxsize > 2**32):
    BUFFER_SIZE = 1.5e9  # this is the buffer size allocation in shared memory
else:
    BUFFER_SIZE = 0.5e9  # this is the buffer size allocation in shared memory
    
import numpy as np
from datetime import datetime
from .utils import *
import ctypes

import cv2

# Current changes have 2 goals
#   1) faster initialization by moving the get 1 frame out (initializing the camera only inside the process)
#   2) keep a rolling buffer for each camera (will use more memory)
#   3) replace the outQ with a shared memory buffer
#   4) remove the refresh period / buffer refresh
#   5) Because of this, python needs to be >3.8

        
#
# Generic class for interfacing with the cameras
#
class GenericCam(Process):
    def __init__(self, cam_id,
                 name = '',
                 out_q = None,
                 recorderpar = None,
                 refreshperiod = 1/20.,
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,
                 recorder_mode = 'shared_mem_queue', # 'shared_mem','queue','inline' 
                 membuffer_len = BUFFER_SIZE,
                 **kwargs):
        super(GenericCam,self).__init__()
        self.name = name
        if cam_id is None:
            display('Need to supply a camera ID.')
        self.cam_id = cam_id
        self.cam = None
        self.close_event = Event()
        self.start_trigger = start_trigger
        self.stop_trigger = stop_trigger
        self.save_trigger = save_trigger
        if self.start_trigger is None:
            self.start_trigger = Event()
        if self.stop_trigger is None:
            self.stop_trigger = Event()
        if self.save_trigger is None:
            self.save_trigger = Event()
        self.nframes = Value('i',-1)

        self.h = Value('i',-1)
        self.w = Value('i',-1)
        self.fs = Value('d',-1)
        self.nchan = Value('i',1)
        self.nbuffers = Value('i',0)

        self.queue = out_q
        self.camera_ready = Event()
        self.eventsQ = Queue(MAX_QUEUE_SIZE)
        self._init_controls()
        self._init_ctrevents()
        self.cam_is_running = False
        self.was_saving = False
        self.recorderpar = recorderpar
        self.recorder = None
        self.refresh_period = refreshperiod
        self._tupdate = time.time()
        self.daemon = True
        self.membuffer_len = int(membuffer_len)
        self.membuffer_name = '{0}_{1}_{2}'.format(int(np.random.rand()*1e9),
                                                   self.name,
                                                   self.cam_id)
        self.membuffer = SharedMemory(name = self.membuffer_name,
                                      create = True,
                                      size = self.membuffer_len)
        self.membuffer_lock = Lock()
        # fixed size, independent of the framesize
        self.lasttime = 0

        if not self.recorderpar is None:
            self._init_recorder = self._recorder_inline_init
            self._handle_recorder = self._recorder_inline_handle
        else:
            self._handle_recorder = self._recorder_shared_mem_handle
    def _init_recorder(self):
        pass
    
    def _recorder_inline_init(self):
        if not self.recorderpar is None:
            extrapar = {}
            if 'binary' in self.recorderpar['recorder'].lower():
                from .io import BinaryCamWriter as rec
            elif 'tiff' in self.recorderpar['recorder'].lower():
                from .io import TiffCamWriter as rec
            elif 'ffmpeg' in self.recorderpar['recorder'].lower():
                from .io import FFMPEGCamWriter as rec
                if 'hwaccel' in self.recorderpar:
                    if 'hwaccel' in self.recorderpar.keys():
                        extrapar['hwaccel'] =  self.recorderpar['hwaccel']
                    if 'compression' in self.recorderpar.keys():                    
                        extrapar['compression'] = self.recorderpar['compression']
            else:                
                display('Recorder {0} not implemented'.format(
                    self.recorderpar['recorder']))
            if 'rec' in dir():
                print(extrapar)
                self.recorder = rec(self.cam,
                                    filename = self.recorderpar['filename'],
                                    pathformat = self.recorderpar['pathformat'],
                                    dataname = self.recorderpar['dataname'],
                                    datafolder = self.recorderpar['datafolder'],
                                    framesperfile = self.recorderpar['framesperfile'],
                                    incrementruns = True,**extrapar)

    def _recorder_inline_handle(self,frame,metadata):
        if not self.recorder is None:
            self.recorder.save(frame, metadata)

    def _recorder_queue_handle(self,frame,metadata):
        self.queue.put((frame, metadata))

    def _recorder_shared_mem_handle(self,frame,metadata):
        self.queue.put((metadata[0], metadata))

    def _stop_recorder(self):
        if self.recorder is None:
            display('[Camera {0}] Sending stop signal to the recorder.'.format(self.cam_id))
            self.queue.put(['STOP'])
        else:
            self.recorder.close_run()

    def get_img(self,frame_index = None):
        # no lock needed when reading because it is in update buffer?
        #self.membuffer_lock.acquire() 
        if frame_index is None:
            frame_index = self.nframes.value
        img = self.imgs[frame_index % self.nbuffers.value]
        #self.membuffer_lock.release()
        return img

    def stop_saving(self):
        # This will send a stop to stop saving and close the writer.
        self.save_trigger.clear()
        
    def _init_controls(self):
        return

    def _init_ctrevents(self):
        if hasattr(self,'ctrevents'):
            for c in self.ctrevents.keys():
                self.ctrevents[c]['call'] ='self.'+self.ctrevents[c]['function']    
    def _init_variables(self, dtype=np.uint8):
        try:
            dtype = dtype()
        except:
            pass
        if not hasattr(self,'membuffer'):
            self.membuffer = SharedMemory(name = self.membuffer_name)
        buffsize = [self.h.value,self.w.value,self.nchan.value]
        self.nbuffers.value = int(self.membuffer_len // np.prod(buffsize+[dtype.itemsize]))
        display('[{0}] - using {1} buffers.'.format(self.name,self.nbuffers.value))
        buffsize = [self.nbuffers.value] + buffsize
        self.imgs = np.ndarray(buffsize,
                               buffer = self.membuffer.buf,
                               dtype = dtype)
        
    def run(self):
        self._init_ctrevents()
        self._init_variables(dtype = self.dtype)
        self.close_event.clear()
        self._init_recorder()
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
                if not self.start_trigger.is_set() or self.stop_trigger.is_set():
                    self._cam_stopacquisition()
                    self.camera_ready.set()
                    self.cam_is_running = False
                    self._cam_waitsoftwaretrigger()
                    if not self.stop_trigger.is_set():
                        self._cam_startacquisition()
                        self.cam_is_running = True
            #display('[Camera {0}] Stop trigger set.'.format(self.cam_id))
            self.start_trigger.clear()
            self._cam_close()
            self.cam_is_running = False
            if self.was_saving:
                self.was_saving = False
                self._stop_recorder()
            self.stop_trigger.clear()
            if self.close_event.is_set():
                break
        self.membuffer.close()
        del self.membuffer_lock
             
    def _handle_frame(self,frame,metadata):
        if self.save_trigger.is_set():
            self.was_saving = True
            if not frame is None:
                if not metadata[0] == self.lastframeid :
                    self._handle_recorder(frame,metadata)
        elif self.was_saving:
            self._stop_recorder()
            self.was_saving = False
        if not frame is None:
            frameID,timestamp = metadata[:2]
            if not frameID == self.lastframeid:
                t = time.time()
                #if (t - self._tupdate) > self.refresh_period:
                #update the buffer at every time.
                self._update_buffer(frame,frameID)
                self._tupdate = t
                #self.nframes.value += 1
                #display('loop rate : {0}'.format(1./(timestamp - self.lasttime)))
                self.lasttime = timestamp
        
    def _update_buffer(self,frame,frameID):
        ''' Updates buffer for a specific frame ID'''
        lock = self.membuffer_lock.acquire(timeout = 0.1)
        if not lock:
            display('Failed to secure lock')
            return
        idx = frameID % self.nbuffers.value
        if len(frame.shape) == 2:
            self.imgs[idx,:,:,0] = frame[:]
        else:
            self.imgs[idx] = frame[:]
        self.nframes.value = frameID
        self.lastframeid = int(frameID)
        self.membuffer_lock.release()

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
                        else:
                            self.recorderpar['filename'] = cmd[1]
                elif cmd[0] == 'log':
                    msg = '# {0},{1} - {2}'.format(
                        self.nframes.value,
                        self.lasttime,cmd[1])
                    if self.recorder is None:
                        self.queue.put([msg])
                    else:
                        if not self.recorder.logfile is None:
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
        self.lastframeid = -1
        while (not self.start_trigger.is_set()):
            # limits resolution to 1 ms 
            time.sleep(0.001)
            if self.close_event.is_set() or self.stop_trigger.is_set():
                break
            self._handle_frame(None,(None,None)) # to stop saving while waiting for triggers
        if self.close_event.is_set() or self.stop_trigger.is_set():
            return
        self.camera_ready.clear()
        display('[{0} {1}] triggered acquisition.'.format(
            self.drivername,
            self.cam_id))

    def stop_acquisition(self):
        self.start_trigger.clear()

    def close(self):
        self.close_event.set()
        self.stop_trigger.set()
        self.stop_acquisition()
        self.membuffer.close()
        self.membuffer.unlink()
        if not self.eventsQ:
             self.eventsQ.close()
        if not self.queue is None:
            self.queue.close()

        
# OpenCV camera; some functionality limited (like hardware triggers)
class OpenCVCam(GenericCam):    
    def __init__(self,
                 cam_id = None,
                 name = '',
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,
                 out_q = None,
                 frame_rate = 0.,
                 recorderpar = None,
                 **kwargs):
        super(OpenCVCam,self).__init__(cam_id = cam_id,
                                       name = name,
                                       out_q = out_q,
                                       start_trigger = start_trigger,
                                       stop_trigger = stop_trigger,
                                       save_trigger = save_trigger,
                                       recorderpar = recorderpar)
        self.drivername = 'openCV'
        self.frame_rate = float(frame_rate)
        self.fs.value = self.frame_rate
        self.cam = cv2.VideoCapture(self.cam_id)
        self.set_framerate(self.frame_rate)
        ret_val, frame = self.cam.read()
        frame = frame
        self.h.value = frame.shape[0]
        self.w.value = frame.shape[1]
        if len(frame.shape) > 2:
            self.nchan.value = frame.shape[2]
        self.dtype = frame.dtype

        self._init_variables(dtype = self.dtype)

        self.cam.release()
        self.cam = None
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
                self.fs.value = self.frame_rate

            if self.cam_is_running:
                self.stop_trigger.set()
                time.sleep()
                self.start_trigger.set()

            display('[OpenCV {0}] Set frame_rate to: {1}.'.format(self.cam_id,
                                                                  self.frame_rate))
            
    def _cam_init(self):
        self.lastframeid = -1
        self.cam = cv2.VideoCapture(self.cam_id) 
        self.set_framerate(self.frame_rate)
        self.cam.release() # like this the camera is not constantly running on software trigger
        self.camera_ready.set()
        self.nframes.value = 0

    def _cam_startacquisition(self):
        self.cam = cv2.VideoCapture(self.cam_id) # like this the camera is not constantly running
        self.nframes.value = 0
    def _cam_stopacquisition(self):
        self.cam.release() 
        
    def _cam_loop(self):
        frameID = self.nframes.value + 1
        #self.nframes.value = frameID  

        ret_val, frame = self.cam.read()
        if not ret_val:
            return
        timestamp = time.time()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame,(frameID,timestamp)

    def _cam_close(self):
        self.cam.release()
        display('[OpenCV {0}] - Stopped acquisition.'.format(self.cam_id))

# incorporates a camera and a recorder, manages the start and stop of both
class Camera(object): 
    def __init__(self, cam_id, driver, name,
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,
                 hardware_trigger_event = None,
                 filename = 'labcams',
                 recorder_path = pjoin(os.path.expanduser('~'),'data'),
                 recorder_path_format = pjoin('{datafolder}',
                                              '{dataname}',
                                              '{filename}',
                                              '{today}_{run}_{nfiles}'),
                 recorder = dict(format='tiff',  # default recorder
                                 method = 'queue',
                                 compression = 0,
                                 frames_per_file = 1024),
                 **kwargs):
        # parse camera based on the driver
        self.cam_id = cam_id
        self.name = name
        self.driver = driver
        self.start_trigger = start_trigger
        self.stop_trigger = stop_trigger
        self.save_trigger = save_trigger
        if self.start_trigger is None:
            self.start_trigger = Event()
        if self.stop_trigger is None:
            self.stop_trigger = Event()
        if self.save_trigger is None:
            self.save_trigger = Event()

        self.hardware_trigger_event = hardware_trigger_event
        if self.hardware_trigger_event is None: # to control the hardware triggering of the cameras
            self.hardware_trigger_event = Event()
        
        self.recorder_path = recorder_path 
        self.recorder_path_format = recorder_path_format
        self.filename = filename
        self.camera_description = self.name
                    
        self.recorder_q = Queue(MAX_QUEUE_SIZE) # queue to talk to the recorder.
        # recorder options
        self.recorder_parameters = recorder
        if not 'datafolder' in recorder.keys():
            self.recorder_parameters['datafolder'] = self.recorder_path 
        if not 'pathformat' in recorder.keys():
            self.recorder_parameters['pathformat'] = self.recorder_path_format 
        if not 'filename'  in recorder.keys():
            self.recorder_parameters['filename'] = self.filename
        if not 'dataname'  in recorder.keys():
            self.recorder_parameters['dataname'] = self.camera_description
        if not 'method' in recorder.keys():
            self.recorder_parameters['method'] = 'queue'
        if not 'format' in recorder.keys():
            self.recorder_parameters['format'] = 'tiff'
        if 'noqueue' in recorder['method']:
            recorderpar = self.recorder_parameters
        else:
            recorderpar = None # Use a queue recorder
                
        params = dict(kwargs,
                      name = self.name,
                      recorderpar = recorderpar)
        # add an arduino if needed
        if 'excitation_trigger' in params.keys():
            if not params['excitation_trigger'] is None:
                if 'port' in params['excitation_trigger'].keys():
                    from .cam_stim_trigger import CamStimInterface
                    self.excitation_trigger = CamStimInterface(
                        port = params['excitation_trigger']['port'],
                        saving = self.save_trigger,
                        outQ = self.recorder_q)
        # parse cameras
        if self.driver.lower() == 'avt':
            self._init_avt_cam(params)
        elif self.driver.lower() == 'qimaging':
            self._init_qimaging_cam(params)
        elif self.driver.lower() == 'opencv':
            self.cam = OpenCVCam(cam_id = self.cam_id,
                                 start_trigger = self.start_trigger,
                                 stop_trigger = self.stop_trigger,
                                 save_trigger = self.save_trigger,
                                 out_q = self.recorder_q,
                                 **params)
        elif self.driver.lower() == 'pco':
            self._init_pco_cam(params)            
        elif self.driver.lower() == 'pvcam':
            self._init_pvcam_cam(params)            
        elif self.driver.lower() == 'basler':
            self._init_basler_cam(params)
        elif self.driver.lower() == 'ximea':
            self._init_ximea_cam(params)
        elif self.driver.lower() in ['pointgrey','flir']:
            self._init_pointgrey_cam(params)
        elif self.driver.lower() in ['nidaq']:
            params['recorderpar'] = self.recorder_parameters
            self._init_nidaq_cam(params)
            self.recorder_parameters['format'] = 'daq'
        else:
            display('[WARNING] -----> Unknown camera driver ' +
                    self.driver)
            raise(ValueError('Unknown camera driver ' +
                             self.driver))
        self.cam.name = self.name
        self.camera_ready = self.cam.camera_ready
        self.writer = None
        if recorderpar is None:
            if self.recorder_parameters['format'] == 'tiff':
                display('Recording to TIFF.')
                from .io import TiffWriter
                self.writer = TiffWriter(cam = self.cam, **self.recorder_parameters)
            elif self.recorder_parameters['format'] == 'ffmpeg':
                display('Recording with FFMPEG.')
                from .io import FFMPEGWriter
                self.writer = FFMPEGWriter(cam = self.cam, **self.recorder_parameters)
            elif self.recorder_parameters['format'] == 'binary':
                from .io import BinaryWriter
                vchans = None
                if hasattr(self,'excitation_trigger'):
                    vchans = self.excitation_trigger.nchannels
                display('Recording in binary format.')
                self.writer = BinaryWriter(cam = self.cam,
                                           virtual_channels = vchans,
                                           **self.recorder_parameters)
            elif self.recorder_parameters['format'] == 'opencv':
                from .io import OpenCVWriter
                display('Recording with OpenCV.')
                self.writer = OpenCVWriter(cam = self.cam,
                                           **self.recorder_parameters)
            elif self.recorder_parameters['format'] == 'daq':
                self.writer = None
            else:
                    print(''' 

The available recorders are:
    - tiff (multiple tiffstacks - the default)   
    - binary 
    - ffmpeg  Records video format using ffmpeg (hwaccel options: intel, nvidia - remove for no hardware acceleration)
    - opencv  Records video format using openCV

The recorders can be specified with the '"format":"ffmpeg"' option in each camera "recorder" setting of the config file.
''')
                    raise ValueError('Unknown recorder {0} '.format(self.recorder_parameters['format']))
        self.stop_saving = self.cam.stop_saving
        self.stop_acquisition = self.cam.stop_acquisition
        if hasattr(self.cam,'get_img'):     
            self.get_img = self.cam.get_img
        if hasattr(self.cam,'nframes'):
            self.nframes = self.cam.nframes
        if hasattr(self.writer,'virtual_channels'):    # set the number of channels from the excitation
            if hasattr(self,'excitation_trigger'):
                self.writer.virtual_channels.value = self.excitation_trigger.nchannels.value

    def get_img_with_virtual_channels(self,frame_index = None):
        if hasattr(self,'excitation_trigger'):
            vchans = self.excitation_trigger.nchannels.value
        else:
            vchans = 1
        lock = self.cam.membuffer_lock.acquire(timeout = 0.1)
        if frame_index is None:
            frame_index = int(np.floor(self.cam.nframes.value/vchans)*vchans)
        imgs = []
        for i in np.arange(vchans)[::-1]:
            imgs.append(self.cam.imgs[
                np.mod(frame_index-i,
                       self.cam.nbuffers.value)].squeeze())
        if vchans > 1:
            img = np.stack(imgs).transpose(1,2,0)
        else:
            img = imgs[0]
        if lock:
            self.cam.membuffer_lock.release()
        return img

    def set_saving(self,value):
        if value:
            if not self.writer is None:
                self.writer.init_cam(self.cam)
                self.writer.write.set()
            self.cam.save_trigger.set()
        else:
            self.stop_saving()

    def start_acquisition(self):
        if hasattr(self,'excitation_trigger'):
            self.excitation_trigger.arm()
            display('Camera LED stim trigger armed.')
        self.start_trigger.set()

    def stop_acquisition(self):
        self.start_trigger.clear()
        if hasattr(self,'excitation_trigger'):
            self.excitation_trigger.disarm()
        
    def start(self):
        self.start_trigger.clear()
        if hasattr(self,'excitation_trigger'):
            self.excitation_trigger.start()
            self.excitation_trigger.disarm()
        if hasattr(self,'writer'):
            if not self.writer is None:
                self.writer.start()
        if hasattr(self,'cam'):
            self.cam.start()
        if hasattr(self,'excitation_trigger'):
            self.excitation_trigger.arm()

    def set_filename(self,name):
        if not self.writer is None:
            self.writer.set_filename(name)
        elif self.driver.lower() == 'nidaq':
            self.cam.recorder.set_filename(name)
        else:
            display('[Camera] Setting serial recorder filename.')
            self.cam.eventsQ.put('filename='+name)

        
    def _init_pco_cam(self,parameters):
        try:
            from .pco import PCOCam
        except Exception as err:
            print(err)
            print(''' 
            
                    Could not load the PCO driver. 

    If you want to record from PCO cameras install the PCO driver.
            
            pip install pco>2.0.1
           
    If not you have the wrong config file.

            Edit the file in USERHME/labcams/default.json and delete the PCO cam or use the -c option

''')
        
        self.cam = PCOCam(cam_id=self.cam_id,
                          out_q = self.recorder_q,
                          start_trigger = self.start_trigger,
                          stop_trigger = self.stop_trigger,
                          save_trigger = self.save_trigger,
                          hardware_trigger = self.hardware_trigger_event,
                          **parameters)
        
    def _init_pvcam_cam(self,parameters):
        try:
            from .pvcam import PVCam
        except Exception as err:
            print(err)
            print(''' 
            
                    Could not load the PVCAM driver. 

    If you want to record from PVCAM cameras install the PyVCam driver.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the PVCAM cam or use the -c option

''')
        
        self.cam = PVCam(cam_id = self.cam_id,
                          out_q = self.recorder_q,
                          start_trigger = self.start_trigger,
                          stop_trigger = self.stop_trigger,
                          save_trigger = self.save_trigger,
                          hardware_trigger = self.hardware_trigger_event,
                          **parameters)

    def _init_nidaq_cam(self,parameters):
        try:
            from .nidaq_acq import NIDAQ
        except Exception as err:
            print(err)
            print('''
    Could not load the NIDAQ driver.

Please install nidaqmx using pip and NIDAQmx from the National Instruments website.

            ''')
        self.cam = NIDAQ(start_trigger = self.start_trigger,
                         stop_trigger = self.stop_trigger,
                         save_trigger = self.save_trigger,
                         out_q = self.recorder_q,
                         **parameters)
        display('\t DAQ device recording: {0}'.format(self.name))
        #for k in np.sort(list(cam.keys())):
        #    if not k == 'name' and not k == 'recorder':
        #        display('\t\t - {0} {1}'.format(k,cam[k]))
        #    cam['recorder'] = 'daq'
    
        
    def _init_qimaging_cam(self, parameters):
        try:
            from .qimaging import QImagingCam
        except Exception as err:
            print(err)
            print(''' 
            
                    Could not load the QImaging driver. 
    If you want to record from QImaging cameras install the QImaging driver.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the QImaging cam or use the -c option 

''')
        self.cam = QImagingCam(cam_id=self.cam_id,
                               out_q = self.recorder_q,
                               start_trigger = self.start_trigger,
                               stop_trigger = self.stop_trigger,
                               save_trigger = self.save_trigger,
                               hardware_trigger = self.hardware_trigger_event,
                               **parameters)
    def _init_ximea_cam(self,parameters):
        try:
            from .ximeacam import XimeaCam
        except Exception as err:
            print(''' 
            
            Could not load the Ximea driver. 

    If you want to record from Ximea cameras install the Ximea driver.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the ximea cam or use the -c option

''')
            raise(err)
        self.cam = XimeaCam(cam_id = self.cam_id,
                            start_trigger = self.start_trigger,
                            stop_trigger = self.stop_trigger,
                            save_trigger = self.save_trigger,
                            out_q = self.recorder_q,
                            hardware_trigger = self.hardware_trigger_event,
                            **parameters)


    def _init_pointgrey_cam(self,parameters):
        try:
            from .pointgreycam import PointGreyCam
        except Exception as err:
            print(err)
            
            print(''' 
            
                    Could not load the PointGrey driver.
 
    If you want to record from PointGrey/FLIR cameras install the Spinaker SDK.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the PointGrey cam or use the -c option

''')
        if 'roi' in parameters.keys():
            if parameters['roi'] is str:
                if ',' in parameters['roi']:
                    parameters['roi'] = [
                        int(c.strip('[').strip(']')) for c in parameters['roi'].split(',')]
                else:
                    parameters['roi'] = []
        self.cam = PointGreyCam(cam_id = self.cam_id,
                                start_trigger = self.start_trigger,
                                stop_trigger = self.stop_trigger,
                                save_trigger = self.save_trigger,
                                out_q = self.recorder_q,
                                **parameters)
        
    def _init_basler_cam(self, parameters):
        try:
            from .basler import BaslerCam
        except Exception as err:
            print(err)
            print(''' 
            
                    Could not load the Basler driver. 

    If you want to record from BASLER cameras install the pypylon driver (pip install).
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the Basler cam or use the -c option

''')

        self.cam = BaslerCam(cam_id = self.cam_id,
                             start_trigger = self.start_trigger,
                             stop_trigger = self.stop_trigger,
                             save_trigger = self.save_trigger,
                             out_q = self.recorder_q,
                             **parameters)

    def _init_avt_cam(self, parameters):
        ''' Exposed parameters for AVT cams
        exposure = 29000
        frame_rate = 30.
        gain = 10
        frame_timeout = 100
        n_frame_buffers = 10
        trigger_source = 'Line1'
        trigger_mode = 'LevelHigh'
        trigger_selector = 'FrameStart'
        acquisition_mode = 'Continuous'
        n_triggered_frames = 1000
        frame_timeout = 100
        '''
        try:
            from .avt import AVTCam
        except Exception as err:
            print(''' 
            
            Could not load the Allied Vision Technologies driver. 
            
    If you want to record from AVT cameras install the Vimba SDK and pimba.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json

            ''')
            raise(err)
        self.cam = AVTCam(cam_id = self.cam_id,
                          start_trigger = self.start_trigger,
                          stop_trigger = self.stop_trigger,
                          save_trigger = self.save_trigger,
                          out_q = self.recorder_q,
                          hardware_trigger = self.hardware_trigger_event,
                          **parameters)
    def close(self):
        self.stop_acquisition()
        self.cam.close()
        self.cam.stop_saving()
        if not self.writer is None:
            self.writer.stop()
        if hasattr(self,'excitation_trigger'):
            self.excitation_trigger.close()

        self.cam.join()
        if not self.writer is None:
            self.writer.join()

        
