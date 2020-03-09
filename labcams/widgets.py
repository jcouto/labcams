import time

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
                             QDoubleSpinBox,
                             QGraphicsView,
                             QGraphicsScene,
                             QGraphicsItem,
                             QGraphicsLineItem,
                             QGroupBox,
                             QTableWidget,
                             QMainWindow,
                             QDockWidget,
                             QFileDialog,
                             QInputDialog)
from PyQt5.QtGui import QImage, QPixmap,QBrush,QPen,QColor,QFont
from PyQt5.QtCore import Qt,QSize,QRectF,QLineF,QPointF,QTimer

import pyqtgraph as pg
pg.setConfigOption('background', [200,200,200])
pg.setConfigOptions(imageAxisOrder='row-major')
pg.setConfigOption('crashWarning', True)

from .utils import *
from functools import partial
import cv2
cv2.setNumThreads(1)

class QActionCheckBox(QWidgetAction):
    ''' Check box for the right mouse button dropdown menu'''
    def __init__(self,parent,label='',value=True):
        super(QActionCheckBox,self).__init__(parent)
        self.subw = QWidget()
        self.sublay = QFormLayout()
        self.checkbox = QCheckBox()
        self.sublab = QLabel(label)
        self.sublay.addRow(self.checkbox,self.sublab)
        self.subw.setLayout(self.sublay)
        self.setDefaultWidget(self.subw)
        self.checkbox.setChecked(value)
        self.value = self.checkbox.isChecked
    def link(self,func):
        self.checkbox.stateChanged.connect(func)

class QActionSlider(QWidgetAction):
    ''' Slider for the right mouse button dropdown menu'''
    def __init__(self,parent,label='',value=0,vmin = 0,vmax = 1000):
        super(QActionSlider,self).__init__(parent)
        self.subw = QWidget()
        self.sublay = QFormLayout()
        self.slider = QSlider()
        self.sublab = QLabel(label)
        self.sublay.addRow(self.sublab,self.slider)
        self.slider.setOrientation(Qt.Horizontal)
        self.subw.setLayout(self.sublay)
        self.setDefaultWidget(self.subw)
        self.slider.setMaximum(vmax)
        self.slider.setValue(value)
        self.slider.setMinimum(vmin)
        self.value = self.slider.value
    def link(self,func):
        self.slider.valueChanged.connect(func)

class QActionFloat(QWidgetAction):
    ''' Float edit for the right mouse button dropdown menu'''
    def __init__(self,parent,label='',value=0,vmax = None,vmin = None):
        super(QActionFloat,self).__init__(parent)
        self.subw = QWidget()
        self.sublay = QFormLayout()
        self.spin = QDoubleSpinBox()
        self.sublab = QLabel(label)
        self.sublay.addRow(self.sublab,self.spin)
        self.subw.setLayout(self.sublay)
        self.setDefaultWidget(self.subw)
        if not vmax is None:
            self.spin.setMaximum(vmax)
        if not value is None:
            self.spin.setValue(value)
        if not vmin is None:
            self.spin.setMinimum(vmin)
        self.value = self.spin.value
    def link(self,func):
        self.spin.editingFinished.connect(func)


