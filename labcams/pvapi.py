# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 15:17:31 2011

True Camera API that binds to the underlying PvAPI SDK.
This is the result of a lot of blood, sweat, and pain.

Not all functions are implemented, but example in example.py 
demonstrates successful initialization of the camera, captures a frame,
and then shuts down the driver engine.

multicamera.py shows how multiple cameras can be opened and displayed simultaneously.

Updated in July-September 2011 by Mikael Mannberg, Cranfield University, United Kingdom:
- Added error codes
- Added further configuration functions
- Support for Windows, Linux and Mac OS X on 32 and 64bit architectures
- Added Camera class to simplify camera management and multi-camera use

@author: coryli, mikaelmannberg
"""


from ctypes import *
import platform, sys
import numpy as np

class ResultValues():
    ePvErrSuccess       = 0        # No error
    ePvErrCameraFault   = 1        # Unexpected camera fault
    ePvErrInternalFault = 2        # Unexpected fault in PvAPI or driver
    ePvErrBadHandle     = 3        # Camera handle is invalid
    ePvErrBadParameter  = 4        # Bad parameter to API call
    ePvErrBadSequence   = 5        # Sequence of API calls is incorrect
    ePvErrNotFound      = 6        # Camera or attribute not found
    ePvErrAccessDenied  = 7        # Camera cannot be opened in the specified mode
    ePvErrUnplugged     = 8        # Camera was unplugged
    ePvErrInvalidSetup  = 9        # Setup is invalid (an attribute is invalid)
    ePvErrResources     = 10       # System/network resources or memory not available
    ePvErrBandwidth     = 11       # 1394 bandwidth not available
    ePvErrQueueFull     = 12       # Too many frames on queue
    ePvErrBufferTooSmall= 13       # Frame buffer is too small
    ePvErrCancelled     = 14       # Frame cancelled by user
    ePvErrDataLost      = 15       # The data for the frame was lost
    ePvErrDataMissing   = 16       # Some data in the frame is missing
    ePvErrTimeout       = 17       # Timeout during wait
    ePvErrOutOfRange    = 18       # Attribute value is out of the expected range
    ePvErrWrongType     = 19       # Attribute is not this type (wrong access function) 
    ePvErrForbidden     = 20       # Attribute write forbidden at this time
    ePvErrUnavailable   = 21       # Attribute is not available at this time
    ePvErrFirewall      = 22       # A firewall is blocking the traffic (Windows only)
    
    errors =   ['ePvErrSuccess', 'ePvErrCameraFault', 'ePvErrInternalFault', 'ePvErrBadHandle', \
        'ePvErrBadParameter', 'ePvErrBadSequence', 'ePvErrNotFound', 'ePvErrAccessDenied', \
        'ePvErrUnplugged', 'ePvErrInvalidSetup', 'ePvErrResources', 'ePvErrBandwidth', \
        'ePvErrQueueFull', 'ePvErrBufferTooSmall', 'ePvErrCancelled', 'ePvErrDataLost', \
        'ePvErrDataMissing', 'ePvErrTimeout', 'ePvErrOutOfRange', 'ePvErrWrongType',\
        'ePvErrForbidden', 'ePvErrUnavailable', 'ePvErrFirewall']
    
    descriptions = ['No error', 'Unexpected camera fault','Unexpected fault in PvAPI or driver','Camera handle is invalid',\
            'Bad parameter to API call', 'Sequence of API calls is incorrect', 'Camera or attribute not found',\
            'Camera cannot be opened in the specified mode', 'Camera was unplugged', 'Setup is invalid (an attribute is invalid)',\
            'System/network resources or memory not available', '1394 bandwidth not available', 'Too many frames on queue',\
            'Frame buffer is too small', 'Frame cancelled by user', 'The data for the frame was lost', 'Some data in the frame is missing',\
            'Timeout during wait', 'Attribute value is out of the expected range', 'Attribute is not this type (wrong access function)',\
            'Attribute write forbidden at this time', 'Attribute is not available at this time', 'A firewall is blocking the traffic (Windows only)']

class CameraInfoEx(Structure):
    """Struct that holds information about the camera"""
    
    _fields_ = [
    ("StructVer",c_ulong),
    ("UniqueId", c_ulong),
    ("CameraName", c_char*32),
    ("ModelName", c_char*32),
    ("PartNumber", c_char*32),
    ("SerialNumber", c_char*32),
    ("FirmwareVersion", c_char*32),
    ("PermittedAccess", c_long),
    ("InterfaceId",c_ulong),
    ("InterfaceType",c_int)
    ]

class Frame(Structure):
    """Struct that holds the frame and other relevant information"""

    _fields_ = [
    ("ImageBuffer",POINTER(c_char)),
    ("ImageBufferSize",c_ulong),
    # ("AncillaryBuffer",c_int),
    ("AncillaryBuffer", POINTER(c_char)),
    # ("AncillaryBuffer", c_char*48),
    # ("AncillaryBufferSize",c_int),
    ("AncillaryBufferSize",c_ulong),
    ("Context",c_int*4),
    ("_reserved1",c_ulong*8),

    ("Status",c_int),
    ("ImageSize",c_ulong),
    ("AncillarySize",c_ulong),
    ("Width",c_ulong),
    ("Height",c_ulong),
    ("RegionX",c_ulong),
    ("RegionY",c_ulong),
    ("Format",c_int),
    ("BitDepth",c_ulong),
    ("BayerPattern",c_int),
    ("FrameCount",c_ulong),
    ("TimestampLo",c_ulong),
    ("TimestampHi",c_ulong),
    ("_reserved2",c_ulong*32)    
    ]
    
    def __init__(self, frame_size, ancillary_size):
        self.ImageBuffer = create_string_buffer(frame_size)
        self.ImageBufferSize = c_ulong(frame_size)
        self.AncillaryBuffer = create_string_buffer(ancillary_size)
        self.AncillaryBufferSize = c_ulong(ancillary_size)

e = ResultValues()

class Camera:
	
    dll				= None
    apiData 		= None
    handle			= None
    is64bit         = False

    width, height, channels = 0, 0, 1
    dtype           = 8
    frame 			= None
    pixelFormat		= None

    name            = None
    uid             = None
	
    def __init__(self, driver, apiData):
        self.dll     = driver.dll
        self.apiData = apiData
        self.is64bit = sys.maxsize>2**32
		
        self.name = apiData.CameraName
        self.uid  = apiData.UniqueId
		
        self.handle = self.open()

        self.width  = self.attr_uint32_get('Width')
        self.height = self.attr_uint32_get('Height')

        # Set the PacketSize
        result = self.adjust_packet_size(int(self.attr_range_uint32('PacketSize').split(',')[1]))
        if result != e.ePvErrSuccess:
            self.handle_error(result) 

        # Set the camera to take images in RGB format which is compatible with PIL
        result = self.attr_enum_set('PixelFormat', 'Mono16')
        if result != e.ePvErrSuccess:
            self.handle_error(result)

        # Create a frame to hold the image data
        self.frame = self.create_frame()

        self.requested_frame_rate = 60.0

    def request_frame_rate(self, fr):
        self.requested_frame_rate = fr

    def open(self):
        """Opens a particular camera. Returns the camera's handle"""
        if self.is64bit:
            camera_handle = c_uint64()
        else:
            camera_handle = c_uint()
        result = self.dll.PvCameraOpen(self.uid, 0, byref(camera_handle))
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        return camera_handle

    def close(self):
        """Closes a camera given a handle"""
        if self.capture_query(): self.capture_end()
        result = self.dll.PvCameraClose(self.handle)
        return result

    def capture_start(self):
        """Begins Camera Capture"""
        result = self.dll.PvCaptureStart(self.handle)
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        # Set the frame trigger mode

        result = self.attr_float32_set('FrameRate', self.requested_frame_rate)
        if result != e.ePvErrSuccess:
            self.handle_error(result)

        result = self.attr_enum_set('FrameStartTriggerMode','FixedRate')
        if result != e.ePvErrSuccess:
            self.handle_error(result) 
        # Set the Acquisition Mode. This is Continuous so that auto exposure will work
        result = self.attr_enum_set('AcquisitionMode','Continuous')
        if result != e.ePvErrSuccess:
            self.handle_error(result)  
        # Start acquisition
        result = self.command_run('AcquisitionStart')
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        return

    def capture_end(self):
        """Ends Camera Capture"""
        return self.dll.PvCaptureEnd(self.handle)

    def capture_query(self):
        """Checks if the camera is running"""
        isRunning = c_ulong()
        self.dll.PvCaptureQuery(self.handle, byref(isRunning))
        return isRunning

    def queue_frame(self):
        # Queue the frame
        result = self.dll.PvCaptureQueueFrame(self.handle, byref(self.frame), None)
        if result != e.ePvErrSuccess:
            self.handle_error(result)

    def capture_wait(self,Timeout=1000):        
        # Wait for the frame to complete
        #result = self.dll.PvCaptureWaitForFrameDone(self.handle,byref(self.frame),1000)        
        if Timeout=="inf":
            result = self.dll.PvCaptureWaitForFrameDone(self.handle,byref(self.frame),0xFFFFFFFF)
        else:
            result = self.dll.PvCaptureWaitForFrameDone(self.handle,byref(self.frame),Timeout)    
        
        if result != e.ePvErrSuccess:
            self.handle_error(result)

        im = self.frame.ImageBuffer[0:(self.frame.ImageBufferSize)]
        im_array = np.fromstring(im, dtype='uint16')
        im_array.shape = (self.height, self.width)

        ancillary_buffer_size = self.frame.AncillaryBufferSize
        ancillary_buffer_str = self.frame.AncillaryBuffer[0:ancillary_buffer_size]

        ab = np.fromstring(ancillary_buffer_str, dtype='uint8')
        
        sync_in = ab[17]
        timestamp_lo = self.frame.TimestampLo
        timestamp_hi = self.frame.TimestampHi

        metadata = dict(s1=sync_in&1, s2=(sync_in&2)>>1, ts0=timestamp_lo, ts1=timestamp_hi)

        return im_array, metadata

    def capture(self):
        """ Convenience function that automatically queues a frame, initiates capture
            and returns the image frame as a string"""

        self.queue_frame()

        image = self.capture_wait()
            
        # Return image string
        return image

    def create_frame(self, frameSize = 0):
        """ Creates a frame with a given size """
        if frameSize == 0:
            frameSize = self.attr_uint32_get('TotalBytesPerFrame')

        ancillary_size = self.attr_uint32_get('NonImagePayloadSize')
        self.attr_boolean_set('ChunkModeActive', True)
        return Frame(frameSize, ancillary_size)

    def attr_boolean_set(self,param,value):
        """Set a particular enum attribute given a param and value"""
        result = self.dll.PvAttrBooleanSet(self.handle,param,value)
        return result

    def attr_boolean_get(self,param):
        """Reads a particular enum attribute given a param"""
        val = create_string_buffer(20)
        result = self.dll.PvAttrBooleanGet(self.handle,param, byref(val), len(val), None)
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        return val.value

    def attr_enum_set(self,param,value):
        """Set a particular enum attribute given a param and value"""
        result = self.dll.PvAttrEnumSet(self.handle,param,value)
        return result

    def attr_enum_get(self,param):
        """Reads a particular enum attribute given a param"""
        val = create_string_buffer(20)
        result = self.dll.PvAttrEnumGet(self.handle,param, byref(val), len(val), None)
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        return val.value

    def command_run(self,command):
        """Runs a particular command valid in the Camera and Drive Attributes"""
        return self.dll.PvCommandRun(self.handle,command)

    def attr_uint32_get(self,name):
        """Returns a particular integer attribute"""
        val = c_uint()
        result = self.dll.PvAttrUint32Get(self.handle,name,byref(val))
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        return val.value

    def attr_uint32_set(self, param, value):
        """Sets a particular integer attribute"""
        val = c_uint32(value)
        result = self.dll.PvAttrUint32Set(self.handle,param,val)
        return result


    def attr_float32_get(self,name):
        """Returns a particular integer attribute"""
        val = c_float()
        result = self.dll.PvAttrFloat32Get(self.handle,name,byref(val))
        if result != e.ePvErrSuccess:
            self.handle_error(result)
        return val.value

    def attr_float32_set(self, param, value):
        """Sets a particular integer attribute"""
        val = c_float(value)
        result = self.dll.PvAttrFloat32Set(self.handle,param,val)
        return result


    def attr_range_enum(self, param):
        val = create_string_buffer(100)
        result = self.dll.PvAttrRangeEnum(self.handle,param, byref(val), len(val), None)
        return val.value

    def attr_range_uint32(self,name):
        """Returns a particular integer attribute"""
        val1 = c_uint()
        val2 = c_uint()
        self.dll.PvAttrRangeUint32(self.handle,name,byref(val1),byref(val2))
        return str(val1.value)+','+str(val2.value)
    
    def adjust_packet_size(self, value):
        """ Sets the Packet Size for the camera. Should match your network card's MTU """
        val = c_ulong(value)
        result = self.dll.PvCaptureAdjustPacketSize(self.handle,byref(val))
        return result

    def handle_error(self, result):
        #print e.descriptions[result] + ' ('+ e.errors[result] + ')'
        raise Exception("PvAPI Error: %s (uid: %d, name: %s)" % (e.errors[result], self.uid, self.name))
        #exit()   
		

