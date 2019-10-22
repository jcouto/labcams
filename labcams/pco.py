from .cams import *

class PCOCam(GenericCam):
    time_modes = {0:"ns", 1: "us", 2: "ms"}
    def __init__(self, camId = None, outQ = None,
                 binning = 2,
                 exposure = 100,
                 dtype = np.uint16,
                 useCameraParameters = True,
                 triggerSource = np.uint16(2),
                 triggered = Event(),
                 dllpath = 'C:\\Program Files (x86)\\pco\\pco.sdk\\bin64\\SC2_Cam.dll',
                 **kwargs):
        super(PCOCam,self).__init__()
        self.armed = False
        self.drivername = 'PCO'
        self._dll = ctypes.WinDLL(dllpath)
        self.dllpath = dllpath
        self.poll_timeout=1
                
        self.trigerMode = 0
        self.exposure = exposure
        self.binning = binning
        if camId is None:
            display('Need to supply a camera ID.')
        self.camId = camId
        self.queue = outQ
        self.dtype = dtype
        ret = self.camopen(self.camId)
        assert ret == 0, "PCO: Could not open camera {0}".format(camId)
        self.useCameraParameters = useCameraParameters
        if self.useCameraParameters:
            ret = self.set_binning(binning,binning)
            display('PCO - Binning: {0}'.format(ret))
        ret = self.set_exposure_time(self.exposure)
        display('PCO - Exposure: {0} {1}'.format(*ret))
        self.set_trigger_mode(0)
        display('PCO - Trigger mode: {0}'.format(self.get_trigger_mode()))
        frame = self.get_one()
        self.camclose()
        self.hCam = None
        self._prepared = []
        self.h = frame.shape[0]
        self.w = frame.shape[1]
        display('PCO - size: {0} x {1}'.format(self.h,self.w))
        self.nchannels = 1 #frame.shape[2]
        self._init_variables(dtype)
        self.triggered = triggered
        self.triggerSource = triggerSource

        self._dll = None
        self.img[:] = np.reshape(frame,self.img.shape)[:]

        display("Got info from camera (name: {0})".format(
             'PCO'))

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

    def camopen(self,camid,reset = True):
        '''Open PCO camera'''
        opencamera = self._dll.PCO_OpenCamera
        # PCO_OpenCamera(HANDLE *hCam, int board_num), return int
        opencamera.argtypes = (ctypes.POINTER(ctypes.c_int), ctypes.c_int)
        opencamera.restype = ctypes.c_int
        self.hCam = ctypes.c_int()
        ret = opencamera(self.hCam, camid)
        #if ret == 0 and reset:
        #    self._dll.PCO_ResetSettingsToDefault(self.hCam)
        return ret
    
    def camclose(self):
        ''' Close PCO camera'''
        return self._dll.PCO_CloseCamera(self.hCam)
    
    def acquisitionstart(self):
        """
        Start recording
        :return: message from recording status
        """
        return self._dll.PCO_SetRecordingState(self.hCam, ctypes.c_int16(1))
    
    def acquisitionstop(self):
        """
        Start recording
        :return: message from recording status
        """
        return self._dll.PCO_SetRecordingState(self.hCam, ctypes.c_int16(0))
    
    def get_health_state(self):
        cameraWarning, cameraError, cameraStatus = (ctypes.c_uint16(), ctypes.c_uint16(),ctypes.c_uint16())
        iRet = self._dll.PCO_GetCameraHealthStatus(self.hCam,
                                                   ctypes.byref(cameraWarning),
                                                   ctypes.byref(cameraError),
                                                   ctypes.byref(cameraStatus))
        if cameraError.value !=0:
            display("PCO - Camera has ErrorStatus");
            return -1
        return 0
    def _prepare_to_mem(self):
        """
        Prepares memory for recording
        :return:
        """
        dw1stImage, dwLastImage = ctypes.c_uint32(0), ctypes.c_uint32(0)
        wBitsPerPixel = ctypes.c_uint16(16)
        dwStatusDll, dwStatusDrv = ctypes.c_uint32(), ctypes.c_uint32()
        bytes_per_pixel = ctypes.c_uint32(2)
        pixels_per_image = ctypes.c_uint32(self.wXResAct.value * self.wYResAct.value)
        added_buffers = []
        for which_buf in range(len(self.buffer_numbers)):
            self._dll.PCO_AddBufferEx(
                self.hCam, dw1stImage, dwLastImage,
                self.buffer_numbers[which_buf], self.wXResAct,
                self.wYResAct, wBitsPerPixel)
            added_buffers.append(which_buf)

        # prepare Python data types for receiving data
        # http://stackoverflow.com/questions/7543675/how-to-convert-pointer-to-c-array-to-python-array
        ArrayType = ctypes.c_uint16*pixels_per_image.value
        self._prepared = (dw1stImage, dwLastImage,
                          wBitsPerPixel,
                          dwStatusDll, dwStatusDrv,
                          bytes_per_pixel, pixels_per_image,
                          added_buffers, ArrayType)
        return None
    
    def allocate_buffers(self, num_buffers=2):
        """
        Allocate buffers for image grabbing
        :param num_buffers:
        :return:
        """
        dwSize = ctypes.c_uint32(self.wXResAct.value*self.wYResAct.value*2)  # 2 bytes per pixel
        # set buffer variable to []
        self.buffer_numbers, self.buffer_pointers, self.buffer_events = ([], [], [])
        # now set buffer variables to correct value and pass them to the API
        for i in range(num_buffers):
            self.buffer_numbers.append(ctypes.c_int16(-1))
            self.buffer_pointers.append(ctypes.c_void_p(0))
            self.buffer_events.append(ctypes.c_void_p(0))
            self._dll.PCO_AllocateBuffer(self.hCam, ctypes.byref(self.buffer_numbers[i]),
                                         dwSize, ctypes.byref(self.buffer_pointers[i]),
                                         ctypes.byref(self.buffer_events[i]))

        # Tell camera link what actual resolution to expect
        self._dll.PCO_CamLinkSetImageParameters(self.hCam, self.wXResAct, self.wYResAct)
    
    #def get_one(self, poll_timeout=5e7):
    #    iRet = PCO_GetImageEx(cam, 1, 0, 0, BufNum, XResAct, YResAct, 16)
    
    def get_trigger_mode(self):
        wTrigMod = ctypes.c_uint16()
        self._dll.PCO_GetTriggerMode(self.hCam, ctypes.byref(wTrigMod))
        return wTrigMod.value
    
    def set_trigger_mode(self,tmode = 0):
        '''
        0x0000 = [auto sequence]
        0x0001 = [software trigger]
        0x0002 = [external exposure start & software trigger]
        0x0003 = [external exposure control]
        0x0004 = [external synchronized]
        0x0005 = [fast external exposure control]
        0x0006 = [external CDS control]
        0x0007 = [slow external exposure control]
        0x0102 = [external synchronized HDSDI]
        '''
        wTrigMod = ctypes.c_uint16(tmode)
        return self._dll.PCO_SetTriggerMode(self.hCam, wTrigMod)

    def set_binning(self, h_bin, v_bin):
        """
        binning allows for Binning pixels in h_bin x v_bin
        Allowed values in {1,2,4,8,16,32}
        :param h_bin: binning in horizontal direction
        :param v_bin:
        :return: None
        """
        allowed = [1, 2, 4]
        wBinHorz = ctypes.c_uint16(int(h_bin))
        wBinVert = ctypes.c_uint16(int(v_bin))
        if (h_bin in allowed) and (v_bin in allowed):
            self._dll.PCO_SetBinning(self.hCam, wBinHorz, wBinVert)
            self._dll.PCO_GetBinning(self.hCam, ctypes.byref(wBinHorz),
                                          ctypes.byref(wBinVert))
            return [wBinHorz.value, wBinVert.value]
        else:
            raise ValueError("Not allowed binning value pair " + str(h_bin)
                              + "x" + str(v_bin))
            return None
    
    def set_exposure_time(self, exp_time=100, base_exposure=2):
        """
        Sets delay and exposure time allowing to choose a base for each parameter
        0x0000 timebase=[ns]=[10^-9 seconds]
        0x0001 timebase=[us]=[10^-6 seconds]
        0x0002 timebase=[ms]=[10^-3 seconds]
        Note: Does not require armed camera to set exp time
        :param exp_time: Exposure time (integer < 1000)
        :param base_exposure: Base 10 order for exposure time in seconds-> ns/us/ms
        :param verbose: True if process should be printed
        :return: None
        """
        # check for allowed values
        self.exposure = exp_time
        if not(base_exposure in [1, 2]):
            raise UserWarning("PCO - Not accepted time base mode (has to be 1 or 2).")

        # pass values to ctypes variables
        dwDelay = ctypes.c_uint32(0)
        dwExposure = ctypes.c_uint32(int(exp_time))
        wTimeBaseDelay = ctypes.c_uint16(0)
        wTimeBaseExposure = ctypes.c_uint16(int(base_exposure))

        # set exposure time and delay time
        self._dll.PCO_SetDelayExposureTime(self.hCam,
                                           dwDelay, dwExposure,
                                           wTimeBaseDelay, wTimeBaseExposure)
        self._dll.PCO_GetDelayExposureTime(self.hCam, ctypes.byref(dwDelay),
                                           ctypes.byref(dwExposure),
                                           ctypes.byref(wTimeBaseDelay),
                                           ctypes.byref(wTimeBaseExposure))

        return [dwExposure.value, self.time_modes[wTimeBaseExposure.value]]

    def get_exposure_time(self):
        """
        Get exposure time of the camera.
        :return: exposure time, units
        """
        # pass values to ctypes variables
        dwDelay = ctypes.c_uint32(0)
        dwExposure = ctypes.c_uint32(0)
        wTimeBaseDelay = ctypes.c_uint16(0)
        wTimeBaseExposure = ctypes.c_uint16(0)

        # get exposure time
        self._dll.PCO_GetDelayExposureTime(self.hCam, ctypes.byref(dwDelay),
                                           ctypes.byref(dwExposure),
                                           ctypes.byref(wTimeBaseDelay),
                                           ctypes.byref(wTimeBaseExposure))

        return [dwExposure.value, self.time_modes[wTimeBaseExposure.value]]

    def arm(self):
        """
        Arms camera and allocates buffers for image recording
        :return:
        """
        if self.armed:
            
            raise UserWarning("PCO - Camera already armed?")

        # Arm camera
        self._dll.PCO_ArmCamera(self.hCam)
        # Get the actual image resolution-needed for buffers
        self.wXResAct, self.wYResAct, wXResMax, wYResMax = (
            ctypes.c_uint16(), ctypes.c_uint16(), ctypes.c_uint16(),
            ctypes.c_uint16())
        self._dll.PCO_GetSizes(self.hCam, ctypes.byref(self.wXResAct),
                               ctypes.byref(self.wYResAct), ctypes.byref(wXResMax),
                               ctypes.byref(wYResMax))
        self.h,self.w = [self.wXResAct.value,
                         self.wYResAct.value]
        self.armed = True
        self.allocate_buffers()
        return self.armed
    
    def disarm(self):
        """
        Disarm camera, free allocated buffers and set
        recording to 0
        :return:
        """
        # set recording state to 0
        wRecState = ctypes.c_uint16(0)
        self._dll.PCO_SetRecordingState(self.hCam, wRecState)
        # free all allocated buffers
        self._dll.PCO_RemoveBuffer(self.hCam)
        for buf in self.buffer_numbers:
            self._dll.PCO_FreeBuffer(self.hCam, buf)
        self.buffer_numbers, self.buffer_pointers, self.buffer_events = (
            [], [], [])
        self.armed = False

        
    def get_one(self, poll_timeout=5e7):
        """
        Records a single image
        :return:
        """
        self.arm()
        self.acquisitionstart()
        self._prepare_to_mem()

        message = 0
        (dw1stImage, dwLastImage, wBitsPerPixel, dwStatusDll,
         dwStatusDrv, bytes_per_pixel,
         pixels_per_image, added_buffers, ArrayType) = self._prepared

        assert bytes_per_pixel.value == 2
        out = np.zeros((self.wYResAct.value, self.wXResAct.value),
                       dtype=np.uint16)
        
        num_acquired = 0
        num_images = 1
        for which_im in range(num_images):
            num_polls = 0
            polling = True
            while polling:
                num_polls += 1
                message = self._dll.PCO_GetBufferStatus(
                    self.hCam, self.buffer_numbers[added_buffers[0]],
                    ctypes.byref(dwStatusDll), ctypes.byref(dwStatusDrv))
                if dwStatusDll.value == 0xc0008000:
                    which_buf = added_buffers.pop(0)  # Buffer exits the queue
                    #print("After", num_polls, "polls, buffer")
                    #print(self.buffer_numbers[which_buf].value)
                    #print("is ready.")
                    polling = False
                    break
                else:
                    time.sleep(0.00005)  # Wait 50 microseconds
                if num_polls > poll_timeout:
                    #print("After %i polls, no buffer."%(poll_timeout))
                    return None
            try:
                if dwStatusDrv.value == 0x00000000:
                    pass
                elif dwStatusDrv.value == 0x80332028:
                    print('DMA error during record_to_memory')
                    break
                    raise MemoryError('DMA error during record_to_memory')
                else:
                    print("dwStatusDrv:", dwStatusDrv.value)
                    print("Buffer status error")
                    break
                    #raise UserWarning("Buffer status error")

                #print("Record to memory result:")
                #print(hex(dwStatusDll.value), hex(dwStatusDrv.value))
                #print(message)


                buffer_ptr = ctypes.cast(self.buffer_pointers[which_buf], ctypes.POINTER(ArrayType))
                out[:, :] = np.frombuffer(buffer_ptr.contents, dtype=np.uint16).reshape(out.shape)
                num_acquired += 1
            finally:
                self._dll.PCO_AddBufferEx(  # Put the buffer back in the queue
                    self.hCam, dw1stImage, dwLastImage,
                    self.buffer_numbers[which_buf], self.wXResAct, self.wYResAct,
                    wBitsPerPixel)
                added_buffers.append(which_buf)
        
        self.acquisitionstop()
        self.disarm()
        return out

    def _cam_init(self):
        self._dll = ctypes.WinDLL(self.dllpath)
        self.nframes.value = 0
        self.lastframeid = -1
        ret = self.camopen(self.camId)
        if self.useCameraParameters:
            ret = self.set_binning(self.binning,self.binning)
            display('PCO - Binning: {0}'.format(ret))
            ret = self.set_exposure_time(self.exposure)
            display('PCO - Exposure: {0} {1}'.format(*ret))
        if self.triggered.is_set():
            display('PCO - Trigger mode settting to: {0}'.format(self.triggerSource))
            display('\t\t\tPCO - {0}'.format(self.set_trigger_mode(self.triggerSource)))
        else:
            self.set_trigger_mode(0)
        display('PCO - Trigger mode: {0}'.format(self.get_trigger_mode()))
        display('PCO - size: {0} x {1}'.format(self.h,self.w))
        self.arm()
        self.camera_ready.set()
        self.nframes.value = 0
        self.stop_trigger.clear()

    def _cam_startacquisition(self):
        self.acquisitionstart()
        display('PCO [{0}] - Started acquisition.'.format(self.camId))
        self.camera_ready.clear()
        self._prepare_to_mem()
        (self.dw1stImage, self.dwLastImage, self.wBitsPerPixel, self.dwStatusDll,
         self.dwStatusDrv, bytes_per_pixel,
         pixels_per_image, self.added_buffers, self.ArrayType) = self._prepared
        assert bytes_per_pixel.value == 2
        self.out = np.zeros((self.wYResAct.value, self.wXResAct.value),
                            dtype=np.uint16)
        
    def _cam_loop(self):

        timestamp = 0
        message = 0
        num_acquired = 0
        num_polls = 0
        polling = True
        while polling:
            which_buf = None
            num_polls += 1
            message = self._dll.PCO_GetBufferStatus(
                self.hCam, self.buffer_numbers[self.added_buffers[0]],
                ctypes.byref(self.dwStatusDll), ctypes.byref(self.dwStatusDrv))
            if self.dwStatusDll.value == 0xc0008000:
                which_buf = self.added_buffers.pop(0)  # Buffer exits the queue
                #print("After", num_polls, "polls, buffer")
                #print(self.buffer_numbers[which_buf].value)
                #print("is ready.")
                frameID = self.nframes.value
                polling = False
                break
            else:
                time.sleep(0.00005)  # Wait 50 microseconds
                if num_polls > self.poll_timeout:
                    break
        if not which_buf is None:
            try:
                if self.dwStatusDrv.value == 0x00000000:
                    pass
                elif self.dwStatusDrv.value == 0x80332028:
                    print('DMA error during record_to_memory')
                    raise MemoryError('DMA error during record_to_memory')
                else:
                    print("dwStatusDrv:", self.dwStatusDrv.value)
                    print("Buffer status error")
                    raise UserWarning("Buffer status error")
                #print("Record to memory result:")
                #print(hex(dwStatusDll.value), hex(dwStatusDrv.value))
                buffer_ptr = ctypes.cast(self.buffer_pointers[which_buf], ctypes.POINTER(self.ArrayType))
                self.out[:, :] = np.frombuffer(buffer_ptr.contents, dtype=np.uint16).reshape(self.out.shape)
                num_acquired += 1
                frame = self.out.copy()
                self.nframes.value += 1
                if self.saving.is_set():
                    if not frameID == self.lastframeid :
                        self.queue.put((frame.copy(),
                                        (frameID,timestamp)))
                self.lastframeid = frameID
                self.buf[:,:] = np.reshape(frame[:,:],self.buf.shape)[:]

            finally:
                self._dll.PCO_AddBufferEx(  # Put the buffer back in the queue
                    self.hCam, self.dw1stImage, self.dwLastImage,
                    self.buffer_numbers[which_buf], self.wXResAct, self.wYResAct,
                    self.wBitsPerPixel)
                self.added_buffers.append(which_buf)
                
    def _cam_close(self):
        display('PCO [{0}] - Stopping acquisition.'.format(self.camId))
        self.acquisitionstop()
        self.disarm()
        ret = self.camclose()
        display('PCO - returned {0} on close'.format(ret))
        self.saving.clear()
        self.start_trigger.clear()
        self.stop_trigger.clear()
        display('PCO {0} - Close event: {1}'.format(self.camId,
                                                    self.close_event.is_set()))