class RecordingControlWidget(QWidget):
    def __init__(self,parent):
        super(RecordingControlWidget,self).__init__()	
        self.parent = parent
        form = QFormLayout()

        info = '''Set the name of the experiment.
        Datapath is relative to the folder specified in the preferences.
        Can be set via UDP (expname=my_experiment/name) or ZMQ (dict(action='expname',value='my_experiment/name'))
'''
        self.experimentNameEdit = QLineEdit(' ')
        self.experimentNameEdit.returnPressed.connect(self.setExpName)
        label = QLabel('Name:')
        label.setToolTip(info)
        self.experimentNameEdit.setToolTip(info)
        form.addRow(label,self.experimentNameEdit)
        self.camTriggerToggle = QCheckBox()
        self.camTriggerToggle.setChecked(self.parent.triggered.is_set())
        self.camTriggerToggle.stateChanged.connect(self.toggleTriggered)
        label = QLabel("Hardware trigger: ")
        label.setToolTip(info)
        info = '''Toggle the hardware trigger mode on cameras that support it.
This will can be differently configured for different cameras.'''
        self.camTriggerToggle.setToolTip(info)
        form.addRow(label,self.camTriggerToggle)
        
        self.saveOnStartToggle = QCheckBox()
        self.saveOnStartToggle.setChecked(self.parent.saveOnStart)
        self.saveOnStartToggle.stateChanged.connect(self.toggleSaveOnStart)
        form.addRow(QLabel("Manual save: "),self.saveOnStartToggle)
        self.softTriggerToggle = QCheckBox()
        self.softTriggerToggle.setChecked(self.parent.software_trigger)
        self.softTriggerToggle.stateChanged.connect(
            self.toggleSoftwareTriggered)
        label = QLabel("Software trigger: ")
        label.setToolTip(info)
        info = '''Toggle the software trigger to start or stop acquisition via software.'''
        self.softTriggerToggle.setToolTip(info)
        form.addRow(label,self.softTriggerToggle)
        self.udpmessages = QLabel('')
        b1=QFont()
        b1.setPixelSize(16)
        b1.setFamily('Regular')
        b1.setBold(True)
        self.udpmessages.setFont(b1)
        self.udpmessages.setStyleSheet("color: rgb(255,165,0)")
        form.addRow(self.udpmessages)
        
        self.setLayout(form)
    def toggleSoftwareTriggered(self,value):
        display('Software trigger pressed [{0}]'.format(value))
        if value:
            for cam in self.parent.cams:
                cam.start_trigger.set()
        else:
            for cam in self.parent.cams:
                cam.start_trigger.clear()
    def toggleTriggered(self,value):
        display('Hardware trigger mode pressed [{0}]'.format(value))
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
                    if not writer is None:
                        writer.write.set()
                else:
                    display('Manual stop saving.')
                    cam.stop_saving()
                    #writer.write.clear()
        display('Toggled ManualSave [{0}]'.format(state))
        
