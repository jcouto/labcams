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
# Allied Vision Technologies cameras
try:
    import vmbpy
except:
    print('Installing vmbpy to support the AVT cameras' )
    os.system('python -m pip install vmbpy')
    import vmbpy

def get_camera(camera_id):
    with vmbpy.VmbSystem.get_instance() as vmb:
        if camera_id:
            try:
                return vmb.get_camera_by_id(str(camera_id))

            except vmbpy.VmbCameraError:
                get_avt_cams()
                raise(OSError(f'[AVT Vimba]: Failed to access Camera {camera_id}.'))

        else:
            cams = vmb.get_all_cameras()
            if not cams:
                raise(vmbpy.VmbCameraError('[AVT Vimba] No Cameras accessible. Abort.'))
            return cams
        
def get_avt_cams():
    cam_ids = {}
    with vmbpy.VmbSystem.get_instance() as vmb:
        cams = vmb.get_all_cameras()
        for cam in cams:
            cam_id = cam.get_id()
            model = cam.get_model()
            print(f' \t {model} id: {cam_id}')
            cam_ids[cam_id] = model
    return cam_ids

def adjust_gev_packet(cam):
    with cam: # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        try:
            stream = cam.get_streams()[0]
            stream.GVSPAdjustPacketSize.run()
            while not stream.GVSPAdjustPacketSize.is_done():
                pass
        except (AttributeError, VmbFeatureError):
            pass



        