class PvAPI:
    """Handles the driver"""

    def __init__(self, libpath='/usr/local/lib/'):


        # is64bit = sys.maxsize>2**32
        # if is64bit:
        #     path = path + "x64/"
        # else:
        #     path = path + "x86/"

        if platform.system() == "Linux":  path = libpath + "libPvAPI.so"
        if platform.system() == "Darwin": path = libpath + "libPvAPI.dylib"
        if platform.system() == "Windows": path = libpath + "PvAPI.dll"        
        
        if platform.system() == "Windows":
            self.dll = windll.LoadLibrary(path)            
        else:
            self.dll = cdll.LoadLibrary(path)

        self.initialize()

    def __del__(self):
        self.uninitialize()

    def version(self):
        """Returns a tuple of the driver version"""
        pMajor = c_int()
        pMinor = c_int()
        self.dll.PvVersion(byref(pMajor),byref(pMinor))
        return (pMajor.value,pMinor.value)
        
    def initialize(self):
        """Initializes the driver.  Call this first before anything"""
        result = self.dll.PvInitialize()
        return result
    
    def camera_count(self):
        """Returns the number of attached cameras"""
        return self.dll.PvCameraCount()

    def uninitialize(self):
        """Uninitializes the camera interface"""
        result = self.dll.PvUnInitialize()
        return result

    def camera_list(self):
        """Returns a list of all attached cameras as CameraInfoEx"""
        var = (CameraInfoEx*20)()
        self.dll.PvCameraListEx(byref(var), 20, None, sizeof(CameraInfoEx))
        return var
        


