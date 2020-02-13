from .utils import *
from .cams import *
from .io import *
from .widgets import *

N_UDP = 1024

class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, expName = 'test',
                 camDescriptions = [],
                 parameters = {},
                 server = True,
                 saveOnStart = False,
                 triggered = False,
                 updateFrequency = 33):
        '''
        Graphical interface for controling labcams.
        General parameters:
            - 
        '''
        super(LabCamsGUI,self).__init__()
        display('Starting labcams interface.')
        self.parameters = parameters
        self.app = app
        self.updateFrequency=updateFrequency
        self.saveOnStart = saveOnStart
        self.cam_descriptions = camDescriptions
        self.triggered = Event()
        if triggered:
            self.triggered.set()
        else:
            self.triggered.clear()
        # Init cameras
        camdrivers = [cam['driver'] for cam in camDescriptions]
        if 'AVT' in camdrivers:
            from .avt import AVT_get_ids
            try:
                avtids,avtnames = AVT_get_ids()
            except Exception as e:
                display('[ERROR] AVT  camera error? Connections? Parameters?')
                print(e)
        self.camQueues = []
        self.saveflags = []
        self.writers = []
        connected_avt_cams = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if not 'Save' in cam.keys():
                cam['Save'] = True
            self.saveflags.append(cam['Save'])
            if 'NoQueue' in cam.keys():
                if cam['NoQueue']:
                    self.camQueues.append(None)
                else:
                    self.camQueues.append(Queue())
            else:
                self.camQueues.append(Queue())

            if not 'recorder' in cam.keys():
                cam['recorder'] = dict(type='ffmpeg',
                                       crf = 17)
            
            recorderpar = dict(cam['recorder'],
                               datafolder=self.parameters['recorder_path'],
                               framesperfile=self.parameters['recorder_frames_per_file'],
                               compression = self.parameters['compress'],
                               filename = expName,
                               dataname = cam['description'])

            if cam['driver'] == 'AVT':
                from .avt import AVTCam
                camids = [(camid,name) for (camid,name) in zip(avtids,avtnames) 
                          if cam['name'] in name]
                camids = [camid for camid in camids
                          if not camid[0] in connected_avt_cams]
                if len(camids) == 0:
                    display('Could not find or already connected to: '+cam['name'])
                    display('Available AVT cameras:')
                    print('\n                -> '+
                          '\n                -> '.join(avtnames))
                    
                    sys.exit()
                cam['name'] = camids[0][1]
                if not 'TriggerSource' in cam.keys():
                    cam['TriggerSource'] = 'Line1'
                if not 'TriggerMode' in cam.keys():
                    cam['TriggerMode'] = 'LevelHigh'
                if not 'TriggerSelector' in cam.keys():
                    cam['TriggerSelector'] = 'FrameStart'
                if not 'AcquisitionMode' in cam.keys():
                    cam['AcquisitionMode'] = 'Continuous'
                if not 'AcquisitionFrameCount' in cam.keys():
                    cam['AcquisitionFrameCount'] = 1000
                if not 'nFrameBuffers' in cam.keys():
                    cam['nFrameBuffers'] = 6
                self.cams.append(AVTCam(camId=camids[0][0],
                                        outQ = self.camQueues[-1],
                                        frameRate=cam['frameRate'],
                                        gain=cam['gain'],
                                        triggered = self.triggered,
                                        triggerSource = cam['TriggerSource'],
                                        triggerMode = cam['TriggerMode'],
                                        triggerSelector = cam['TriggerSelector'],
                                        acquisitionMode = cam['AcquisitionMode'],
                                        nTriggeredFrames = cam['AcquisitionFrameCount'],
                                        nFrameBuffers = cam['nFrameBuffers'],
                                        recorderpar = recorderpar))
                connected_avt_cams.append(camids[0][0])
            elif cam['driver'] == 'QImaging':
                from .qimaging import QImagingCam
                if not 'binning' in cam.keys():
                    cam['binning'] = 2
                self.cams.append(QImagingCam(camId=cam['id'],
                                             outQ = self.camQueues[-1],
                                             exposure=cam['exposure'],
                                             gain=cam['gain'],
                                             binning = cam['binning'],
                                             triggerType = cam['triggerType'],
                                             triggered = self.triggered,
                                             recorderpar = recorderpar))
            elif cam['driver'] == 'OpenCV':
                self.cams.append(OpenCVCam(camId=cam['id'],
                                           outQ = self.camQueues[-1],
                                           triggered = self.triggered,
                                           **cam,
                                           recorderpar = recorderpar))
            elif cam['driver'] == 'PCO':
                from .pco import PCOCam
                self.cams.append(PCOCam(camId=cam['id'],
                                        binning = cam['binning'],
                                        exposure = cam['exposure'],
                                        outQ = self.camQueues[-1],
                                        triggered = self.triggered,
                                        recorderpar = recorderpar))
            elif cam['driver'] == 'ximea':
                from .ximeacam import XimeaCam
                self.cams.append(XimeaCam(camId=cam['id'],
                                          binning = cam['binning'],
                                          exposure = cam['exposure'],
                                          outQ = self.camQueues[-1],
                                          triggered = self.triggered,
                                          recorderpar = recorderpar))
            elif cam['driver'] == 'PointGrey':
                from .pointgreycam import PointGreyCam
                if not 'roi' in cam.keys():
                    cam['roi'] = []
                if not 'pxformat' in cam.keys():
                    cam['pxformat'] = 'Mono8' #'BayerRG8'
                if not 'serial' in cam.keys():
                    # camera serial number
                    cam['serial'] = None 
                if not 'binning' in cam.keys():
                    cam['binning'] = None
                if not 'exposure' in cam.keys():
                    cam['exposure'] = None
                self.cams.append(PointGreyCam(camId=cam['id'],
                                              serial = cam['serial'],
                                              gain = cam['gain'],
                                              roi = cam['roi'],
                                              frameRate = cam['frameRate'],
                                              pxformat = cam['pxformat'],
                                              exposure = cam['exposure'],
                                              binning = cam['binning'],
                                              outQ = self.camQueues[-1],
                                              triggered = self.triggered,
                                              recorderpar = recorderpar))
            else: 
                display('[WARNING] -----> Unknown camera driver' +
                        cam['driver'])
                self.camQueues.pop()
                self.saveflags.pop()
            if not self.camQueues[-1] is None:
                if not 'compress' in self.parameters:
                    self.parameters['compress'] = 0
                if not 'saveMethod' in cam.keys():
                    cam['saveMethod'] = 'tiff'
                if  cam['saveMethod'] == 'tiff':
                    self.writers.append(TiffWriter(
                        inQ = self.camQueues[-1],
                        datafolder=self.parameters['recorder_path'],
                        framesperfile=self.parameters['recorder_frames_per_file'],
                        sleeptime = self.parameters['recorder_sleep_time'],
                        compression = self.parameters['compress'],
                        filename = expName,
                        dataname = cam['description']))
                elif cam['saveMethod'] == 'ffmpeg':
                    self.writers.append(FFMPEGWriter(
                        inQ = self.camQueues[-1],
                        datafolder=self.parameters['recorder_path'],
                        sleeptime = self.parameters['recorder_sleep_time'],
                        compression = 17,
                        frame_rate = cam['frameRate'],
                        filename = expName,
                        dataname = cam['description']))
                else:
                    self.writers.append(OpenCVWriter(
                        inQ = self.camQueues[-1],
                        datafolder=self.parameters['recorder_path'],
                        sleeptime = self.parameters['recorder_sleep_time'],
                        compression = 17,
                        frame_rate = cam['frameRate'],
                        filename = expName,
                        dataname = cam['description']))
            else:
                self.writers.append(None)
            # Print parameters
            display('\t Camera: {0}'.format(cam['name']))
            for k in np.sort(list(cam.keys())):
                if not k == 'name' and not k == 'recorder':
                    display('\t\t - {0} {1}'.format(k,cam[k]))
        #self.resize(100,100)

        self.initUI()
        
        if server:
            if not 'server_refresh_time' in self.parameters.keys():
                self.parameters['server_refresh_time'] = 30
            if not 'server' in self.parameters.keys():
                self.parameters['server'] = 'zmq'
            if self.parameters['server'] == 'udp':
                import socket
                self.udpsocket = socket.socket(socket.AF_INET, 
                                     socket.SOCK_DGRAM) # UDP
                self.udpsocket.bind(('0.0.0.0',
                                     self.parameters['server_port']))
                display('Listening to UDP port: {0}'.format(
                    self.parameters['server_port']))
                self.udpsocket.settimeout(.02)
            else:
                import zmq
                self.zmqContext = zmq.Context()
                self.zmqSocket = self.zmqContext.socket(zmq.REP)
                self.zmqSocket.bind('tcp://0.0.0.0:{0}'.format(
                    self.parameters['server_port']))
                display('Listening to ZMQ port: {0}'.format(
                    self.parameters['server_port']))
            self.serverTimer = QTimer()
            self.serverTimer.timeout.connect(self.serverActions)
            self.serverTimer.start(self.parameters['server_refresh_time'])

        self.camerasRunning = False
        for cam,writer in zip(self.cams,self.writers):
            cam.start()
            if not writer is None:
                writer.start()
        camready = 0
        while camready != len(self.cams):
            camready = np.sum([cam.camera_ready.is_set() for cam in self.cams])
        display('Initialized cameras.')
        self.triggerCams(save=self.saveOnStart)

    def setExperimentName(self,expname):
        # Makes sure that the experiment name has the right slashes.
        if os.path.sep == '/':
            expname = expname.replace('\\',os.path.sep).strip(' ')
        for flg,writer,cam in zip(self.saveflags,self.writers,self.cams):
            if flg:
                if not writer is None:
                    writer.setFilename(expname)
                else:
                    display('Setting serial recorder filename.')
                    cam.eventsQ.put('filename='+expname)
        time.sleep(0.15)
        self.recController.experimentNameEdit.setText(expname)
        
    def serverActions(self):
        if self.parameters['server'] == 'zmq':
            try:
                message = self.zmqSocket.recv_pyobj(flags=zmq.NOBLOCK)
            except:
                return
            self.zmqSocket.send_pyobj(dict(action='handshake'))
        elif self.parameters['server'] == 'udp':
            try:
                msg,address = self.udpsocket.recvfrom(N_UDP)
            except:
                return
            msg = msg.decode().split('=')
            message = dict(action=msg[0])
            if len(msg) > 1:
                message = dict(message,value=msg[1])
        display('Server received message: {0}'.format(message))
        if message['action'].lower() == 'expname':
            self.setExperimentName(message['value'])
        elif message['action'].lower() == 'trigger':
            for cam in self.cams:
                cam.stop_acquisition()
            # make sure all cams closed
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                cam.stop_saving()
                #if not writer is None: # Logic moved to inside camera.
                #    writer.write.clear()
            self.triggerCams(save = True)
        elif message['action'].lower() == 'settrigger':
            self.recController.camTriggerToggle.setChecked(
                int(message['value']))
        elif message['action'].lower() == 'setmanualsave':
            self.recController.saveOnStartToggle.setChecked(
                int(message['value']))
        elif message['action'].lower() == 'log':
            for cam in self.cam:
                cam.eventsQ.put('log={0}'.format(message['value']))
        elif message['action'].lower() == 'ping':
            display('Server got PING.')
            
    def triggerCams(self,soft_trigger = True, save=False):
        # stops previous saves if there were any
        display("Waiting for the cameras to be ready.")
        for c,cam in enumerate(self.cams):
            while not cam.camera_ready.is_set():
                time.sleep(0.001)
            display('Camera {{0}} ready.'.format(c))
        display('Doing save ({0}) and trigger'.format(save))
        if save:
            for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                                    self.saveflags,
                                                    self.writers)):
                if flg:
                    cam.saving.set()
                    if not writer is None:
                        writer.write.set()
        else:
            for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                                    self.saveflags,
                                                    self.writers)):
                if flg:
                    if not writer is None:
                        cam.stop_saving()
                    #writer.write.clear() # cam stops writer
        #time.sleep(2)
        if soft_trigger:
            for c,cam in enumerate(self.cams):
                cam.start_trigger.set()
            display('Software triggered cameras.')
        
    def experimentMenuTrigger(self,q):
        if q.text() == 'Set refresh time':
            self.timer.stop()
            res = QInputDialog().getDouble(self,"What refresh period do you want?","GUI refresh period",
                                           self.updateFrequency)
            if res[1]:
                self.updateFrequency = res[0]
            self.timer.start(self.updateFrequency)
            #display(q.text()+ "clicked. ")
        
    def initUI(self):
        # Menu
        self.setDockOptions(QMainWindow.AllowTabbedDocks |
                            QMainWindow.AllowNestedDocks
)
        from .widgets import CamWidget,RecordingControlWidget
        bar = self.menuBar()
        editmenu = bar.addMenu("Options")
        editmenu.addAction("Set refresh time")
        editmenu.triggered[QAction].connect(self.experimentMenuTrigger)
        self.setWindowTitle("labcams")
        self.tabs = []
        self.camwidgets = []
        self.recController = RecordingControlWidget(self)
        self.setCentralWidget(self.recController)
        
        for c,cam in enumerate(self.cams):
            tt = ''
            if self.saveflags[c]:
                tt +=  ' - ' + self.cam_descriptions[c]['description'] +' ' 
            self.tabs.append(QDockWidget("Camera: "+str(c) + tt,self))
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w,cam.nchan),
                                                              dtype=cam.dtype),
                                             iCam = c,
                                             parent = self,
                                             parameters = self.cam_descriptions[c]))
            self.tabs[-1].setWidget(self.camwidgets[-1])
            self.tabs[-1].setFloating(False)
            self.tabs[-1].setAllowedAreas(Qt.LeftDockWidgetArea |
                                          Qt.LeftDockWidgetArea |
                                          Qt.BottomDockWidgetArea |
                                          Qt.TopDockWidgetArea)
            self.tabs[-1].setFeatures(QDockWidget.DockWidgetMovable |
                                      QDockWidget.DockWidgetFloatable)
            self.addDockWidget(
                Qt.LeftDockWidgetArea,
                self.tabs[-1])
            self.tabs[-1].setMinimumHeight(200)
            display('Init view: ' + str(c))

        self.timer = QTimer()
        self.timer.timeout.connect(self.timerUpdate)
        self.timer.start(self.updateFrequency)
        self.camframes = []
        for c,cam in enumerate(self.cams):
            self.camframes.append(cam.img)
        self.move(0, 0)
        self.show()
            	
    def timerUpdate(self):
        for c,(cam,frame) in enumerate(zip(self.cams,self.camframes)):
            try:
                self.camwidgets[c].image(frame,cam.nframes.value)
            except Exception as e:
                display('Could not draw cam: {0}'.format(c))
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(
                    exc_tb.tb_frame.f_code.co_filename)[1]
                print(e, fname, exc_tb.tb_lineno)
    def closeEvent(self,event):
        if hasattr(self,'serverTimer'):
            self.serverTimer.stop()
        self.timer.stop()
        for cam in self.cams:
            cam.stop_acquisition()
        display('Acquisition stopped (close event).')
        for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                            self.saveflags,
                                            self.writers)):
            if flg:
                cam.stop_saving()
                #writer.write.clear() # logic moved inside writer
                if not writer is None:
                    writer.stop()
            cam.close()
        for c in self.cams:
            c.join()
        for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                                self.saveflags,
                                                self.writers)):
            if flg:
                if not writer is None:
                    display('   ' + self.cam_descriptions[c]['name']+
                            ' [ Acquired:'+
                            str(cam.nframes.value) + ' - Saved: ' + 
                            str(writer.frameCount.value) +']')
                    writer.join()
        from .widgets import pg
        pg.setConfigOption('crashWarning', False)
        event.accept()


def main():
    from argparse import ArgumentParser
    import os
    import json
    
    parser = ArgumentParser(description='Script to control and record from cameras.')
    parser.add_argument('preffile',
                        metavar='configfile',
                        type=str,
                        default=None,
                        nargs="?")
    parser.add_argument('-d','--make-config',
                        type=str,
                        default = None,
                        action='store')
    parser.add_argument('--triggered',
                        default=False,
                        action='store_true')
    parser.add_argument('-c','--cam-select',
                        type=int,
                        nargs='+',
                        action='store')
    parser.add_argument('--no-server',
                        default=False,
                        action='store_true')

    opts = parser.parse_args()
    if not opts.make_config is None:
        fname = opts.make_config
        getPreferences(fname, create=True)
        sys.exit()
    parameters = getPreferences(opts.preffile)
    cams = parameters['cams']
    if not opts.cam_select is None:
        cams = [parameters['cams'][i] for i in opts.cam_select]

    app = QApplication(sys.argv)
    w = LabCamsGUI(app = app,
                   camDescriptions = cams,
                   parameters = parameters,
                   server = not opts.no_server,
                   triggered = opts.triggered)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