class AVTCam(GenericCam):    
    def __init__(self,
                 cam_id = None,
                 name = '',
                 serial = None,
                 out_q = None,
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,
                 exposure = None,
                 frame_rate = None,
                 gain = None,
                 frame_timeout = 100,
                 n_frame_buffers = 300,
                 binning = None,
                 gamma = None,
                 roi = [],
                 pxformat = 'Mono8',
                 exposure_auto = False,
                 outputs = [],
                 trigger_source = 'Line1',
                 trigger_mode = 'LevelHigh',
                 trigger_selector = 'FrameStart',
                 hardware_trigger = None,
                 recorderpar = None,
                 **kwargs):
        self.drivername = 'AVT'

        super(AVTCam,self).__init__(cam_id = cam_id,
                                    name = name,
                                    out_q = out_q,
                                    start_trigger = start_trigger,
                                    stop_trigger = stop_trigger,
                                    save_trigger = save_trigger,                
                                    recorderpar = recorderpar)
        self.drivername = 'AVT'
        self.hardware_trigger = hardware_trigger
        if self.hardware_trigger is None:
            self.hardware_trigger = ''
        self.serial = serial
        self.avtid = None
        self.frame_buffer = None
        if not serial is None:
            self.serial = serial
            cam = get_camera(self.serial)
        else:
            display('Set the serial in the preference file to use AVT cameras.')
            txt = '''
                
AVT camera serial not correct set.

Available serials are:
    {0}
'''.format(get_avt_cams())
            raise(OSError(txt))
                
        self.drv = None
        if not len(roi):
            roi = [None,None,None,None]
        #self.pxformat = pxformat
        self.gamma = gamma
        self.outputs = outputs
        self.binning = binning
        self.exposure = exposure
        self.frame_rate = frame_rate
        if not self.frame_rate is None:
            self.fs.value = self.frame_rate

        self.gain = gain
        self.roi = roi
        with vmbpy.VmbSystem.get_instance() as smb:
            with cam as c:
                frameb = c.get_frame()
                fet = c.get_all_features()
                print(c.get_feature_by_name('LineStatus'))
        self.h.value = frameb.get_height()#frame.shape[0]
        self.w.value = frameb.get_width()#frame.shape[1]
        self.nchan.value = 1
        # color not allowed now...
        #if len(frame.shape) == 3:
        #    self.nchan.value = frame.shape[2] 
        self.dtype = np.uint8 #frame.dtype
        self._init_variables(self.dtype)
        #self._cam_init()
        #import ipdb
        #ipdb.set_trace()
        display("[AVT {0}] - got info from camera.".format(self.cam_id))

    def set_exposure(self,exposure=None):
        '''Set the exposure time is in us'''        
        if exposure is None:
            if not self.cam is None:
                self.exposure = self.cam.ExposureTime.get()
            return
        self.exposure = exposure
        if not self.cam is None:
            try:
                self.cam.ExposureTime.set(self.exposure)
                display('[AVT {0}] - Exposure {1}'.format(self.cam_id,self.cam.ExposureTime.get()))
            except Exception as err:
                display('[AVT {0}] - could not set exposure {1}'.format(self.cam_id,self.exposure))
                print(err)
            
        
    def set_gamma(self,gamma=None):
        '''Set gamma'''
        if gamma is None:
            return
        self.gamma = gamma
        if not self.cam is None:
            try:
                self.cam.Gamma.set(self.gamma)
            except Exception as err:
                display('[AVT {0}] - could not set gamma {1}'.format(
                    self.cam_id, self.gamma))
                print(err)
            display('[AVT {0}] - Gamma set to: {1}'.format(
                self.cam_id, self.cam.Gamma.get()))
        
    def set_gain(self,gain = 1):
        '''Set the gain is in dB'''
        if gain is None:
            return
        self.gain = gain
        if not self.cam is None:
            try:
                self.cam.Gain.set(self.gain)
                display('[AVT {0}] - Gain set to: {1}'.format(
                    self.cam_id, self.cam.Gain.get()))

            except Exception as err:
                display('[AVT {0}] - could not set gain {1}'.format(self.cam_id,self.cam.Gain.get()))
                print(err)
                
    def set_framerate(self,framerate = 120):
        '''Set the frame rate in Hz'''
        if framerate is None:
           return 
        self.frame_rate = float(framerate)
        if self.frame_rate is None:
            pass
        else:
            if not self.cam is None:
                self.frame_rate = min(self.cam.AcquisitionFrameRate.get_range()[1],
                                      self.frame_rate)
                
                try:
                    self.cam.AcquisitionFrameRate.set(self.frame_rate)
                    display('[AVT {0}] - Frame rate: {1}'.format(
                        self.cam_id,self.cam.AcquisitionFrameRate.get()))
                except Exception as err:
                    self.frame_rate = self.cam.AcquisitionFrameRate.get()
                    display('[AVT {0}] - Could not set frame rate {1}'.format(self.cam_id,self.frame_rate))
                    print(err)
            self.fs.value = self.frame_rate


    def _init_controls(self):
        self.ctrevents = dict(
            frame_rate=dict(
                function = 'set_framerate',
                widget = 'float',
                variable = 'frame_rate',
                units = 'hz',
                type = 'float',
                min = 0.1,
                max = 1000,
                step = 10),
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
                step = 100),
            gamma=dict(
                function = 'set_gamma',
                widget = 'float',
                variable = 'gamma',
                units = 'NA',
                type = 'float',
                min = 0,
                max = 3.9,
                step = 0.01))
        
    def _cam_init(self):
        self.drv = vmbpy.VmbSystem.get_instance()
        self.cam = get_camera(self.serial)
        self.drv = vmbpy.VmbSystem.get_instance()
        type(self.drv).__enter__(self.drv)
        type(self.cam).__enter__(self.cam)
        self.cam.set_pixel_format(vmbpy.PixelFormat.Mono8)
        display("[AVT] set the pixel format to Mono8")
        self.set_framerate(self.frame_rate)
        if not self.exposure is None:
            self.set_exposure(self.exposure)
        self.set_gain(self.gain)
        self.set_gamma(self.gamma)        
        self.cam.LineSelector = 'Line0'
        self.cam.LineMode = 'Input'
        # the line status is not returned by the frame.
        self.camera_ready.set()

        
    def _start_acquisition(self):
        self.cam.start_streaming()
        
    def _cam_loop(self):
        #frame = self.cam.get_frame()
        if self.frame_buffer is None:
            self.frame_buffer = self.cam.get_frame_generator(None)
        frame = next(self.frame_buffer)
        ff = frame.as_numpy_ndarray().squeeze().copy()
        frameid = frame._frame.frameID #self.nframes.value + 1
        timestamp = frame.get_timestamp()
        return ff,(frameid,timestamp,self.cam.LineStatus)
    
    def _stop_acquisition(self):
        self.cam.stop_streaming()
        self.frame_buffer = None

    def _cam_close(self, do_stop = True):
        if not self.cam is None:
            if do_stop:
                self._cam_stopacquisition()
            self.cam.__exit__(None,None,None)
            self.cam = None
            self.drv.__exit__(None,None,None)
            self.drv = None
