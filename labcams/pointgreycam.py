import PySpin
from .cams import *
# Adapted from point grey spinnaker examples
class TriggerType:
    SOFTWARE = 1
    HARDWARE = 2

CHOSEN_TRIGGER = TriggerType.SOFTWARE

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

    except PySpin.SpinnakerException as ex:
        display('[PointGrey] Error: %s' % ex)
        return False
    return result


class PointGreyCam(GenericCam):
    def __init__(self,
                 camId = None,
                 serial = None,
                 outQ = None,
                 binning = 1,
                 frameRate = 120,
                 gain = 10,
                 roi = [],
                 pxformat = 'Mono8',
                 triggerSource = np.uint16(0),
                 outputs = ['XI_GPO_EXPOSURE_ACTIVE'],
                 triggered = Event(),
                 recorderpar=None,
                 **kwargs):
        super(PointGreyCam,self).__init__(outQ = outQ, recorderpar=recorderpar)
        self.drivername = 'PointGrey'
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
            print(serials)
            camId = int(np.where(np.array(serials)==self.serial)[0][0])
            print(camId)    
        self.drv = None
        self.cam_id = camId
        if not len(roi):
            roi = [None,None,None,None]
        self.pxformat = pxformat
        self.triggered = triggered
        self.outputs = outputs
        self.binning = binning
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

        node_acquisition_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            display('[PointGrey] - Unable to set acquisition mode(enum retrieval). Aborting...')
        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(
                node_acquisition_mode_continuous):
            display('[PointGrey] - Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
        # Set integer value from entry node as new value of enumeration node
        node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        self.cam.BeginAcquisition()
        try:
            img = self.cam.GetNextImage()
            frame = img.GetNDArray()
            img.Release()
        except PySpin.SpinnakerException as ex:
            display('[PointGrey] - Error: %s' % ex)

        self._cam_close()
        self.cam = None
        self.cam_list = []
        self.cambuf = None
        self.drv = None
        self.nodemap = None
        self.nodemap_tldevice = None
        return frame
    
    def set_framerate(self,framerate = 120):
        '''Set the exposure time is in us'''
        self.frame_rate = float(framerate)
        if not self.cam is None:
            try:
                self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off) # Need to have the trigger off to set the rate.
                self.cam.AcquisitionFrameRateEnable.SetValue(True)
            except:
                pass
            self.frame_rate = min(self.cam.AcquisitionFrameRate.GetMax(),self.frame_rate)
            self.cam.AcquisitionFrameRate.SetValue(self.frame_rate)


    def set_gain(self,gain = 10):
        '''Set the gain is in dB'''
        self.gain = gain
        if not self.cam is None:
            self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
            self.cam.Gain.SetValue(self.gain)

    def _cam_init(self,set_gpio=True):
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
        self.nodemap_tldevice = self.cam.GetTLDeviceNodeMap()
        serial = PySpin.CStringPtr(
            self.nodemap_tldevice.GetNode('DeviceSerialNumber'))
        display('[PointGrey] - Serial number {0}'.format(serial.ToString()))
        display('[PointGrey] - Camera model is {0}'.format(PySpin.CStringPtr(
            self.nodemap_tldevice.GetNode('DeviceModelName')).ToString()))
        
        self.nodemap = self.cam.GetNodeMap()

        if False:
            display('[PointGrey] - timestamp is enabled.')

        x,y,w,h = self.roi
        pg_image_settings(self.nodemap,X=x,Y=y,W=w,H=h,pxformat=self.pxformat)
        self.set_framerate(self.frame_rate)
        display('[PointGrey] - Frame rate is:{0}'.format(self.frame_rate))
        self.lastframeid = -1
        self.nframes.value = 0
        self.camera_ready.set()
        self.prev_ts = 0
        self.lasttime = time.time()
        
    def _cam_startacquisition(self):
        node_acquisition_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            display('[PointGrey] - Unable to set acquisition mode(enum retrieval). Aborting...')
        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(
                node_acquisition_mode_continuous):
            display('[PointGrey] - Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
        # Set integer value from entry node as new value of enumeration node
        node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        if self.triggered.is_set():
            self.cam.TriggerSource.SetValue(PySpin.TriggerSource_Line0)
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
            display('PointGrey [{0}] - Triggered mode ON.'.format(self.cam_id))            
        else:
            display('PointGrey [{0}] - Triggered mode OFF.'.format(self.cam_id))            
            self.cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
            
        self.cam.BeginAcquisition()
        display('PointGrey [{0}] - Started acquitition.'.format(self.cam_id))            


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
            img.Release()
            frameID = img.GetFrameID()
            timestamp = img.GetTimeStamp()*1e-9
            return frame,(frameID,timestamp)
        else:
            return None,(None,None)

    def _cam_close(self):
        if not self.cam is None:
            try:
                self.cam.EndAcquisition()
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
            
