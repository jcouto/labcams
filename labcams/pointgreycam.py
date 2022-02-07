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

import PySpin
from .cams import *
# Adapted from point grey spinnaker examples

def pg_device_info(nodemap):
    """
    This function prints the device information of the camera from the transport
    layer; please see NodeMapInfo example for more in-depth comments on printing
    device information from the nodemap.
    
    :param nodemap: Transport layer device nodemap from camera.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True
        # Retrieve and display Device Information
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))
        if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('[PointGrey] - %s: %s' % (node_feature.GetName(),
                                                node_feature.ToString()
                                                if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('[PointGrey] - Device control information not available.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False
    return result

def pg_image_settings(nodemap,X=None,Y=None,W=None,H=None,pxformat='Mono8'):
    """
    Configures a number of settings on the camera including offsets  X and Y, width,
    height, and pixel format. These settings must be applied before BeginAcquisition()
    is called; otherwise, they will be read only. Also, it is important to note that
    settings are applied immediately. This means if you plan to reduce the width and
    move the x offset accordingly, you need to apply such changes in the appropriate order.

    :param nodemap: GenICam nodemap.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True

        # Apply mono 8 pixel format
        #
        # *** NOTES ***
        # Enumeration nodes are slightly more complicated to set than other
        # nodes. This is because setting an enumeration node requires working
        # with two nodes instead of the usual one.
        #
        # As such, there are a number of steps to setting an enumeration node:
        # retrieve the enumeration node from the nodemap, retrieve the desired
        # entry node from the enumeration node, retrieve the integer value from
        # the entry node, and set the new value of the enumeration node with
        # the integer value from the entry node.
        #
        # Retrieve the enumeration node from the nodemap
        node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
        if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):

            # Retrieve the desired entry node from the enumeration node
            node_pixel_format_mono8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName(pxformat))
            if PySpin.IsAvailable(node_pixel_format_mono8) and PySpin.IsReadable(node_pixel_format_mono8):
                # Retrieve the integer value from the entry node
                pixel_format_mono8 = node_pixel_format_mono8.GetValue()
                # Set integer as new value for enumeration node
                node_pixel_format.SetIntValue(pixel_format_mono8)
                # Set width
        node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
        if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
            if W is None:
                W = node_width.GetMax()
            node_width.SetValue(W)
        else:
            display('[PointGrey] -  Width not available...')

        # Set height
        node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
        if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
            if H is None:
                H = node_height.GetMax()
            node_height.SetValue(H)
        else:
            display('[PointGrey] - Height not available...')
        # Apply offset X
        node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
        if PySpin.IsAvailable(node_offset_x) and PySpin.IsWritable(node_offset_x):
            if X is None:
                X = node_offset_x.GetMin()
            node_offset_x.SetValue(int(X))
        else:
            display('[PointGrey] - Offset X not available...')

        # Apply offset Y
        node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
        if PySpin.IsAvailable(node_offset_y) and PySpin.IsWritable(node_offset_y):
            if Y is None:
                Y = node_offset_y.GetMin()
            node_offset_y.SetValue(int(Y))
        else:
            display('[PointGrey] - Offset Y not available...')

    except PySpin.SpinnakerException as ex:
        display('[PointGrey] Error: %s' % ex)
        return False
    return result


