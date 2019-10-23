from ximea import xiapi
from .cams import *

class XimeaCam(GenericCam):
    def __init__(self,
                 camId = None,
                 outQ = None,
                 binning = 2,
                 exposure = 100,
                 triggerSource = np.uint16(2),
                 triggered = Event(),
                 **kwargs):
        super(XimeaCam,self).__init__()
        self.drivername = 'ximea'
        if camId is None:
                display('[Ximea] - Need to supply a camera ID.')
        self.camId = camId
        self.queue = outQ

        frame = self.get_one()

        self.h = frame.shape[0]
        self.w = frame.shape[1]
        self.nchannels = 1
        self.dtype = np.uint16
        self._init_variables(self.dtype)
        self.triggered = triggered
        self.triggerSource = triggerSource

        self.img[:] = np.reshape(frame,self.img.shape)[:]

        display("[Ximea {0}] - got info from camera.".format(self.camId))
        
    def get_one(self):
        self._cam_init()
        self.cam.start_acquisition()
        self.cam.get_image(self.cambuf)
        frame = self.cambuf.get_image_data_numpy()
        self.cam.stop_acquisition()
        self.cam.close_device()
        self.cam = None
        self.cambuf = None
        return frame
    def _cam_init(self):
        self.cam = xiapi.Camera()
        #start communication
        self.cam.open_device()
        self.cam.set_exposure(20000)
        self.cambuf = xiapi.Image()
        self.camera_ready.set()
        self.nframes.value = 0

    def _cam_startacquisition(self):
        self.cam.start_acquisition()

    def _cam_loop(self):
        self.cam.get_image(self.cambuf)
        frame = self.cambuf.get_image_data_numpy()
        frameID = self.nframes.value
        self.nframes.value += 1
        timestamp = self.cambuf.tsUSec
        if self.saving.is_set():
            if not frameID == self.lastframeid :
                self.queue.put((frame.copy(),
                                (frameID,timestamp)))
        self.lastframeid = frameID
        self.buf[:] = np.reshape(frame.copy(),self.buf.shape)[:]

    def _cam_close(self):
        self.cam.stop_acquisition()
        self.cam.close_device()
        self.cam = None        