class CamWidget(QWidget):
    def __init__(self,
                 frame,
                 iCam = 0,
                 parent = None,
                 parameters = None,
                 invertX = False):
        super(CamWidget,self).__init__()
        self.parent = parent
        self.iCam = iCam
        self.cam = self.parent.cams[self.iCam]
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
        self.text = pg.TextItem('',color = [220,80,80],anchor = [0,0])
        p1.addItem(self.text)
        b=QFont()
        b.setPixelSize(14)
        b.setFamily('Regular')
        b.setBold(False)
        self.text.setFont(b)
        # remotemsg
        #self.text_remote = pg.TextItem('',color = [220,100,200],anchor = [0,0.1])
        #p1.addItem(self.text_remote)
        #b1=QFont()
        #b1.setPixelSize(14)
        #b1.setFamily('Regular')
        #b1.setBold(False)
        #self.text_remote.setFont(b1)
        
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
        self.parameters['reference_channel'] = None
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
        sep = QAction(self)
        sep.setSeparator(True)
        self.addAction(sep)
        self.functs = []
        # add camera controls
        if hasattr(self.cam,'ctrevents'):
            self.ctract = dict()
            def vchanged(the):
                val = the['action'].value()
                self.cam.eventsQ.put(the['name']+'='+str(int(np.floor(val))))

            for k in  self.cam.ctrevents.keys():
                self.ctract[k] = dict(**self.cam.ctrevents[k])
                ev = self.ctract[k]
                val = eval('self.cam.' + ev['variable'])
                ev['name'] = k
                ev['action'] = None
                if ev['widget'] == 'slider':
                    ev['action'] = QActionSlider(self,k+' [{0:03d}]:'.format(int(val)),
                                                 value = val,
                                                 vmin = ev['min'],
                                                 vmax = ev['max'],)
                elif ev['widget'] == 'float':
                    ev['action'] = QActionFloat(self,k,
                                                value = val,
                                                vmin = ev['min'],
                                                vmax = ev['max'],)
                    
                if not ev['action'] is None:
                        #e.sublab.setText(k + ' [{0:03d}]:'.format(int(val)))
                    self.functs.append(partial(vchanged,self.ctract[k]))
                    ev['action'].link(self.functs[-1]) 
                    self.addAction(ev['action'])
            
        sep = QAction(self)
        sep.setSeparator(True)
        self.addAction(sep)

        # Slider
        toggleSubtract = QActionSlider(self,'Nsubtract [{0:03d}]:'.format(int(self.nAcum)),
                                       value = 0,
                                       vmin = 0,
                                       vmax = 200)
        toggleSubtract.link(lambda x: toggleSubtract.sublab.setText(
            'Nsubtract [{0:03d}]:'.format(int(x))))
        def vchanged(val):
            self.nAcum = float(np.floor(val))
        toggleSubtract.link(vchanged) 
        # ROIs
        self.addAction(toggleSubtract)
        addroi = QAction("Add ROI",self)
        addroi.triggered.connect(self.addROI)
        self.addAction(addroi)
        # Equalize histogram
        toggleEqualize = QActionCheckBox(self,'Equalize histogram',self.parameters['Equalize'])
        def toggleEq():
            self.parameters['Equalize'] = not self.parameters['Equalize']
            toggleEqualize.checkbox.setChecked(self.parameters['Equalize'])
        toggleEqualize.link(toggleEq)
        self.addAction(toggleEqualize)
        # Eye tracker
        self.etrackercheck = QActionCheckBox(self,'Eye tracker',
                                             self.parameters['TrackEye'])
        self.etrackercheck.link(self.toggleEyeTracker)
        self.addAction(self.etrackercheck)
        # autorange
        tar = QActionCheckBox(self,'Auto range',self.autoRange)
        def toggleAutoRange():
            self.autoRange = not self.autoRange
            tar.checkbox.setChecked(self.autoRange)
        tar.link(toggleAutoRange)
        self.addAction(tar)
        # histogram
        tEt = QAction('Histogram',self)
        tEt.triggered.connect(self.histogramWin)
        self.addAction(tEt)
        # Save
        ts = QActionCheckBox(self,'Save camera',  self.parent.saveflags[self.iCam])
        def toggleSaveCam():
            self.parameters['Save'] = not self.parameters['Save']
            self.parent.saveflags[self.iCam] = self.parameters['Save']
            ts.checkbox.setChecked(self.parameters['Save'])
            if not self.parameters['Save']:
                self.string = 'no save - {0}'
            else:
                self.string = '{0}'            
        ts.link(toggleSaveCam)
        self.addAction(ts)
        tr = QActionCheckBox(self,'reference channel',  False)
        def toggleReference():
            if self.parameters['reference_channel'] is None:
                reffile = str(QFileDialog().getOpenFileName(self,'Load reference image')[0])
                if not reffile == '':
                    print('Selected {0}'.format(reffile))
                    from tifffile import imread
                    reference = imread(reffile).squeeze()
                    if len(reference.shape) > 2:
                        reference = reference.mean(axis = 0)
                    self.parameters['reference_channel'] = reference
            else:
                self.parameters['reference_channel'] = None
        tr.link(toggleReference)
        self.addAction(tr)

        
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
        histTab.setAllowedAreas(Qt.LeftDockWidgetArea |
                                Qt.RightDockWidgetArea |
                                Qt.BottomDockWidgetArea |
                                Qt.TopDockWidgetArea)
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
            roiTab.setAllowedAreas(Qt.LeftDockWidgetArea |
                                   Qt.RightDockWidgetArea |
                                   Qt.BottomDockWidgetArea |
                                   Qt.TopDockWidgetArea)
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
            if hasattr(self,'trackerpar'):
                self.trackerpar.close()
                self.trackerTab.close()
                [self.p1.removeItem(c) for c in self.tracker_roi.items()]
        self.parameters['TrackEye'] = not self.parameters['TrackEye']
        self.etrackercheck.checkbox.setChecked(self.parameters['TrackEye'])

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
            if not self.parents.writers[self.iCam] is None:
                self.trackerToggle.setChecked(self.parent.writers[self.iCam].trackerFlag.is_set())
            self.trackerToggle.stateChanged.connect(self.trackerSaveToggle)
            self.trackerpar.pGridSave.addRow(
                QLabel("Save cameras: "),self.trackerToggle)
        self.trackerTab.setWidget(self.trackerpar)
        self.trackerTab.setFloating(True)
        self.trackerpar.resize(400,250)
        self.trackerTab.setAllowedAreas(Qt.LeftDockWidgetArea |
                                        Qt.LeftDockWidgetArea |
                                        Qt.BottomDockWidgetArea |
                                        Qt.TopDockWidgetArea )
        self.trackerTab.setFeatures(QDockWidget.DockWidgetMovable |
                                  QDockWidget.DockWidgetFloatable |
                                  QDockWidget.DockWidgetClosable)
        self.parent.addDockWidget(Qt.LeftDockWidgetArea
                                  ,self.trackerTab)
    def trackerSaveToggle(self,value):
        writer = self.parent.writers[self.iCam]
        if not writer is None:
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
            if self.parameters['reference_channel'] is None:
                self.view.setImage(frame.squeeze(),
                                   autoHistogramRange=self.autoRange)
            else:
                frame = frame.squeeze()
                ref = self.parameters['reference_channel']
                ref /= ref.max()
                im = np.stack([ref,frame/np.max(frame),np.zeros_like(frame)]).transpose([1,2,0])
                self.view.setImage(im)
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

