# Qt imports
import sys
import os
from .utils import display,getPreferences
from .cams import *
from .io import *
import cv2
import ctypes
try:
    from mptracker import MPTracker
except:
    pass
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
                 camDescriptions = [],
                 parameters = {},
                 server = True,
                 saveOnStart = False,
                 triggered = False,
                 updateFrequency = 50):
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
            try:
                avtids,avtnames = AVT_get_ids()
            except:
                display('AVT camera error? Connections? Parameters?')
        self.camQueues = []
        self.writers = []
        connected_avt_cams = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if not 'Save' in cam.keys():
                cam['Save'] = True
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
                if cam['Save']:
                    self.writers.append(TiffWriter(inQ = self.camQueues[-1],
                                                   dataFolder=self.parameters['recorder_path'],
                                                   framesPerFile=self.parameters['recorder_frames_per_file'],
                                                   sleepTime = self.parameters['recorder_sleep_time'],
                                                   filename = expName,
                                                   dataName = cam['description']))
                else:
                    self.writers.append(None)
                self.cams.append(AVTCam(camId=camids[0],
                                        outQ = self.camQueues[-1],
                                        frameRate=cam['frameRate'],
                                        gain=cam['gain'],
                                        triggered = self.triggered,
                                        triggerSource = cam['TriggerSource'],
                                        triggerMode = cam['TriggerMode']))
                connected_avt_cams.append(camids[0])
            elif cam['driver'] == 'QImaging':
                self.camQueues.append(Queue())
                if cam['Save']:
                    self.writers.append(
                        TiffWriter(inQ = self.camQueues[-1],
                                   dataFolder=self.parameters['recorder_path'],
                                   framesPerFile=self.parameters['recorder_frames_per_file'],
                                   sleepTime = self.parameters['recorder_sleep_time'],
                                   filename = expName,
                                   dataName = cam['description']))
                else:
                    self.writers.append(None)
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
            if cam['Save']:
                self.writers[-1].daemon = True
            self.cams[-1].daemon = True
