# Qt imports
import sys
import os
from .utils import display
from .cams import *
from .io import *
import cv2
import ctypes

from mptracker import MPTracker
try:
    from PyQt5.QtWidgets import (QWidget,
                                 QApplication,
                                 QGridLayout,
                                 QFormLayout,
                                 QVBoxLayout,
                                 QTabWidget,
                                 QCheckBox,
                                 QTextEdit,
                                 QLineEdit,
                                 QComboBox,
                                 QFileDialog,
                                 QSlider,
                                 QPushButton,
                                 QLabel,
                                 QAction,
                                 QMenuBar,
                                 QGraphicsView,
                                 QGraphicsScene,
                                 QGraphicsItem,
                                 QGraphicsLineItem,
                                 QGroupBox,
                                 QTableWidget,
                                 QMainWindow,
                                 QDockWidget,
                                 QFileDialog)
    from PyQt5.QtGui import QImage, QPixmap,QBrush,QPen,QColor
    from PyQt5.QtCore import Qt,QSize,QRectF,QLineF,QPointF,QTimer
    display("Using Qt5 framework.")
except:
    from PyQt4.QtGui import (QWidget,
                             QApplication,
                             QAction,
                             QMainWindow,
                             QDockWidget,
                             QMenuBar,
                             QGridLayout,
                             QFormLayout,
                             QLineEdit,
                             QFileDialog,
                             QVBoxLayout,
                             QCheckBox,
                             QTextEdit,
                             QComboBox,
                             QSlider,
                             QLabel,
                             QPushButton,
                             QGraphicsView,
                             QGraphicsScene,
                             QGraphicsItem,
                             QGraphicsLineItem,
                             QGroupBox,
                             QTableWidget,
                             QFileDialog,
                             QImage,
                             QPixmap)
    from PyQt4.QtCore import Qt,QSize,QRectF,QLineF,QPointF,QTimer

from multiprocessing import Queue,Event
import zmq

class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, expName = 'test',
                 camDescriptions = [],server = True,
                 saveOnStart = False,triggered = False,updateFrequency = 50):
        super(LabCamsGUI,self).__init__()
        display('Starting labcams interface.')
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
            try:
                avtids,avtnames = AVT_get_ids()
            except:
                display('AVT camera error? Connections? Parameters?')
        self.camQueues = []
        self.writers = []
        connected_avt_cams = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if cam['driver'] == 'AVT':
                camids = [camid for (camid,name) in zip(avtids,avtnames) 
                          if cam['name'] in name]
                camids = [camid for camid in camids
                          if not camid in connected_avt_cams]
                if len(camids) == 0:
                    display('Could not find: '+cam['name'])
                if not 'TriggerSource' in cam.keys():
                    cam['TriggerSource'] = 'Line1'
                if not 'TriggerMode' in cam.keys():
                    cam['TriggerMode'] = 'LevelHigh'
                self.camQueues.append(Queue())
                self.writers.append(TiffWriter(inQ = self.camQueues[-1],
                                                  filename = expName,
                                               dataName = cam['description']))
                
                self.cams.append(AVTCam(camId=camids[0],
                                        outQ = self.camQueues[-1],
                                        frameRate=cam['frameRate'],
                                        gain=cam['gain'],
                                        triggered = self.triggered,
                                        triggerSource = cam['TriggerSource'],
                                        triggerMode = cam['TriggerMode']))
                connected_avt_cams.append(camids[0])
            elif cam['driver'] == 'QImaging':
            	display('Connecting to Qimaging camera.')
                self.camQueues.append(Queue())
                self.writers.append(TiffWriter(inQ = self.camQueues[-1],
                                                  filename = expName,
                                                  dataName = cam['description']))
                if not 'binning' in cam.keys():
                    cam['binning'] = 2
                self.cams.append(QImagingCam(camId=cam['id'],
                                             outQ = self.camQueues[-1],
                                             exposure=cam['exposure'],
                                             gain=cam['gain'],
                                             binning = cam['binning'],
                                             triggerType = cam['triggerType'],
                                             triggered = self.triggered))
            else:
            	display('Unknown camera driver' + cam['driver'])
            self.writers[-1].daemon = True
            self.cams[-1].daemon = True
