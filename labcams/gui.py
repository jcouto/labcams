# Qt imports
import sys
import os
from .utils import display
from .cams import *
import cv2
import ctypes
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


class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, camDescriptions = []):
        super(LabCamsGUI,self).__init__()
        display('Starting labcams interface.')
        self.app = app
        self.cam_descriptions = camDescriptions
        # Init cameras
        avtids,avtname = AVT_get_ids()
        
#        self.cam_descriptions = range(3)
#        for c,cam in enumerate(self.cam_descriptions):
        for c,(cam,frate) in enumerate(zip(avtids,[250,30])):
            display("Connecting to " + str(c) + ' camera')
#            self.cams.append(DummyCam())
            self.cams.append(AVTCam(camId=cam,frameRate=frate,
                                    exposure = 3000,gain=10))
            self.cams[-1].daemon = True
        self.resize(500,700)

        self.initUI()
        for cam in self.cams:
            cam.start()
        camready = 0
        while camready<len(self.cams):
            camready = np.sum([cam.cameraReady.is_set() for cam in self.cams])
        display('All cameras ready!')
        self.triggerCams()
        
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
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w),
                                                              dtype=np.uint8)))
            self.tabs[-1].setWidget(self.camwidgets[-1])
            self.tabs[-1].setFloating(False)
            self.addDockWidget(Qt.RightDockWidgetArea and Qt.TopDockWidgetArea,self.tabs[-1])
            self.tabs[-1].setFixedSize(cam.w,cam.h)
            display('Init view: ' + str(c))
        self.show()
        self.timer = QTimer()
        self.timer.timeout.connect(self.timerUpdate)
        self.timer.start(30)
        self.camframes = []
        for c,cam in enumerate(self.cams):
            self.camframes.append(np.frombuffer(cam.frame.get_obj(),
                                                dtype = ctypes.c_ubyte).reshape(
                                                    [cam.h,cam.w]))
    def timerUpdate(self):
        for c,(cam,frame) in enumerate(zip(self.cams,self.camframes)):
            self.camwidgets[c].image(frame,cam.nframes.value)
    def closeEvent(self,event):
        for cam in self.cams:
            cam.stop_acquisition()
        print('Acquisition duration.')
        for cam,srate in zip(self.cams,[250.,30.]):
            print(cam.nframes.value/srate)

        event.accept()

class CamWidget(QWidget):
    def __init__(self,frame):
        super(CamWidget,self).__init__()
        print(frame.shape)
        self.scene=QGraphicsScene(0,0,frame.shape[1],
                                  frame.shape[0],self)
        self.view = QGraphicsView(self.scene, self)
        self.image(np.array(frame),-1)
        self.show()
    def image(self,image,nframe):
        self.scene.clear()
        frame = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_GRAY2BGR)
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

def main():
    app = QApplication(sys.argv)
    w = LabCamsGUI(app = app)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
