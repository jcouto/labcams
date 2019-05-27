import numpy as np
import cv2
cv2.setNumThreads(1)
import time
try:
    from mptracker import MPTracker
    from mptracker.widgets import MptrackerParameters
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
    from PyQt5.QtGui import QImage, QPixmap,QBrush,QPen,QColor,QFont
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

from .utils import display

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
        self.setLayout(form)

    def toggleTriggered(self,value):
        display('Toggle trigger mode pressed [{0}]'.format(value))
        if value:
            self.parent.triggered.set()
        else:
            #self.toggleSaveOnStart(False)
            # save button does not get unticked (this is a bug)
            if self.saveOnStartToggle.isChecked():
                self.saveOnStart = False
                self.saveOnStartToggle.setCheckState(Qt.Unchecked)
            self.parent.triggered.clear()
        for cam in self.parent.cams:
            cam.stop_acquisition()
        time.sleep(.5)
        self.parent.triggerCams(save = self.parent.saveOnStart)
        
    def setExpName(self):
        name = self.experimentNameEdit.text()
        if not self.saveOnStartToggle.isChecked():
            self.parent.setExperimentName(str(name))
        else:
            display('[Critical message] Disable manual save to change the filename!')

    def toggleSaveOnStart(self,state):
        self.parent.saveOnStart = state
        display('Warning: The save button is no longer restarting the cameras.')
        #for cam in self.parent.cams:
        #    cam.stop_acquisition()
        #time.sleep(.5)
        for c,(cam,writer) in enumerate(zip(self.parent.cams,
                                            self.parent.writers)):
            if not writer is None:
                if state:
                    cam.saving.set()
                    writer.write.set()
                else:
                    cam.saving.clear()
                    writer.write.clear()
        display('Toggled ManualSave [{0}]'.format(state))
        
class CamWidget(QWidget):
    def __init__(self,frame, iCam = 0, parent = None, parameters = None):
        super(CamWidget,self).__init__()
        self.parent = parent
        self.iCam = iCam
        h,w = frame.shape[:2]
        self.w = w
        self.h = h
        self.addActions()
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        import pyqtgraph as pg
        pg.setConfigOption('background', [200,200,200])
        pg.setConfigOptions(imageAxisOrder='row-major')
        win = pg.GraphicsLayoutWidget()
        p1 = win.addPlot(title="")
        self.view = pg.ImageItem(background=[1,1,1])
        p1.getViewBox().invertY(True)
        p1.getViewBox().invertX(True)
        p1.hideAxis('left')
        p1.hideAxis('bottom')
        p1.addItem(self.view)
#        hist = pg.HistogramLUTItem()
#        p1.addItem(hist)
#        hist.setImageItem(self.view)
        self.text = pg.TextItem('',color = [200,100,100],anchor = [1,0])
        p1.addItem(self.text)
        b=QFont()
        b.setPixelSize(24)
        self.text.setFont(b)
        self.layout.addWidget(win,0,0)
        self.p1 = p1
        self.autoRange = True
