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

import PyCapture2 as pc2
from .cams import *

class PointGreyCam(GenericCam):
    def __init__(self,
                 camId = None,
                 outQ = None,
                 binning = 1,
                 frameRate = 120,
                 gain = 10,
                 roi = [],
                 triggerSource = np.uint16(0),
                 outputs = ['XI_GPO_EXPOSURE_ACTIVE'],
                 triggered = Event(),
                 **kwargs):
        super(PointGreyCam,self).__init__()
        self.drivername = 'PointGrey'
        if camId is None:
            display('[PointGrey] - Need to supply a camera ID.')
        self.cam_id = camId
        self.triggered = triggered
        self.queue = outQ
        self.outputs = outputs
        self.binning = binning
        self.frame_rate = frameRate
        self.gain = gain
        self.roi = roi
        frame = self.get_one()
        self.h = frame.shape[0]
        self.w = frame.shape[1]
        self.nchannels = 1
        self.dtype = np.uint16
        self._init_variables(self.dtype)
        self.triggerSource = triggerSource
        self.img[:] = np.reshape(frame,self.img.shape)[:]

        display("[Point Grey {0}] - got info from camera.".format(self.cam_id))

    def cam_info(self,cam):
        cam_info = cam.getCameraInfo()
        print('\n*** Point Grey Research ***\n')
        print('Serial number - %d' % cam_info.serialNumber)
        print('Camera model - %s' % cam_info.modelName)
        print('Camera vendor - %s' % cam_info.vendorName)
        print('Sensor - %s' % cam_info.sensorInfo)
        print('Resolution - %s' % cam_info.sensorResolution)
        print('Firmware version - %s' % cam_info.firmwareVersion)
        print('Firmware build time - %s' % cam_info.firmwareBuildTime)

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
                max = 18,
                step = 1))

    def get_one(self):
        self._cam_init()
        self.cam.startCapture()
        img = self.cam.retrieveBuffer()
        frame = img.getData().reshape([img.getRows(),img.getCols()])
        self.cam.stopCapture()
        self.cam.disconnect()
        del self.bus
        self.cam = None
        self.cambuf = None
        return frame
    
    def set_framerate(self,framerate = 120):
        '''Set the exposure time is in us'''
        self.frame_rate = framerate
        if not self.cam is None:
            tmp = self.cam.getProperty(pc2.PROPERTY_TYPE.FRAME_RATE)
            tmp.absValue = self.frame_rate
            tmp.onOff = True
            self.cam.setProperty(tmp)

    def set_gain(self,gain = 10):
        '''Set the gain is in dB'''
        self.gain = gain
        if not self.cam is None:
            tmp = self.cam.getProperty(pc2.PROPERTY_TYPE.GAIN)
            tmp.absValue = self.gain
            tmp.onOff = True
            self.cam.setProperty(tmp)

    def _cam_init(self,set_gpio=True):
        self.bus = pc2.BusManager()
        self.cam = pc2.Camera()
        if not self.bus.getNumOfCameras():
            display('No Point Grey Research cameras detected')
            raise
        # Run example on the first camera
        uid = self.bus.getCameraFromIndex(self.cam_id)
        self.cam.connect(uid)
        embedded_info = self.cam.getEmbeddedImageInfo()
        if embedded_info.available.timestamp:
            self.cam.setEmbeddedImageInfo(timestamp = True)
            enable_timestamp = True
        if enable_timestamp:
            display('[PointGrey] - timestamp is enabled.')
        else:
            display('[PointGrey] - timeStamp is disabled.') 
        fmt7_info, supported = self.cam.getFormat7Info(0)
        if supported:
            display('[PointGrey] - Max image pixels: ({}, {})'.format(
                fmt7_info.maxWidth, fmt7_info.maxHeight))
            if not len(self.roi):
                self.roi = [0,0,fmt7_info.maxWidth,fmt7_info.maxHeight]
            display('[PointGrey] - Image unit size: ({}, {})'.format(
                fmt7_info.imageHStepSize, fmt7_info.imageVStepSize))
            display('[PointGrey] - Offset unit size: ({}, {})'.format(
                fmt7_info.offsetHStepSize, fmt7_info.offsetVStepSize))
            #display('[PointGrey] - Pixel format bitfield: 0x{}'.format(
            #    fmt7_info.pixelFormatBitField))
            #if pc2.PIXEL_FORMAT.MONO8 & fmt7_info.pixelFormatBitField == 0:
            #    display('[PointGrey] - setting MONO8')
            x,y,w,h = self.roi
            fmt7_img_set = pc2.Format7ImageSettings(0,x, y,w,h,
                                                    pc2.PIXEL_FORMAT.MONO8)
            fmt7_pkt_inf, isValid = self.cam.validateFormat7Settings(fmt7_img_set)
            if not isValid:
                print('[PointGrey] - Format7 settings are not valid!')
            self.cam.setFormat7ConfigurationPacket(fmt7_pkt_inf.recommendedBytesPerPacket, fmt7_img_set)
        tmp = self.cam.getProperty(pc2.PROPERTY_TYPE.FRAME_RATE)
        tmp.absValue = self.frame_rate
        tmp.onOff = True
        self.cam.setProperty(tmp)
        tmp = self.cam.getProperty(pc2.PROPERTY_TYPE.FRAME_RATE)
        self.frame_rate = tmp.absValue
        display('[PointGrey] - Frame rate is:{0}'.format(self.frame_rate))
        # Set gain
        tmp = self.cam.getProperty(pc2.PROPERTY_TYPE.GAIN)
        tmp.absValue = self.gain
        tmp.onOff = True
        self.cam.setProperty(tmp)
        #start communication
        #self.cam.open_device()
        #self.cam.set_acq_timing_mode('XI_ACQ_TIMING_MODE_FREE_RUN')
        #self.cam.set_exposure(self.exposure)
        #self.cam.set_binning_vertical(self.binning)
        #self.cam.set_binning_horizontal(self.binning)
        # Set the GPIO
        #self.cam.set_gpi_selector('XI_GPI_PORT1')
        #self.cam.set_trigger_source('XI_TRG_OFF')

        #if set_gpio:
        #    self.cam.set_gpo_selector('XI_GPO_PORT1')
            # for now set the GPO to blink in software (port1 will do that for sync purposes, the test cam does not support XI_GPO_EXPOSURE_PULSE)
        #    self.cam.set_gpo_mode('XI_GPO_ON'); #XI_GPO_EXPOSURE_PULSE
        #    if self.triggered.is_set():
        #        self.cam.set_gpi_mode('XI_GPI_TRIGGER')
        #        self.cam.set_trigger_source('XI_TRG_EDGE_RISING')
        self.lastframeid = -1
        self.nframes.value = 0
        self.camera_ready.set()
        self.prev_ts = 0
        self.lasttime = time.time()
    def _cam_startacquisition(self):
        self.cam.startCapture()

    def _cam_loop(self):
        img = self.cam.retrieveBuffer()
        frame = img.getData().reshape([self.h,self.w])
        frameID = self.lastframeid+1
        ts = img.getTimeStamp()
        timestamp = 0
        ntime = time.time()
        #display('loop rate : {0}'.format(1./(ntime - self.lasttime)))
        self.lasttime = ntime
        if self.saving.is_set():
            if not frameID == self.lastframeid :
                self.queue.put((frame.copy(),
                                (frameID,timestamp)))
        if not frameID == self.lastframeid:
            self.buf[:] = np.reshape(frame.copy(),self.buf.shape)[:]
            self.nframes.value += 1
        self.lastframeid = frameID
        
    def _cam_close(self):
        try:
            self.cam.stopCapture()
        except:
            display('[PointGrey] - Stop capture error... check this at some point.')
        self.cam.disconnect()
        del self.bus
        self.cam = None        