#        self.resize(500,700)

        self.initUI()
        
        if server:
            self.zmqContext = zmq.Context()
            self.zmqSocket = self.zmqContext.socket(zmq.REP)
            self.zmqSocket.bind('tcp://0.0.0.0:{0}'.format(self.parameters['server_port']))
            display('Listening to port: {0}'.format(self.parameters['server_port']))
        self.camerasRunning = False
        for cam,writer in zip(self.cams,self.writers):
            cam.start()
            if not writer is None:
                writer.start()
        camready = 0
        while camready != len(self.cams):
            camready = np.sum([cam.cameraReady.is_set() for cam in self.cams])
        display('Initialized cameras.')
        self.zmqTimer = QTimer()
        self.zmqTimer.timeout.connect(self.zmqActions)
        self.zmqTimer.start(500)
        self.triggerCams(save=self.saveOnStart)
    def setExperimentName(self,expname):
        for writer in self.writers:
            if not writer is None:
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
                if not writer is None:
                    cam.saving.set()
                    writer.write.set()
        else:
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                if not writer is None:
                    cam.saving.clear()
                    writer.write.clear()
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
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w),
                                                              dtype=cam.dtype),
                                             parameters = self.cam_descriptions[c]))
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
            if not writer is None:
                cam.saving.clear()
                writer.write.clear()
                writer.stop()
            cam.stop()
        for c in self.cams:
            c.join()
        for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
            if not writer is None:
                display('   ' + self.cam_descriptions[c]['name']+
                        ' [ Acquired:'+
                        str(cam.nframes.value) + ' - Saved: ' + 
                        str(writer.frameCount.value) + ' - Frames/rate: '
                        +str(cam.nframes.value/
                             self.cam_descriptions[c]['frameRate']) +']')
                writer.join()
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
            self.toggleSaveOnStart(False)
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
    def __init__(self,frame, parameters = None):
        super(CamWidget,self).__init__()
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        toggleSubtract = QAction("Background subtraction",self)
        toggleSubtract.triggered.connect(self.toggleSubtract)
        self.addAction(toggleSubtract)
        tEq = QAction('Equalize histogram',self)
        tEq.triggered.connect(self.toggleEqualize)
        self.addAction(tEq)


        self.scene=QGraphicsScene(0,0,frame.shape[1],
                                  frame.shape[0],self)
        self.view = QGraphicsView(self.scene, self)
        self.lastnFrame = 0
        if not 'SubtractBackground' in parameters.keys():
            parameters['SubtractBackground'] = False
        if not 'Equalize' in parameters.keys():
            parameters['Equalize'] = False
        if not 'TrackEye' in parameters.keys():
            parameters['TrackEye'] = False
        self.parameters = parameters
        self.lastFrame = frame.copy().astype(np.float32)
        if not 'NBackgroundFrames' in parameters.keys():
            self.nAcum = 3.
        else:
            self.nAcum = float(parameters['NBackgroundFrames'])
        self.eyeTracker = None
        self.string = '{0}'
        if not self.parameters['Save']:
            self.string = 'no save -{0}'
        self.image(np.array(frame),-1)
        
        self.show()
        
    def toggleSubtract(self):
        self.parameters['SubtractBackground'] = not self.parameters['SubtractBackground']
    def toggleEqualize(self):
        self.parameters['Equalize'] = not self.parameters['Equalize']

    def image(self,image,nframe):
        if self.lastnFrame != nframe:
            self.scene.clear()
            if self.parameters['TrackEye']:
                if self.eyeTracker is None:
                    self.eyeTracker = MPTracker(drawProcessedFrame=True)
                img = self.eyeTracker.apply(image.copy()) 
                frame = self.eyeTracker.img
            else:
                tmp = image.copy()
                if self.parameters['Equalize']:
                    try: # In case the type is messed up..
                        tmp = cv2.equalizeHist(tmp)
                    except:
                        pass
                if self.parameters['SubtractBackground']:
                    tmp = tmp.astype(np.float32)
                    frame = (np.abs(tmp - self.lastFrame))*10.
                    self.lastFrame = ((1-1/self.nAcum)*(self.lastFrame.astype(np.float32)) +
                                      (1/self.nAcum)*tmp)
                else:
                    frame = tmp
            if self.parameters['driver'] == 'QImaging':
                frame = np.array((frame.astype(np.float32)/2.**14)*2.**8).astype(np.uint8)
            if len(frame.shape) == 2 :
                frame = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_GRAY2BGR)
            cv2.putText(frame,self.string.format(nframe), (10,100), cv2.FONT_HERSHEY_SIMPLEX,
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
    parser.add_argument('-a','--analyse',
                        default=False,
                        action='store_true')
    opts = parser.parse_args()
    if not opts.make_config is None:
        fname = opts.make_config
        getPreferences(fname)
        sys.exit()
    parameters = getPreferences(opts.preffile)
    cams = parameters['cams']
    if not opts.cam_select is None:
        cams = [parameters['cams'][i] for i in opts.cam_select]

    if not opts.analyse:
        app = QApplication(sys.argv)
        w = LabCamsGUI(app = app,
                       camDescriptions = cams,
                       parameters = parameters,
                       server = not opts.no_server,
                       triggered = opts.triggered)
        sys.exit(app.exec_())
    else:
        app = QApplication(sys.argv)
        fname = str(QFileDialog.getExistingDirectory(None,"Select Directory of the run to process",
                                                     parameters['datapaths']['dataserverpaths'][0]))
        from .utils import cameraTimesFromVStimLog,findVStimLog
        from .io import parseCamLog,TiffStack
        from tqdm import tqdm
        import numpy as np
        from glob import glob
        import os
        from os.path import join as pjoin
        from pyvstim import parseVStimLog as parseVStimLog,getStimuliTimesFromLog
        fname = pjoin(*fname.split("/"))
        expname = fname.split(os.path.sep)[-2:]
        camlogext = '.camlog'
        camlogfile = glob(pjoin(fname,'*'+camlogext))
        if not len(camlogfile):
            print('Camera logfile not found in: {0}'.format(fname))
            sys.exit()
        else:
            camlogfile = camlogfile[0]
        camlog = parseCamLog(camlogfile)[0]
        logfile = findVStimLog(expname)
        plog,pcomms = parseVStimLog(logfile)
        camidx = 3
        camlog = cameraTimesFromVStimLog(camlog,plog,camidx = camidx)
        camdata = TiffStack(fname)
        (stimtimes,stimpars,stimoptions) = getStimuliTimesFromLog(logfile,plog)
        camtime = np.array(camlog['duinotime']/1000.)
        stimavgs = triggeredAverage(camdata,camtime,stimtimes)

        for iStim,savg in enumerate(stimavgs):
            fname = pjoin(parameters['datapaths']['dataserverpaths'][0],
                          parameters['datapaths']['analysispaths'],
                          expname[0],expname[1],'stimaverages_cam{0}'.format(camidx),
                          'stim{0}.tif'.format(iStim))
            if not os.path.isdir(os.path.dirname(fname)):
                os.makedirs(os.path.dirname(fname))
            from tifffile import imsave
            imsave(fname,savg)
        
        sys.exit()
if __name__ == '__main__':
    main()