class CamStimTriggerWidget(QWidget):
    def __init__(self,port = None,ino=None, outQ = None):
        super(CamStimTriggerWidget,self).__init__()
        if (ino is None) and (not port is None):
            from .cam_stim_trigger import CamStimInterface
            ino = CamStimInterface(port = port,outQ = outQ)
        self.ino = ino
        form = QFormLayout()
        if not ino is None:
            def disarm():
                ino.disarm()
            disarmButton = QPushButton('Disarm')
            disarmButton.clicked.connect(disarm)
            form.addRow(disarmButton)

            def arm():
                ino.arm()
            armButton = QPushButton('Arm')
            armButton.clicked.connect(arm)
            form.addRow(armButton)

            wcombo = QComboBox()
            # TODO: make this general/ access from the json file.
            wcombo.addItems(['470nm','405nm','both'])
            wcombo.currentIndexChanged.connect(self.setMode)
            form.addRow(wcombo)

            self.wwidth = QLineEdit(str(ino.width.value))
            self.wmargin = QLineEdit(str(ino.margin.value))
            wparametersButton = QPushButton('Set parameters')
            wparametersButton.clicked.connect(self.setParameters)
            form.addRow(QLabel('Width'),self.wwidth)
            form.addRow(QLabel('PMT margin'),self.wmargin)
            form.addRow(wparametersButton)
            
        self.setLayout(form)
        self.setMode(2)
        self.ino.set_parameters(None,None)
        
    def setMode(self,i):
        self.ino.set_mode(i+1)
        
    def setParameters(self):
        try:
            width = int(self.wwidth.text())
            margin = int(self.wmargin.text())
        except:
            print('Could not interpret parameters.')
        finally:
            self.ino.set_parameters(width,margin)

    def close(self):
        self.ino.close()
        self.ino.join()
