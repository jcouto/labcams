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
                                 QWidgetAction,
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

import pyqtgraph as pg
pg.setConfigOption('background', [200,200,200])
pg.setConfigOptions(imageAxisOrder='row-major')
pg.setConfigOption('crashWarning', True)

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
        for c,(cam,flg,writer) in enumerate(zip(self.parent.cams,
                                                self.parent.saveflags,
                                                self.parent.writers)):
            if flg:
                if state:
                    cam.saving.set()
                    writer.write.set()
                else:
                    cam.saving.clear()
                    writer.write.clear()
        display('Toggled ManualSave [{0}]'.format(state))
        
class CamWidget(QWidget):
    def __init__(self,frame, iCam = 0, parent = None,
                 parameters = None,
                 invertX = False):
        super(CamWidget,self).__init__()
        self.parent = parent
        self.iCam = iCam
        self.cam = self.parent.cams[self.iCam]
        print(self.cam.ctrevents)
        h,w = frame.shape[:2]
        self.w = w
        self.h = h
        self.roiwidget = None
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        win = pg.GraphicsLayoutWidget()
        p1 = win.addPlot(title="")
        self.view = pg.ImageItem(background=[1,1,1])
        p1.getViewBox().invertY(True)
        if invertX:
            p1.getViewBox().invertX(True)
        p1.getViewBox().setAspectLocked(True)
        p1.hideAxis('left')
        p1.hideAxis('bottom')
        p1.addItem(self.view)
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
        if not 'NBackgroundFrames' in parameters.keys() or not parameters['SubtractBackground']:
            self.nAcum = 0
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
        # Slider
        toggleSubtract = QWidgetAction(self)
        subw = QWidget()
        sublay = QFormLayout()
        subwid = QSlider()
        subwid.setOrientation(Qt.Horizontal)
        sublab = QLabel('Nsubtract [{0:03d}]:'.format(int(self.nAcum)))
        sublay.addRow(sublab,subwid)
        subw.setLayout(sublay)
        toggleSubtract.setDefaultWidget(subw)
        subwid.setMaximum(1000)
        subwid.setValue(self.nAcum)
        subwid.setMinimum(0)
        subwid.valueChanged.connect(lambda x: sublab.setText(
            'Nsubtract [{0:03d}]:'.format(int(x))))
        def vchanged(val):
            self.nAcum = float(np.floor(val))
        subwid.valueChanged.connect(vchanged) 
        # ROIs
        self.addAction(toggleSubtract)
        addroi = QAction("Add ROI",self)
        addroi.triggered.connect(self.addROI)
        self.addAction(addroi)
        # Equalize histogram
        toggleEqualize = QWidgetAction(self)
        eqw = QWidget()
        eqlay = QFormLayout()
        eqc = QCheckBox()
        eqlay.addRow(eqc,QLabel('Equalize histogram'))
        eqw.setLayout(eqlay)
        toggleEqualize.setDefaultWidget(eqw)
        def toggleEq():
            self.parameters['Equalize'] = not self.parameters['Equalize']
            eqc.setChecked(self.parameters['Equalize'])
        eqc.stateChanged.connect(toggleEq)
        self.addAction(toggleEqualize)
        # Eye tracker
        tEt = QAction('Eye tracker',self)
        tEt.triggered.connect(self.toggleEyeTracker)
        self.addAction(tEt)
        def toggleAutoRange():
            self.autoRange = not self.autoRange
        tEt = QAction('Auto range',self)
        tEt.triggered.connect(toggleAutoRange)
        self.addAction(tEt)
        tEt = QAction('Histogram',self)
        tEt.triggered.connect(self.histogramWin)
        self.addAction(tEt)

        toggleSave = QWidgetAction(self)
        savew = QWidget()
        savelay = QFormLayout()
        savec = QCheckBox()
        savelay.addRow(savec,QLabel('Save camera'))
        savew.setLayout(savelay)
        toggleSave.setDefaultWidget(savew)
        savec.setChecked(self.parameters['Save'])
        def toggleSaveCam():
            self.parameters['Save'] = not self.parameters['Save']
            self.parent.saveflags[self.iCam] = self.parameters['Save']
            savec.setChecked(self.parameters['Save'])
            if not self.parameters['Save']:
                self.string = 'no save -{0}'
            else:
                self.string = '{0}'            
        savec.stateChanged.connect(toggleSaveCam)
        self.addAction(toggleSave)

        
    def histogramWin(self):
        histTab = QDockWidget("histogram cam {0}".format(self.iCam), self)
        widget = QWidget()
        layout = QGridLayout()
        widget.setLayout(layout)
        win = pg.GraphicsLayoutWidget()
        p1 = win.addPlot()
        p1.getViewBox().invertY(True)
        p1.hideAxis('left')
        p1.hideAxis('bottom')

        hist = pg.HistogramLUTItem()
        hist.axis.setPen('k')
        p1.addItem(hist)
        hist.setImageItem(self.view)
        layout.addWidget(win,0,0)
        histTab.setWidget(widget)
        histTab.setAllowedAreas(Qt.BottomDockWidgetArea |
                                Qt.TopDockWidgetArea )
        histTab.setFeatures(QDockWidget.DockWidgetMovable |
                           QDockWidget.DockWidgetFloatable |
                           QDockWidget.DockWidgetClosable)
        self.parent.addDockWidget(Qt.BottomDockWidgetArea
                                  ,histTab)
        histTab.setFloating(True)
        histTab.resize(200,200)
        

    def addROI(self):
        roiTab = QDockWidget("roi cam {0}".format(self.iCam), self)
        if self.roiwidget is None:
            self.roiwidget = ROIPlotWidget(roi_target = self.p1, view = self.view)
            roiTab.setWidget(self.roiwidget)
            roiTab.setAllowedAreas(Qt.BottomDockWidgetArea |
                                   Qt.TopDockWidgetArea )
            roiTab.setFeatures(QDockWidget.DockWidgetMovable |
                               QDockWidget.DockWidgetFloatable |
                               QDockWidget.DockWidgetClosable)
            self.parent.addDockWidget(Qt.BottomDockWidgetArea
                                      ,roiTab)
            roiTab.setFloating(True)
            roiTab.resize(400,150)
            
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

