from .cams import *
# Allied Vision Technologies cameras
from pymba import *

def AVT_get_ids():
    with Vimba() as vimba:
        # get system object
        system = vimba.getSystem()
        # list available cameras (after enabling discovery for GigE cameras)
        if system.GeVTLIsPresent:
            system.runFeatureCommand("GeVDiscoveryAllOnce")
        #time.sleep(0.01)
        camsIds = vimba.getCameraIds()
        cams = [vimba.getCamera(id) for id in camsIds]
        camsModel = []
        for camid,cam in zip(camsIds,cams):
            try:
                cam.openCamera()
                
            except:
                camsModel.append('')
                continue
            camsModel.append('{0} {1} {2}'.format(cam.DeviceModelName,
                                                  cam.DevicePartNumber,
                                                  cam.DeviceID))
            #print(camsModel)
    return camsIds,camsModel

class AVTCam(GenericCam):
    def __init__(self, camId = None, outQ = None,exposure = 29000,
                 frameRate = 30., gain = 10,frameTimeout = 100,
                 nFrameBuffers = 10,
                 triggered = Event(),
                 triggerSource = 'Line1',
                 triggerMode = 'LevelHigh',
                 triggerSelector = 'FrameStart',
                 acquisitionMode = 'Continuous',
                 nTriggeredFrames = 1000,
                 frame_timeout = 100):
        super(AVTCam,self).__init__()
        if camId is None:
            display('Need to supply a camera ID.')
        self.cam_id = camId
        self.exposure = (1000000/int(frameRate)) - 150
        self.frame_rate = frameRate
        self.gain = gain
        self.frameTimeout = frameTimeout
        self.triggerSource = triggerSource
        self.triggerSelector = triggerSelector
        self.acquisitionMode = acquisitionMode
        self.nTriggeredFrames = nTriggeredFrames 
        self.nbuffers = nFrameBuffers
        self.queue = outQ
        self.frame_timeout = frame_timeout
        self.triggerMode = triggerMode
        self.tickfreq = float(1.0)
        with Vimba() as vimba:
            system = vimba.getSystem()
            if system.GeVTLIsPresent:
                system.runFeatureCommand("GeVDiscoveryAllOnce")
            time.sleep(0.01)
            cam = vimba.getCamera(camId)
            cam.openCamera()
            names = cam.getFeatureNames()
            # get a frame
            cam.acquisitionMode = 'SingleFrame'
            cam.AcquisitionFrameRateAbs = self.frame_rate
            cam.ExposureTimeAbs =  self.exposure
            self.tickfreq = float(cam.GevTimestampTickFrequency)
            cam.GainRaw = self.gain 
            cam.TriggerSource = 'FixedRate'
            cam.TriggerMode = 'Off'
            cam.TriggerSelector = 'FrameStart'
            frame = cam.getFrame()
            frame.announceFrame()
            cam.startCapture()
            frame.queueFrameCapture()
            cam.runFeatureCommand('AcquisitionStart')
            frame.waitFrameCapture()
            cam.runFeatureCommand('AcquisitionStop')
            self.h = frame.height
            self.w = frame.width
            self.dtype = frame.dtype
            self._init_variables(dtype = self.dtype)
            framedata = np.ndarray(buffer = frame.getBufferByteData(),
                                   dtype = self.dtype,
                                   shape = (frame.height,
                                            frame.width)).copy()
            self.img[:] = framedata[:]
            cam.endCapture()
            cam.revokeAllFrames()
            display("AVT [{1}] = Got info from camera (name: {0})".format(
                cam.DeviceModelName,self.cam_id))
        self.triggered = triggered
        if self.triggered.is_set():
            display('AVT [{0}] - Triggered mode ON.'.format(self.cam_id))
            self.triggerSource = triggerSource
    
    def run(self):
        buf = np.frombuffer(self.frame.get_obj(),
                            dtype = self.dtype).reshape([self.h,self.w])
        self.close_event.clear()
        while not self.close_event.is_set():
            self.nframes.value = 0
            recorded_frames = []
            with Vimba() as vimba:
                system = vimba.getSystem()
                if system.GeVTLIsPresent:
                    system.runFeatureCommand("GeVDiscoveryAllOnce")
                time.sleep(0.1)
                # prepare camera
                cam = vimba.getCamera(self.cam_id)
                cam.openCamera()
                # cam.EventSelector = 'FrameTrigger'
                cam.EventNotification = 'On'
                cam.PixelFormat = 'Mono8'
                cameraFeatureNames = cam.getFeatureNames()
                #display('\n'.join(cameraFeatureNames))
                cam.AcquisitionFrameRateAbs = self.frame_rate
                cam.ExposureTimeAbs =  self.exposure
                cam.GainRaw = self.gain
                cam.SyncOutSelector = 'SyncOut1'
                cam.SyncOutSource = 'FrameReadout'#'Exposing'
                if self.triggered.is_set():
                    cam.TriggerSource = self.triggerSource#'Line1'#self.triggerSource
                    cam.TriggerMode = 'On'
                    #cam.TriggerOverlap = 'Off'
                    cam.TriggerActivation = self.triggerMode #'LevelHigh'##'RisingEdge'
                    cam.AcquisitionMode = self.acquisitionMode
                    cam.TriggerSelector = self.triggerSelector
                    if self.acquisitionMode == 'MultiFrame':
                        cam.AcquisitionFrameCount = self.nTriggeredFrames
                        cam.TriggerActivation = self.triggerMode #'LevelHigh'##'RisingEdge'
                else:
                    display('[Cam - {0}] Using no trigger.'.format(self.cam_id))
                    cam.AcquisitionMode = 'Continuous'
                    cam.TriggerSource = 'FixedRate'
                    cam.TriggerMode = 'Off'
                    cam.TriggerSelector = 'FrameStart'
                # create new frames for the camera
                frames = []
                for i in range(self.nbuffers):
                    frames.append(cam.getFrame())    # creates a frame
                    frames[i].announceFrame()
                cam.startCapture()
                for f,ff in enumerate(frames):
                    try:
                        ff.queueFrameCapture()
                    except:
                        display('Queue frame error while getting cam ready: '+ str(f))
                        continue                    
                self.camera_ready.set()
                self.nframes.value = 0
                # Wait for trigger
                display('AVT [{0}] - Camera waiting for software trigger.'.format(self.cam_id))
                while not self.start_trigger.is_set():
                    # limits resolution to 1 ms 
                    time.sleep(0.001)
                    if self.close_event.is_set():
                        break
                display('AVT [{0}] - Received software trigger.'.format(
                    self.cam_id))

                if self.close_event.is_set():
                    cam.endCapture()
                    try:
                        cam.revokeAllFrames()
                    except:
                        display('Failed to revoke frames.')
                    cam.closeCamera()
                    break

                cam.runFeatureCommand("GevTimestampControlReset")
                cam.runFeatureCommand('AcquisitionStart')
                if self.triggered.is_set():
                    cam.TriggerSelector = self.triggerSelector
                    cam.TriggerMode = 'On'
                #tstart = time.time()
                lastframeid = [-1 for i in frames]
                self.camera_ready.clear()
                while not self.stop_trigger.is_set():
                    # run and acquire frames
                    #sortedfids = np.argsort([f._frame.frameID for f in frames])
                    for ibuf in range(self.nbuffers):
                        f = frames[ibuf]
                        avterr = f.waitFrameCapture(timeout = self.frameTimeout)
                        if avterr == 0:
                            timestamp = f._frame.timestamp/self.tickfreq
                            frameID = f._frame.frameID
                            #print('Frame id:{0}'.format(frameID))
                            if not frameID in recorded_frames:
                                recorded_frames.append(frameID)
                                frame = np.ndarray(buffer = f.getBufferByteData(),
                                                   dtype = self.dtype,
                                                   shape = (f.height,
                                                            f.width)).copy()
                                newframe = frame.copy()
                                #display("Time {0} - {1}:".format(str(1./(time.time()-tstart)),self.nframes.value))
                                #tstart = time.time()
                            try:
                                f.queueFrameCapture()
                            except:
                                display('Queue frame failed: '+ str(f))
                                continue
                            self.nframes.value += 1
                            if self.saving.is_set():
                                if not frameID in lastframeid :
                                    self.queue.put((frame.copy(),(frameID,timestamp)))
                                    lastframeid[ibuf] = frameID
                            buf[:] = frame[:]
                        elif avterr == -12:
                            #display('VimbaException: ' +  str(avterr))        
                            break
                cam.runFeatureCommand('AcquisitionStop')
                display('Stopped acquisition.')
                # Check if all frames are done...
                for ibuf in range(self.nbuffers):
                    f = frames[ibuf]
                    try:
                        f.waitFrameCapture(timeout = self.frame_timeout)
                        timestamp = f._frame.timestamp/self.tickfreq
                        frameID = f._frame.frameID
                        frame = np.ndarray(buffer = f.getBufferByteData(),
                                           dtype = self.dtype,
                                           shape = (f.height,
                                                    f.width)).copy()
                        if self.saving.is_set():
                            if not frameID in lastframeid :
                                self.queue.put((frame.copy(),(frameID,timestamp)))
                                lastframeid[ibuf] = frameID
                        self.nframes.value += 1
                        self.frame = frame
                    except VimbaException as err:
                        #display('VimbaException: ' + str(err))
                        pass
                display('{4} delivered:{0},dropped:{1},queued:{4},time:{2}'.format(
                    cam.StatFrameDelivered,
                    cam.StatFrameDropped,
                    cam.StatTimeElapsed,
                    cam.DeviceModelName,
                    self.nframes.value))
                cam.runFeatureCommand('AcquisitionStop')
                cam.endCapture()
                try:
                    cam.revokeAllFrames()
                except:
                    display('Failed to revoke frames.')
                cam.closeCamera()
                self.saving.clear()
                self.start_trigger.clear()
                self.stop_trigger.clear()
                time.sleep(0.01)
                display('AVT [{0}] - Close event: {1}'.format(
                    self.cam_id,
                    self.close_event.is_set()))
