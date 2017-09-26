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
                                 QSlider,
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
    print("Using Qt5 framework.")
except:
    from PyQt4.QtGui import (QWidget,
                             QApplication,
                             QAction,
                             QMainWindow,
                             QDockWidget,
                             QMenuBar,
                             QGridLayout,
                             QFormLayout,
                             QVBoxLayout,
                             QCheckBox,
                             QTextEdit,
                             QSlider,
                             QLabel,
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

from multiprocessing import Queue

class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, expName = 'test',
                 camDescriptions = [{'description':'facecam',
                                     'name':'Mako G-030B',
                                     'driver':'AVT',
                                     'gain':10,
                                     'frameRate':30.},
                                     {'description':'eyecam',
                                     'name':'GC660M',
                                     'driver':'AVT',
                                     'gain':10,
                                     'trackEye':True,
                                     'frameRate':30.},
									{'description':'1photon',
                                     'name':'qcam',
                                     'id':0,
                                     'driver':'QImaging',
                                     'gain':3600,
                                     'exposure':100000,
                                     'frameRate':0.1}],
                                     
                 saveOnStart = False):
        super(LabCamsGUI,self).__init__()
        display('Starting labcams interface.')
        self.app = app
        self.defaultSaveOption = saveOnStart
        self.cam_descriptions = camDescriptions
        # Init cameras
        avtids,avtnames = AVT_get_ids()
        self.camQueues = []
        self.writers = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if cam['driver'] == 'AVT':
                camids = [camid for (camid,name) in zip(avtids,avtnames) 
                          if cam['name'] in name]
                if len(camids) == 0:
                    display('Could not find: '+cam['name'])
                self.camQueues.append(Queue())
                self.writers.append(TiffWriter(inQ = self.camQueues[-1],
                                                  expName = expName,
                                                  dataName = cam['description']))
                self.cams.append(AVTCam(camId=camids[0],
                                        outQ = self.camQueues[-1],
                                        frameRate=cam['frameRate'],
                                        gain=cam['gain']))
            elif cam['driver'] == 'QImaging':
            	display('Connecting to Qimaging camera.')
                self.camQueues.append(Queue())
                self.writers.append(TiffWriter(inQ = self.camQueues[-1],
                                                  expName = expName,
                                                  dataName = cam['description']))
                self.cams.append(QImagingCam(camId=cam['id'],
                                        outQ = self.camQueues[-1],
                                        exposure=cam['exposure'],
                                        gain=cam['gain']))
            else:
            	display('Unknown camera driver' + cam['driver'])
            self.writers[-1].daemon = True
            self.cams[-1].daemon = True
        self.resize(500,700)

        self.initUI()
        for cam,writer in zip(self.cams,self.writers):
            cam.start()
            writer.start()
        camready = 0
        while camready<len(self.cams):
            camready = np.sum([cam.cameraReady.is_set() for cam in self.cams])
        display('All cameras ready!')
        self.triggerCams(save=self.defaultSaveOption)
        
        
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
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w),
                                                              dtype=cam.dtype),
                                             trackeye=trackeye))
            self.tabs[-1].setWidget(self.camwidgets[-1])
            self.tabs[-1].setFloating(False)
            self.addDockWidget(Qt.RightDockWidgetArea and Qt.TopDockWidgetArea,self.tabs[-1])
            self.tabs[-1].setFixedSize(cam.w,cam.h)
            display('Init view: ' + str(c))
        self.show()
        self.timer = QTimer()
        self.timer.timeout.connect(self.timerUpdate)
        self.timer.start(50)
        self.camframes = []
        for c,cam in enumerate(self.cams):
        	if cam.dtype == np.uint8:
        		self.camframes.append(np.frombuffer(cam.frame.get_obj(),dtype = ctypes.c_ubyte).reshape([cam.h,cam.w]))
        	else:
        		self.camframes.append(np.frombuffer(cam.frame.get_obj(),dtype = ctypes.c_ushort).reshape([cam.h,cam.w]))
            	
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
        for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
            display('   ' + self.cam_descriptions[c]['name']+
                  ' [ Acquired:'+
                  str(cam.nframes.value) + ' - Saved: ' + 
                  str(writer.frameCount.value) + ' - Frames/rate: '
                  +str(cam.nframes.value/
                       self.cam_descriptions[c]['frameRate']) +']')

        event.accept()

class CamWidget(QWidget):
    def __init__(self,frame,trackeye=None):
        super(CamWidget,self).__init__()
        self.scene=QGraphicsScene(0,0,frame.shape[1],
                                  frame.shape[0],self)
        self.view = QGraphicsView(self.scene, self)
        self.lastFrame = None
        if not trackeye is None:
            trackeye = MPTracker()
        self.eyeTracker = trackeye
        self.trackEye = True
        self.image(np.array(frame),-1)
        self.show()
    def image(self,image,nframe):
        self.scene.clear()
        if not self.eyeTracker is None and self.trackEye:
            img = self.eyeTracker.apply(image.copy()) 
            frame = img[0]
        else:
            if not self.lastFrame is None:
                frame = 2*(image.copy().astype(np.int16) -
                           self.lastFrame.astype(np.int16)) + 128
            else:
                frame = image
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
        
        self.scene.update()
        #self.lastFrame = image.copy()

def main():
    app = QApplication(sys.argv)
    w = LabCamsGUI(app = app)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