class PointGreyCam(GenericCam):
    def __init__(self,
                 camId = None,
                 serial = None,
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
        super(PointGreyCam,self).__init__(outQ = outQ, recorderpar=recorderpar)
        self.drivername = 'PointGrey'
        self.hardware_trigger = hardware_trigger
        if camId is None:
            display('[PointGrey] - Need to supply a camera ID.')
        self.serial = serial
        if not serial is None:
            self.serial = int(serial)
            drv = PySpin.System.GetInstance()
            cam_list = drv.GetCameras()
            serials = []
            for i,c in enumerate(cam_list):
                c.Init()
                nodemap_tldevice = c.GetTLDeviceNodeMap()
                serial = PySpin.CStringPtr(
                    nodemap_tldevice.GetNode('DeviceSerialNumber'))
                serials.append(int(serial.ToString()))
                del nodemap_tldevice
            for c in cam_list:
                c.DeInit()
                del c
            cam_list.Clear()
            drv.ReleaseInstance()
            try:
                camId = int(np.where(np.array(serials)==self.serial)[0][0])
            except:
                txt = '''
                
FLIR camera serial not correct or camera missing?

Available serials are:
    {0}
'''.format('\t\t  and '.join([str(s) for s in serials]))
                raise(OSError(txt))
                
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
        display("Point Grey [{0}] - got info from camera.".format(self.cam_id))

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

    def get_one(self):
        self._cam_init()
        node_acquisition_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            display('Point Grey [{0}] - Unable to set acquisition mode(enum retrieval). Aborting...'.format(self.cam_id))
        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(
                node_acquisition_mode_continuous):
            display('Point Grey [{0}] - Unable to set acquisition mode to continuous (entry retrieval). Aborting...'.format(self.cam_id))
        # Set integer value from entry node as new value of enumeration node
        node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        self.cam.BeginAcquisition()
        try:
            img = self.cam.GetNextImage()
            frame = img.GetNDArray()
            img.Release()
        except PySpin.SpinnakerException as ex:
            display('Point Grey [{0}] - Error: {1}'.format(self.cam_id,ex))

        self._cam_close()
        self.cam = None
        self.cam_list = []
        self.cambuf = None
        if not self.drv is None:
            self.drv.ReleaseInstance()
            self.drv = None
        self.nodemap = None
        self.nodemap_tldevice = None
        return frame
    
    def set_framerate(self,framerate = 120):
        '''Set the exposure time is in us'''
        if self.triggered.is_set():
            display('Camera in trigger mode, skipping frame rate setting.')
            return
        if framerate is None:
           return 
        self.frame_rate = float(framerate)
        if not self.cam is None:
            self.frame_rate = min(self.cam.AcquisitionFrameRate.GetMax(),
                                  self.frame_rate)
            # Need to have the trigger off to set the rate.
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off) 
            self.cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
            try:
                self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                try:
                    self.cam.AcquisitionFrameRateEnable.SetValue(True)
                except:
                    framerate_enabled = PySpin.CBooleanPtr(
                        self.nodemap.GetNode('AcquisitionFrameRateEnabled'))
                    framerate_enabled.SetValue(True)
            except Exception as err:
                display('Point Grey [{0}] - Could not set frame rate enable.'.format(self.cam_id))
                print(err)
            if 'Chameleon3' in self.cammodel: 
                framerate_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('AcquisitionFrameRateAuto'))
                autooff = framerate_mode.GetEntryByName('Off')
                framerate_mode.SetIntValue(autooff.GetValue())
            try:
                self.cam.AcquisitionFrameRate.SetValue(self.frame_rate)
                display('PointGrey [{0}] - Frame rate: {1}'.format(
                    self.cam_id,self.cam.AcquisitionFrameRate.GetValue()))
            except Exception as err:
                self.frame_rate = self.cam.AcquisitionFrameRate.GetValue()
                display('PointGrey [{0}] - Could not set frame rate {1}'.format(self.cam_id,self.frame_rate))
                print(err)
                
    def set_binning(self,binning = 1):
        if binning is None:
           return 
        self.binning = int(binning)
        if not self.cam is None:
            self.cam.BinningVertical.SetValue(binning)
            if self.cam.BinningHorizontal.GetAccessMode() == PySpin.RW:
                self.cam.BinningHorizontal.SetValue(binning)

    def set_exposure(self,exposure=None):
        '''Set the exposure time is in us'''        
        if exposure is None:
            if not self.cam is None:
                self.exposure = self.cam.ExposureTime.GetValue()
            return
        self.exposure = exposure
        if not self.cam is None:
            self.cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
            if self.cam.ExposureAuto.GetAccessMode() != PySpin.RW:
                display('PointGrey [{0}] - Cannot disable automatic exposure.'.format(self.cam_id))
                return
            self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            if self.cam.ExposureTime.GetAccessMode() != PySpin.RW:
                display('PointGrey [{0}] - Cannot write to exposure control.'.format(self.cam_id))      
                return
            exposure_time_to_set = min(self.cam.ExposureTime.GetMax(),
                                       exposure)
            try:
                self.cam.ExposureTime.SetValue(exposure_time_to_set)
            except Exception as err:
                display('Pointgrey [{0}] - could not set exposure {1}'.format(self.cam_id,exposure_time_to_set ))
                print(err)

    def set_gamma(self,gamma=None):
        '''Set gamma'''
        if gamma is None:
            return
        self.gamma = gamma
        if not self.cam is None:
            genable = PySpin.CBooleanPtr(self.nodemap.GetNode("GammaEnabled"))
            if not PySpin.IsWritable(genable):
                try: # some cameras dont have this
                    cprocess = PySpin.CBooleanPtr(
                        self.nodemap.GetNode("OnBoardColorProcessEnabled"))
                    cprocess.SetValue(True)
                except:
                    pass
            if PySpin.IsWritable(genable):
                genable.SetValue(True)
            if self.cam.Gamma.GetAccessMode() != PySpin.RW:
                display('PointGrey [{0}] - Cannot set gamma.'.format(self.cam_id))
                return
            try:
                self.cam.Gamma.SetValue(self.gamma)
            except Exception as err:
                display('Pointgrey [{0}] - could not set gamma {1}'.format(
                    self.cam_id, self.gamma))
                print(err)
            display('Pointgrey [{0}] - Gamma set to: {1}'.format(
                self.cam_id, self.cam.Gamma.GetValue()))
            
    def set_gain(self,gain = 1):
        '''Set the gain is in dB'''
        if gain is None:
            return
        self.gain = gain
        if not self.cam is None:
            self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
            try:
                self.cam.Gain.SetValue(self.gain)
            except Exception as err:
                display('Pointgrey [{0}] - could not set gain {1}'.format(self.cam_id,self.gain))
                print(err)
            
    def _cam_init(self, set_gpio=True):
        self.drv = PySpin.System.GetInstance()
        version = self.drv.GetLibraryVersion()
        display('[PointGrey] - Library version: %d.%d.%d.%d' % (version.major,
                                                                version.minor,
                                                                version.type,
                                                                version.build))
        self.cam_list = self.drv.GetCameras()
        ncameras = self.cam_list.GetSize()
        if ncameras == 0:
            self.cam_list.Clear()
            display('[PointGrey] - no cameras connected.')
            self.drv.ReleaseInstance()
            raise ValueError
        
        self.cam = self.cam_list[self.cam_id]
        self.cam.Init()
        # set the buffer to read olderst first
        s_node_map = self.cam.GetTLStreamNodeMap()
        handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode('StreamBufferHandlingMode'))
        handling_mode_entry = handling_mode.GetEntryByName('OldestFirst')
        handling_mode.SetIntValue(handling_mode_entry.GetValue())

        # Set the trigger and exposure off so to be able to set other parameters
        self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        self.cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
        
        self.cam.ChunkModeActive.SetValue(True)
        #self.cam.ChunkSelector.SetValue(PySpin.ChunkSelector_ExposureLineStatusAll)
        #self.cam.ChunkEnable.SetValue(True)
        self.cam.ChunkSelector.SetValue(PySpin.ChunkSelector_ExposureTime)
        self.cam.ChunkEnable.SetValue(True)
        #self.cam.ChunkSelector.SetValue(PySpin.ChunkSelector_FrameCounter)
        self.nodemap_tldevice = self.cam.GetTLDeviceNodeMap()
        serial = PySpin.CStringPtr(
            self.nodemap_tldevice.GetNode('DeviceSerialNumber'))
        self.cammodel = PySpin.CStringPtr(
            self.nodemap_tldevice.GetNode('DeviceModelName')).ToString()
        self.nodemap = self.cam.GetNodeMap()
        display('PointGrey [{0}] - Serial number {1} - model {2}'.format(self.cam_id,
                                                                         serial.ToString(),
                                                                         self.cammodel))
        if False:
            display('[PointGrey] - timestamp is enabled.')
        x,y,w,h = self.roi
        self.set_binning(self.binning)
        # reset size first
        pg_image_settings(self.nodemap,X=0,Y=0,
                          W=None,H=None,pxformat=self.pxformat)
        pg_image_settings(self.nodemap,X=x,Y=y,W=w,H=h,pxformat=self.pxformat)
        self.cam.ExposureAuto.SetValue(0)
        
        genable = PySpin.CBooleanPtr(self.nodemap.GetNode("AcquisitionFrameRateAuto"))
        if PySpin.IsWritable(genable):
            genable.SetValue(0)
        
        genable = PySpin.CBooleanPtr(self.nodemap.GetNode("SharpenessAuto"))
        if PySpin.IsWritable(genable):
            genable.SetValue(0)
        # turn off the trigger mode before doing this
        self.set_exposure(self.exposure)
        self.set_framerate(self.frame_rate)
        self.set_gain(self.gain)
        self.set_gamma(self.gamma)

        self.lastframeid = -1
        self.nframes.value = 0
        self.camera_ready.set()
        self.prev_ts = 0
        self.lasttime = time.time()
        
    def _cam_startacquisition(self):
        node_acquisition_mode = PySpin.CEnumerationPtr(
            self.nodemap.GetNode('AcquisitionMode'))
        if (not PySpin.IsAvailable(node_acquisition_mode)
            or not PySpin.IsWritable(node_acquisition_mode)):
            display('[PointGrey] - Unable to set acquisition mode(enum retrieval). Aborting...')
        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if (not PySpin.IsAvailable(node_acquisition_mode_continuous) or
            not PySpin.IsReadable(node_acquisition_mode_continuous)):
            display('[PointGrey] - Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
        # Set integer value from entry node as new value of enumeration node
        node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        if self.triggered.is_set(): # One can use the hardware_trigger option for these cameras
            # Line 3 for triggering (hardcoded for now)
            self.cam.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
            display('PointGrey [{0}] - Triggered mode ON.'.format(self.cam_id))            
        else:
            display('PointGrey [{0}] - Triggered mode OFF.'.format(self.cam_id))
            
        # Set GPIO lines 2 and 3 to input by default 
        self.cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
        self.cam.LineMode.SetValue(PySpin.LineMode_Input)
        self.cam.LineSelector.SetValue(PySpin.LineSelector_Line3)
        self.cam.LineMode.SetValue(PySpin.LineMode_Input)
        if 'Blackfly S' in self.cammodel: # on Blackfly S turn off 3.3V output on line 2 (Used for sync)
            self.cam.LineSelector.SetValue(eval('PySpin.LineSelector_Line2'))
            self.cam.V3_3Enable.SetValue(False)
            
        if not self.hardware_trigger is None:
            d = '3' # line 3 is the default hardware trigger
            if self.hardware_trigger[-1].isdigit():
                d = self.hardware_trigger[-1]
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
            if 'in_line' in self.hardware_trigger:
                self.cam.LineSelector.SetValue(eval('PySpin.LineSelector_Line' + d))
                self.cam.LineMode.SetValue(PySpin.LineMode_Input)
                self.cam.TriggerSource.SetValue(eval('PySpin.TriggerSource_Line' + d))
                self.cam.TriggerActivation.SetValue(
                    PySpin.TriggerActivation_FallingEdge) # Exposure line is inversed
                try:
                    self.cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
                except:
                    display('PointGrey [{0}] - TriggerOverlap could not be set.')
                self.cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed) #PySpin.ExposureMode_TriggerWidth)
                self.cam.TriggerSource.SetValue(eval('PySpin.TriggerSource_Line'+d))
                self.cam.TriggerSelector.SetValue(PySpin.TriggerSelector_FrameStart) # in CM3
                self.cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
                display('PointGrey [{0}] - External trigger mode ON on line {1}.'.format(self.cam_id, d))    
            if 'out_line' in self.hardware_trigger:
                display('This is a master camera, sleeping .5 sec.')
                time.sleep(0.2)
        if not self.hardware_trigger is None:
            if 'out_line' in self.hardware_trigger:
                # Use line 1 for Blackfly S
                # Use line 2 or 3 for Chamaeleon
                display('PointGrey [{0}] - Setting the output line for line {1}'.format(self.cam_id, d))
                if not 'Chameleon3' in self.cammodel: # delay the chamaeleon until after started
                    self.cam.LineSelector.SetValue(eval('PySpin.LineSelector_Line'+d))
                    self.cam.LineMode.SetValue(PySpin.LineMode_Output)
                    self.cam.LineSource.SetValue(PySpin.LineSource_ExposureActive)
                if 'Blackfly S' in self.cammodel: # on Blackfly S connect line 1 to line 2 with a 10kOhm resistor 
                    display('PointGrey [{0}] - Setting 3.3V Enable on line 2'.format(self.cam_id))
                    self.cam.LineSelector.SetValue(eval('PySpin.LineSelector_Line2'))
                    self.cam.V3_3Enable.SetValue(True)
        self.cam.BeginAcquisition()
        if not self.hardware_trigger is None: # start chameleon trigger after the cam because it is constantly on
            if 'out_line' in self.hardware_trigger and 'Chameleon3' in self.cammodel:
                self.cam.LineSelector.SetValue(eval('PySpin.LineSelector_Line'+d))
                self.cam.LineMode.SetValue(PySpin.LineMode_Output)
                self.cam.LineSource.SetValue(PySpin.LineSource_ExposureActive)
        display('PointGrey [{0}] - Started acquitition.'.format(self.cam_id))
        
    def _cam_stopacquisition(self):
        '''stop camera acq'''
        if not self.hardware_trigger is None:
            #if 'out_line' in self.hardware_trigger:
            d = '3'
            if self.hardware_trigger[-1].isdigit():
                d = self.hardware_trigger[-1]
            if 'out_line' in self.hardware_trigger:
                # Reading the last image and stopping the camera (To clear the buffer).
                if hasattr(self,'img'): # or not self.cam.AcquisitionStatus.GetValue():
                    frame,metadata = self._cam_loop()
                    if not frame is None:
                        self._handle_frame(frame,metadata)
                if not 'Blackfly S' in self.cammodel: # can't set line 1 to input on Blackfly S
                    self.cam.LineSelector.SetValue(eval('PySpin.LineSelector_Line' + d))
                    self.cam.LineMode.SetValue(PySpin.LineMode_Input) # stop output
                self.cam.EndAcquisition()
                return
            if 'in_line' in self.hardware_trigger:
                # to make sure all triggers are acquired (stop only when all frames have been received).
                is_done = False
                while not is_done:
                    if not hasattr(self,'img'):# or not self.cam.AcquisitionStatus.GetValue():
                        break
                    frame,metadata = self._cam_loop()
                    if frame is None:
                        is_done=True
                        break
                    else:
                        # Send it to the recorder
                        self._handle_frame(frame,metadata)
        self.cam.EndAcquisition()
        self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

    def _cam_loop(self):
        try:
            img = self.cam.GetNextImage(100,0)
        except PySpin.SpinnakerException as ex:
            if '-1011' in str(ex):
                img = None
            else:
                display('[PointGrey] - Error: %s' % ex)
        if not img is None:
            if img.IsIncomplete():
                print('Image incomplete with image status %d ...' % image_result.GetImageStatus())
            else:
                frame = img.GetNDArray()
            frameID = img.GetFrameID()
            timestamp = img.GetTimeStamp()*1e-9
            linestat = self.cam.LineStatusAll()
            #frameinfo = img.GetChunkData()
            #linestat = frameinfo.GetFrameID()
            #display('Line {0} {1}'.format(linestat,frameinfo.GetExposureLineStatusAll())) # 
            img.Release()
            self.nframes.value = frameID
            return frame,(frameID,timestamp,linestat)
        else:
            return None,(None,None,None)

    def _cam_close(self):
        if not self.cam is None:
            try:
                self._cam_stopacquisition()
                display('PointGrey [{0}] - Stopped acquitition.'.format(self.cam_id))          
            except:
                pass
            self.cam.DeInit()
            del self.cam
            
        if not self.drv is None:
            del self.nodemap_tldevice
            del self.nodemap
            self.cam_list.Clear()
            self.drv.ReleaseInstance()
            self.drv = None
            
