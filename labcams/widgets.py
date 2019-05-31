import numpy as np
import cv2
cv2.setNumThreads(1)
import time

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
        self.roiwidget = None
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
        p1.getViewBox().setAspectLocked(True)
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
###        self.setFixedSize(size,int(size*ratio))
        self.resize(size,int(size*ratio))
        self.addActions()

        #self.show()
    def addActions(self):
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        saveImg = QAction("Take camera shot",self)
        saveImg.triggered.connect(self.saveImageFromCamera)
        self.addAction(saveImg)
        toggleSubtract = QAction("Background subtraction",self)
        toggleSubtract.triggered.connect(self.toggleSubtract)
        self.addAction(toggleSubtract)
        addroi = QAction("Add ROI",self)
        addroi.triggered.connect(self.addROI)
        self.addAction(addroi)
        tEq = QAction('Equalize histogram',self)
        tEq.triggered.connect(self.toggleEqualize)
        self.addAction(tEq)
        tEt = QAction('Eye tracker',self)
        tEt.triggered.connect(self.toggleEyeTracker)
        self.addAction(tEt)
        tEt = QAction('Auto range',self)
        tEt.triggered.connect(self.toggleAutoRange)
        self.addAction(tEt)
    def addROI(self):
        roiTab = QDockWidget("roi cam {0}".format(self.iCam), self)
        if self.roiwidget is None:
            self.roiwidget = ROIPlotWidget(roi_target = self.p1, view = self.view)
            roiTab.setWidget(self.roiwidget)
            self.roiwidget.resize(500,700)
            self.parent.addDockWidget(Qt.BottomDockWidgetArea
                                      ,roiTab)
            roiTab.setAllowedAreas(Qt.BottomDockWidgetArea |
                                   Qt.TopDockWidgetArea )
            roiTab.setFeatures(QDockWidget.DockWidgetMovable |
                               QDockWidget.DockWidgetFloatable |
                               QDockWidget.DockWidgetClosable)
            def closetab(ev):
                # This probably does not clean up memory...
                if not self.roiwidget is None:
                    [self.p1.removeItem(r)
                     for r in self.roiwidget.items()]
                    del self.roiwidget
                    self.roiwidget = None
                ev.accept()
            roiTab.closeEvent = closetab
        else:
            self.roiwidget.add_roi()

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
            [self.p1.removeItem(c) for c in self.tracker_roi.items()]

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
        try:
            from mptracker import MPTracker
            from mptracker.widgets import MptrackerParameters,EyeROIWidget
        except:
            display('Could not load tracker.')
            display('\nInstall mptracker: https://bitbucket.org/jpcouto/mptracker')
            return
        self.eyeTracker = MPTracker(drawProcessedFrame=True)
        self.trackerTab = QDockWidget("mptracker cam {0}".format(self.iCam), self)
        self.eyeTracker.parameters['crTrack'] = True
        self.eyeTracker.parameters['sequentialCRMode'] = False
        self.eyeTracker.parameters['sequentialPupilMode'] = False
        self.tracker_roi = EyeROIWidget()
        [self.p1.addItem(c) for c in  self.tracker_roi.items()]
        
        self.trackerpar = MptrackerParameters(self.eyeTracker,image,eyewidget=self.tracker_roi)
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
    def trackerSaveToggle(self,value):
        writer = self.parent.writers[self.iCam]
        if not writer is None:
            if value:
                writer.trackerFlag.set()
                writer.parQ.put((None,self.eyeTracker.parameters))
            else:
                writer.trackerFlag.clear()

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
                frame = (tmp - self.lastFrame)
                self.lastFrame = ((1.-1./self.nAcum)*(self.lastFrame.astype(np.float32)) +
                                  (1./self.nAcum)*tmp)
            else:
                frame = tmp
            if not self.roiwidget is None:
                self.roiwidget.update(frame,iFrame=nframe)
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

            self.text.setText(self.string.format(nframe))
            self.view.setImage(frame,autoHistogramRange=self.autoRange)
            self.lastnFrame = nframe


class ROIPlotWidget(QWidget):
    def __init__(self, roi_target= None,view=None,npoints = 500):
        super(ROIPlotWidget,self).__init__()	
        import pyqtgraph as pg
        layout = QGridLayout()
        self.setLayout(layout)
        self.view = view
        self.roi_target = roi_target
        win = pg.GraphicsLayoutWidget()
        self.p1 = win.addPlot(title="ROI plot",background='black')
        layout.addWidget(win,0,0)
        self.N = npoints
        self.rois = []
        self.plots = []
        self.buffers = []
        self.colors = ['k','r','g','b','y']
        self.add_roi()
    def add_roi(self):
        import pyqtgraph as pg
        self.rois.append(pg.RectROI(pos=[100,100],size=100))
        self.plots.append(pg.PlotCurveItem(pen=self.colors[
            np.mod(len(self.plots),len(self.colors))]))
        self.p1.addItem(self.plots[-1])
        self.roi_target.addItem(self.rois[-1])
        buf = np.zeros([2,self.N],dtype=np.float32)
        buf[0,:] = np.arange(self.N)
        buf[1,:] = np.nan
        self.buffers.append(buf)
        print('added roi')
    def items(self):
        return self.rois
    def closeEvent(self,ev):
        print(self.rois)
        for roi in self.rois:
            self.roi_target.removeItem(roi)
        ev.accept()
    def update(self,img,iFrame):
        for i,(roi,plot) in enumerate(zip(self.rois,self.plots)):
            r = roi.getArrayRegion(img, self.view)
            buf = np.roll(self.buffers[i], -1, axis = 1)
            buf[1,-1] = np.mean(r)
            buf[0,-1] = iFrame
            self.buffers[i] = buf
            plot.setData(x = buf[0,:],
                         y = buf[1,:])