#        self.resize(500,700)

        self.initUI()

        if server:
            self.zmqContext = zmq.Context()
            self.zmqSocket = self.zmqContext.socket(zmq.REP)
            port = 100000
            self.zmqSocket.bind('tcp://0.0.0.0:{0}'.format(port))
            display('Listening to port: {0}'.format(port))
        self.camerasRunning = False
        for cam,writer in zip(self.cams,self.writers):
            cam.start()
            writer.start()
        camready = 0
        while camready != len(self.cams):
            camready = np.sum([cam.cameraReady.is_set() for cam in self.cams])
        display('Initialized cameras.')
        self.zmqTimer = QTimer()
        self.zmqTimer.timeout.connect(self.zmqActions)
        self.zmqTimer.start(1000)
        self.triggerCams(save=self.saveOnStart)
    def setExperimentName(self,expname):
        for writer in self.writers:
            writer.setFilename(expname)
        time.sleep(1)
        self.recController.experimentNameEdit.setText(expname)
        
    def zmqActions(self):
        try:
            message = self.zmqSocket.recv_pyobj(flags=zmq.NOBLOCK)
        except zmq.error.Again:
            return
        self.zmqSocket.send_pyobj(dict(action='handshake'))
        if message['action'] == 'expName':
            self.setExperimentName(message['value'])
        elif message['action'] == 'trigger':
            for cam in self.cams:
                cam.stop_acquisition()
            time.sleep(1)
            self.triggerCams(save = True)

    def triggerCams(self,save=False):
        if save:
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                cam.saving.set()
                writer.write.set()
        for c,cam in enumerate(self.cams):
            cam.startTrigger.set()
        display('Triggered cameras.')
        
    def experimentMenuTrigger(self,q):
        display(q.text()+ "clicked. ")
        
    def initUI(self):
        # Menu
        bar = self.menuBar()
        editmenu = bar.addMenu("Experiment")
        editmenu.addAction("New")
        editmenu.triggered[QAction].connect(self.experimentMenuTrigger)
        self.setWindowTitle("LabCams")
        self.tabs = []
        self.camwidgets = []
        for c,cam in enumerate(self.cams):
            self.tabs.append(QDockWidget("Camera: "+str(c),self))
            layout = QVBoxLayout()
            if 'trackEye' in self.cam_descriptions[c].keys():
                trackeye = True
            else:
                trackeye = None
            if 'subtractBackground' in self.cam_descriptions[c].keys():
                subtractBackground = True
            else:
                subtractBackground = False
            
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w),
                                                              dtype=cam.dtype),
                                             trackeye=trackeye,
                                             subtractBackground = subtractBackground))
            self.tabs[-1].setWidget(self.camwidgets[-1])
            self.tabs[-1].setFloating(False)
            if c < 2:
                self.addDockWidget(
                    Qt.RightDockWidgetArea and Qt.TopDockWidgetArea,
                    self.tabs[-1])
            else:
                self.addDockWidget(
                    Qt.RightDockWidgetArea and Qt.BottomDockWidgetArea,
                    self.tabs[-1])
                
            self.tabs[-1].setFixedSize(cam.w,cam.h)
            display('Init view: ' + str(c))
        self.tabs.append(QDockWidget("Controller",self))
        self.recController = RecordingControlWidget(self)
        self.tabs[-1].setWidget(self.recController)
        self.tabs[-1].setFloating(False)
        self.addDockWidget(
            Qt.RightDockWidgetArea and Qt.TopDockWidgetArea,
            self.tabs[-1])
        self.timer = QTimer()
        self.timer.timeout.connect(self.timerUpdate)
        self.timer.start(self.updateFrequency)
        self.camframes = []
        for c,cam in enumerate(self.cams):
        	if cam.dtype == np.uint8:
        		self.camframes.append(np.frombuffer(
                            cam.frame.get_obj(),
                            dtype = ctypes.c_ubyte).reshape([cam.h,cam.w]))
        	else:
        		self.camframes.append(np.frombuffer(
                            cam.frame.get_obj(),
                            dtype = ctypes.c_ushort).reshape([cam.h,cam.w]))
        self.move(0, 0)
        self.show()
            	
    def timerUpdate(self):
        for c,(cam,frame) in enumerate(zip(self.cams,self.camframes)):
            self.camwidgets[c].image(frame,cam.nframes.value)

    def closeEvent(self,event):
        for cam in self.cams:
            cam.stop_acquisition()
        display('Acquisition duration:')
        for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
            if cam.saving.is_set():
                cam.saving.clear()
            writer.stop()
            cam.stop()
        for c in self.cams:
            c.join()
        for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
            display('   ' + self.cam_descriptions[c]['name']+
                  ' [ Acquired:'+
                  str(cam.nframes.value) + ' - Saved: ' + 
                  str(writer.frameCount.value) + ' - Frames/rate: '
                  +str(cam.nframes.value/
                       self.cam_descriptions[c]['frameRate']) +']')

        event.accept()

