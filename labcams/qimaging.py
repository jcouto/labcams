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
# QImaging cameras
from .qimaging_dll import *

class QImagingCam(GenericCam):
    def __init__(self, camId = None,
                 outQ = None,
                 exposure = 100000,
                 gain = 3500,frameTimeout = 100,
                 nFrameBuffers = 1,
                 binning = 2,
                 triggerType = 0,
                 triggered = Event(),
                 recorderpar = None):
        '''
        Qimaging camera (tested with the Emc2 only!)
            triggerType (0=freerun,1=hardware,5=software)
        '''
        super(QImagingCam,self).__init__()
        if camId is None:
            display('Need to supply a camera ID.')
            raise
        self.queue = outQ
        self.triggered = triggered
        self.triggerType = 0
        self.cam_id = camId
        self.estimated_readout_lag = 1257 # microseconds
        self.binning = binning
        self.exposure = exposure
        self.gain = gain
        self.frame_rate = 1./(self.exposure/1000.)
        self.frameTimeout = frameTimeout
        self.nbuffers = nFrameBuffers
        self.triggerType = triggerType
        ReleaseDriver()
        LoadDriver()
        cam = OpenCamera(ListCameras()[camId])
        cam.settings.readoutSpeed=0 # 0=20MHz, 1=10MHz, 7=40MHz
        cam.settings.imageFormat = 'mono16'
        cam.settings.binning = self.binning
        cam.settings.emGain = gain
        cam.settings.triggerType = 0
        cam.settings.exposure = self.exposure - self.estimated_readout_lag
        cam.settings.blackoutMode=True
        cam.settings.Flush()
        cam.StartStreaming()
        frame = cam.GrabFrame()
        self.dtype = np.uint16
        buf = np.frombuffer(frame.stringBuffer,
                            dtype = self.dtype).reshape(
                                (frame.width,frame.height))
        self.h = buf.shape[1]
        self.w = buf.shape[0]
        self._init_variables(dtype = self.dtype)
        cam.StopStreaming()
        cam.CloseCamera()
        ReleaseDriver()
        display("Got info from camera (name: {0})".format(camId))
        self.camera_ready = Event()

    def run(self):
        #buf = np.frombuffer(self.frame.get_obj(),
        #                    dtype = self.dtype).reshape([
        #                        self.w,self.h,self.nchan])
        ReleaseDriver()
        self.close_event.clear()
        while not self.close_event.is_set():
            self.nframes.value = 0
            LoadDriver()
            if not self.camera_ready.is_set():
                # prepare camera
                cam = OpenCamera(ListCameras()[self.cam_id])
                if cam.settings.coolerActive:
                    display('QImaging - cooler active.')
                cam.settings.readoutSpeed=0 # 0=20MHz, 1=10MHz, 7=40MHz
                cam.settings.imageFormat = 'mono16'
                cam.settings.binning = self.binning
                cam.settings.emGain = self.gain
                cam.settings.exposure = self.exposure - self.estimated_readout_lag
                if self.triggered.is_set():
                    triggerType = self.triggerType
                else:
                    triggerType = 0
                cam.settings.triggerType = triggerType
                cam.settings.blackoutMode=True
                cam.settings.Flush()
                queue = CameraQueue(cam)
                display('QImaging - Camera ready!')
                self.camera_ready.set()
                self.nframes.value = 0
                # Wait for trigger
            while not self.start_trigger.is_set():
                # limits resolution to 1 ms 
                time.sleep(0.001)
                if self.close_event.is_set():
                    break
            if self.close_event.is_set():
                queue.stop()
                del queue
                del cam
                break
            queue.start()
            #tstart = time.time()
            display('QImaging - Started acquisition.')
            self.camera_ready.clear()
            while not self.stop_trigger.is_set():
                # run and acquire frames
                try:
                    f = queue.get(True, 1)
                except queue.Empty:
                    continue
                self.nframes.value += 1
                frame = np.ndarray(buffer = f.stringBuffer,
                                   dtype = self.dtype,
                                   shape = (self.w,
                                            self.h)).copy()
                    
                #display("Time {0} - {1}:".format(str(1./(time.time()-tstart)),self.nframes.value))
                #tstart = time.time()
                timestamp = f.timeStamp
                frameID = f.frameNumber
                if self.saving.is_set():
                    self.was_saving = True
                    self.queue.put((frame.reshape([self.h,self.w]),
                                    (frameID,timestamp)))
                elif self.was_saving:
                    self.was_saving = False
                    self.queue.put(['STOP'])
                self.img[:] = np.reshape(frame,self.img.shape)[:]

                queue.put(f)

            queue.stop()
            del queue
            cam.settings.blackoutMode=False
            cam.settings.Flush()
            del cam
            self.saving.clear()
            self.start_trigger.clear()
            self.stop_trigger.clear()
            ReleaseDriver()
            time.sleep(0.01)
            display('QImaging - Stopped acquisition.')