#       self.scene=QGraphicsScene(0,0,frame.shape[1],
 #                                 frame.shape[0],self)
 #       self.view = QGraphicsView(self.scene, self)
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
        size = 600
        ratio = h/float(w)
        self.setFixedSize(size,int(size*ratio))
        #self.show()
    def addActions(self):
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        saveImg = QAction("Take camera shot",self)
        saveImg.triggered.connect(self.saveImageFromCamera)
        self.addAction(saveImg)
        toggleSubtract = QAction("Background subtraction",self)
        toggleSubtract.triggered.connect(self.toggleSubtract)
        self.addAction(toggleSubtract)
        tEq = QAction('Equalize histogram',self)
        tEq.triggered.connect(self.toggleEqualize)
        self.addAction(tEq)
        tEt = QAction('Eye tracker',self)
        tEt.triggered.connect(self.toggleEyeTracker)
        self.addAction(tEt)
        tEt = QAction('Auto range',self)
        tEt.triggered.connect(self.toggleAutoRange)
        self.addAction(tEt)
    def toggleSubtract(self):
        self.parameters['SubtractBackground'] = not self.parameters[
            'SubtractBackground']
    def toggleAutoRange(self):
        self.autoRange = not self.autoRange
    def toggleEqualize(self):
        self.parameters['Equalize'] = not self.parameters['Equalize']
    def toggleEyeTracker(self):
        if self.parameters['TrackEye']:
            self.eyeTracker = None
            self.trackerpar.close()
            self.trackerTab.close()
            self.tracker_roi.sigRemoveRequested.emit(self.tracker_roi)
            self.p1.removeItem(self.tracker_roi)
            self.view.mouseReleaseEvent = None

        self.parameters['TrackEye'] = not self.parameters['TrackEye']
    def saveImageFromCamera(self):
        self.parent.timer.stop()
        frame = self.parent.camframes[self.iCam]
        filename = QFileDialog.getSaveFileName(self,
                                               'Select filename to save.')
        if type(filename) is tuple:
            filename = filename[0]
        if filename:
            from tifffile import imsave
            imsave(str(filename),
                   frame,
                   metadata = {
                       'Camera':str(self.iCam)})
            display('Saved camera frame for cam: {0}'.format(self.iCam))
        else:
            display('Aborted.')
        self.parent.timer.start()
        
    def _open_mptracker(self,image):
        self.eyeTracker = MPTracker(drawProcessedFrame=True)
        self.trackerTab = QDockWidget("mptracker cam {0}".format(self.iCam), self)
        self.eyeTracker.parameters['crTrack'] = True
        self.eyeTracker.parameters['sequentialCRMode'] = False
        self.eyeTracker.parameters['sequentialPupilMode'] = False
        self.trackerpar = MptrackerParameters(self.eyeTracker,image)
        if not self.parent.writers[self.iCam] is None:
            self.trackerToggle = QCheckBox()
            self.trackerToggle.setChecked(self.parent.writers[self.iCam].trackerFlag.is_set())
            self.trackerToggle.stateChanged.connect(self.trackerSaveToggle)
            self.trackerpar.pGridSave.addRow(
                QLabel("Save cameras: "),self.trackerToggle)
        self.trackerTab.setWidget(self.trackerpar)
        self.trackerTab.setFloating(True)
        self.trackerpar.resize(400,250)
        self.parent.addDockWidget(Qt.RightDockWidgetArea
                                  ,self.trackerTab)
        self.trackerTab.setAllowedAreas(Qt.LeftDockWidgetArea |
                                        Qt.LeftDockWidgetArea |
                                        Qt.BottomDockWidgetArea |
                                        Qt.TopDockWidgetArea )
        self.trackerTab.setFeatures(QDockWidget.DockWidgetMovable |
                                  QDockWidget.DockWidgetFloatable |
                                  QDockWidget.DockWidgetClosable)
        import pyqtgraph as pg
        self.tracker_roi = pg.RectROI([200, 200], [100, 100], pen=(0,9),removable=True)
        self.p1.addItem(self.tracker_roi)
        self.tracker_roi.sigRegionChanged.connect(self.print_roi)
        self.view.mouseReleaseEvent = self._tracker_selectPoints
    def print_roi(self,evt):
        a,b = self.tracker_roi.pos()
        c,d = self.tracker_roi.size()
        print([a,b,c,d])#getArrayImage(self.lastFrame,self.view))
    def trackerSaveToggle(self,value):
        writer = self.parent.writers[self.iCam]
        if not writer is None:
            if value:
                writer.trackerFlag.set()
                writer.parQ.put((None,self.eyeTracker.parameters))
            else:
                writer.trackerFlag.clear()
    def _tracker_selectPoints(self,event):
        pt = self.view.mapToScene(event.pos())
        if event.button() == 1:
            x = pt.x()
            y = pt.y()
            self.eyeTracker.parameters['points'].append(
                [int(round(x)),int(round(y))])
            self.eyeTracker.setROI(
                self.eyeTracker.parameters['points'])
            self.trackerpar.putPoints()

    def image(self,image,nframe):
        if self.lastnFrame != nframe:
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
            if bool(self.parameters['TrackEye']):
                if self.eyeTracker is None:
                    self._open_mptracker(image.copy())
                img = self.eyeTracker.apply(image.copy())
                if not self.eyeTracker.concatenateBinaryImage:
                    (x1,y1,w,h) = self.eyeTracker.parameters['imagecropidx']
                    frame = cv2.cvtColor(frame,cv2.COLOR_GRAY2RGB)
                    frame[y1:y1+h,x1:x1+w,:] = self.eyeTracker.img
                else:
                    frame = self.eyeTracker.img
            if self.parameters['driver'] in ['QImaging','PCO']:
                frame = np.array((frame.astype(np.float32)/2.**14)*2.**8).astype(np.uint8)
            #if len(frame.shape) == 2 :
            #    frame = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_GRAY2BGR)
            #cv2.putText(frame,self.string.format(nframe), (10,100), cv2.FONT_HERSHEY_SIMPLEX,
            #            1, 105,2)
            self.text.setText(self.string.format(nframe))
            self.view.setImage(frame,autoHistogramRange=self.autoRange)
            #self.qimage = QImage(frame, frame.shape[1], frame.shape[0], 
            #                     frame.strides[0], QImage.Format_RGB888)
            #self.scene.addPixmap(QPixmap.fromImage(self.qimage))
            #self.view.fitInView(QRectF(0,0,
            #                           frame.shape[1],
            #                           frame.shape[0]),
            #                    Qt.KeepAspectRatio)
            self.lastnFrame = nframe
            #self.scene.update()