class RecordingControlWidget(QWidget):
    def __init__(self,parent):
        super(RecordingControlWidget,self).__init__()	
        self.parent = parent
        form = QFormLayout()

        self.experimentNameEdit = QLineEdit(' ')
        self.changeNameButton = QPushButton('Set name')
        form.addRow(self.experimentNameEdit,self.changeNameButton)
        self.changeNameButton.clicked.connect(self.setExpName)

        self.camTriggerToggle = QCheckBox()
        self.camTriggerToggle.setChecked(self.parent.triggered.is_set())
        self.camTriggerToggle.stateChanged.connect(self.toggleTriggered)
        form.addRow(QLabel("Trigger cams: "),self.camTriggerToggle)
        
        
        self.saveOnStartToggle = QCheckBox()
        self.saveOnStartToggle.setChecked(self.parent.saveOnStart)
        self.saveOnStartToggle.stateChanged.connect(self.toggleSaveOnStart)
        form.addRow(QLabel("Manual save: "),self.saveOnStartToggle)
        self.cameraSelector = QComboBox()
        for i,c in enumerate(self.parent.cams):
            self.cameraSelector.insertItem(i,'Camera {0}'.format(i))
            
        self.saveImageButton = QPushButton('Save image')
        form.addRow(self.cameraSelector,self.saveImageButton)
        self.saveImageButton.clicked.connect(self.saveImageFromCamera)
        
        self.setLayout(form)

    def toggleTriggered(self,value):
        
        if value:
            self.parent.triggered.set()
        else:
            self.parent.triggered.clear()
        for cam in self.parent.cams:
            cam.stop_acquisition()
        time.sleep(1)
        self.parent.triggerCams(save = self.parent.saveOnStart)
        
    def saveImageFromCamera(self):
        self.parent.timer.stop()
        frame = self.parent.camframes[self.cameraSelector.currentIndex()]
        filename = QFileDialog.getSaveFileName(self,
                                               'Select filename to save.',
                                               selectedFilter='*.tif')
        if filename:
            from tifffile import imsave
            imsave(str(filename),
                   frame,
                   metadata = {
                       'Camera':str(self.cameraSelector.currentIndex())})
        else:
            display('Aborted.')
        self.parent.timer.start()
        
    def setExpName(self):
        name = self.experimentNameEdit.text()
        self.parent.setExperimentName(str(name))

    def toggleSaveOnStart(self,state):
        self.parent.saveOnStart = state
        display('Save: {0}'.format(state))
        for cam in self.parent.cams:
            cam.stop_acquisition()
        self.parent.triggerCams(save = state)
        