#    def toggleSubtract(self):
#        self.parameters['SubtractBackground'] = not self.parameters[
#            'SubtractBackground']
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
        if self.parent.saveflags[self.iCam]:
            self.trackerToggle = QCheckBox()
            self.trackerToggle.setChecked(self.parent.writers[self.iCam].trackerFlag.is_set())
            self.trackerToggle.stateChanged.connect(self.trackerSaveToggle)
            self.trackerpar.pGridSave.addRow(
                QLabel("Save cameras: "),self.trackerToggle)
        self.trackerTab.setWidget(self.trackerpar)
        self.trackerTab.setFloating(True)
        self.trackerpar.resize(400,250)
        self.parent.addDockWidget(Qt.LeftDockWidgetArea
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
        if self.parent.saveflags[self.iCam]:
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
                    tmp = cv2.equalizeHist(tmp).reshape(image.shape)
                except:
                    pass
            if self.nAcum > 0:
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
                    self._open_mptracker(image.squeeze())
                img = self.eyeTracker.apply(image.squeeze())
                if not self.eyeTracker.concatenateBinaryImage:
                    (x1,y1,w,h) = self.eyeTracker.parameters['imagecropidx']
                    frame = cv2.cvtColor(frame,cv2.COLOR_GRAY2RGB)
                    frame[y1:y1+h,x1:x1+w] = self.eyeTracker.img
                else:
                    frame = self.eyeTracker.img

            self.text.setText(self.string.format(nframe))
            self.view.setImage(frame.squeeze(),
                               autoHistogramRange=self.autoRange)
            self.lastnFrame = nframe


class ROIPlotWidget(QWidget):
    colors = ['#d62728',
          '#1f77b4',
          '#ff7f0e',
          '#2ca02c',
          '#9467bd',
          '#8c564b',
          '#e377c2',
          '#7f7f7f',
          '#bcbd22']
    penwidth = 1.5
    def __init__(self, roi_target= None,view=None,npoints = 500):
        super(ROIPlotWidget,self).__init__()	
        layout = QGridLayout()
        self.setLayout(layout)
        self.view = view
        self.roi_target = roi_target
        win = pg.GraphicsLayoutWidget()
        self.p1 = win.addPlot()
        self.p1.getAxis('bottom').setPen('k') 
        self.p1.getAxis('left').setPen('k') 
        layout.addWidget(win,0,0)
        self.N = npoints
        self.rois = []
        self.plots = []
        self.buffers = []
        self.add_roi()
    def add_roi(self):
        pencolor = self.colors[
            np.mod(len(self.plots),len(self.colors))]
        self.rois.append(pg.RectROI(pos=[100,100],
                                    size=100,
                                    pen=pencolor))
        self.plots.append(pg.PlotCurveItem(pen=pg.mkPen(
            color=pencolor,width=self.penwidth)))
        self.p1.addItem(self.plots[-1])
        self.roi_target.addItem(self.rois[-1])
        buf = np.zeros([2,self.N],dtype=np.float32)
        buf[0,:] = np.nan
        buf[1,:] = np.nan
        self.buffers.append(buf)
    def items(self):
        return self.rois
    def closeEvent(self,ev):
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