class CamWidget(QWidget):
    def __init__(self,frame, trackeye=None,subtractBackground = False):
        super(CamWidget,self).__init__()
        self.scene=QGraphicsScene(0,0,frame.shape[1],
                                  frame.shape[0],self)
        self.view = QGraphicsView(self.scene, self)
        self.lastFrame = None
        self.lastnFrame = 0
        if not trackeye is None:
            trackeye = MPTracker(drawProcessedFrame=True)
        self.eyeTracker = trackeye
        self.trackEye = True
        if subtractBackground:
            self.lastFrame = frame.copy()
        self.image(np.array(frame),-1)
        self.show()
    def image(self,image,nframe):
        if self.lastnFrame != nframe:
            self.scene.clear()
            if not self.eyeTracker is None and self.trackEye:
                img = self.eyeTracker.apply(image.copy()) 
                frame = self.eyeTracker.img
            else:
                if not self.lastFrame is None:
                    frame = 2*(image.copy().astype(np.int16) -
                               self.lastFrame.astype(np.int16)) + 128
                    self.lastFrame = (1-1/10.)*(self.lastFrame.astype(np.float32)) + (1/10.)*image.copy().astype(np.float32)
                else:
                    frame = image
            if frame.dtype == np.uint16:
                frame = np.array((frame.astype(np.float32)/2.**14)*2.**8).astype(np.uint8)
            if len(frame.shape) == 2:
                frame = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_GRAY2BGR)
            cv2.putText(frame,str(nframe), (10,100), cv2.FONT_HERSHEY_SIMPLEX,
                        1, 105,2)
            self.qimage = QImage(frame, frame.shape[1], frame.shape[0], 
                                 frame.strides[0], QImage.Format_RGB888)
            self.scene.addPixmap(QPixmap.fromImage(self.qimage))
            #self.view.fitInView(QRectF(0,0,
            #                           10,
            #                           10),
            #                    Qt.KeepAspectRatio)
            self.lastnFrame = nframe
            self.scene.update()

DEFAULTS = [{'description':'facecam',
             'name':'Mako G-030B',
             'driver':'AVT',
             'gain':10,
             'frameRate':150.,
             'TriggerSource':'Line1',
             'TriggerMode':'LevelHigh'},
            {'description':'eyecam',
             'name':'GC660M',
             'driver':'AVT',
             'gain':10,
             'trackEye':True,
             'frameRate':31.,
             'TriggerSource':'Line1',
             'TriggerMode':'LevelHigh'},
            {'description':'1photon',
             'name':'qcam',
             'id':0,
             'driver':'QImaging',
             'gain':1500,#1600,#3600
             'triggerType':1,
             'binning':2,
             'exposure':100000,
             'frameRate':0.1}]
#             'subtractBackground':True
#             'trackEye':True,

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
    parser.add_argument('--make-default-config',
                        default=False,
                        action='store_true')
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
    if opts.make_default_config:
        if opts.preffile is None:
            fname = 'default_labcams.json'
        else:
            fname = opts.preffile
        if os.path.isfile(fname):
            display(fname  + ' exists. Delete it first.')
        else:
            with open(fname,'w') as f:
                json.dump(DEFAULTS,f,
                          sort_keys=True,
                          indent=4,)
        sys.exit()
    if not opts.preffile is None:
        with open(opts.preffile,'r') as f:
            parameters = json.load(f)
    else:
        display('Using default parameters.')
        parameters = DEFAULTS
    if not opts.cam_select is None:
        params = [parameters[i] for i in opts.cam_select]
        parameters = params
    app = QApplication(sys.argv)
    w = LabCamsGUI(app = app,camDescriptions = parameters, 
        server = not opts.no_server,triggered = opts.triggered)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
