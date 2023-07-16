#  labcams - https://jpcouto@bitbucket.org/jpcouto/labcams.git
# Copyright (C) 2020 Joao Couto - jpcouto@gmail.com
#
#  This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtWidgets import (QWidget,
                             QApplication,
                             QGridLayout,
                             QFormLayout,
                             QVBoxLayout,
                             QHBoxLayout,
                             QTabWidget,
                             QCheckBox,
                             QTextEdit,
                             QLineEdit,
                             QComboBox,
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
                             QDialog,
                             QInputDialog)
from PyQt5.QtGui import QImage, QPixmap,QBrush,QPen,QColor,QFont
from PyQt5.QtCore import Qt,QSize,QRectF,QLineF,QPointF,QTimer,QSettings


import pyqtgraph as pg
pg.setConfigOption('background', [200,200,200])
pg.setConfigOptions(imageAxisOrder='row-major')
pg.setConfigOption('crashWarning', True)

from .utils import *
cv2.setNumThreads(1)

colors = ['#d62728',
          '#1f77b4',
          '#ff7f0e',
          '#2ca02c',
          '#9467bd',
          '#8c564b',
          '#e377c2',
          '#7f7f7f',
          '#bcbd22'] 
penwidth = 1.


def sleep(dur = 1):
    tstart = time.time()
    while not (time.time()-tstart) > dur:
        QApplication.processEvents()

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
    def __init__(self,parent,label='',value=0,vmin = 0,vmax = 1000,step = None):
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
        if not step is None:
            self.slider.setSingleStep(step)
        self.slider.setMinimum(vmin)
        self.value = self.slider.value
    def link(self,func):
        self.slider.valueChanged.connect(func)

class QActionFloat(QWidgetAction):
    ''' Float edit for the right mouse button dropdown menu'''
    def __init__(self,parent,label='',value=0,
                 vmax = None,
                 vmin = None,
                 step = None):
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
        if not step is None:
            self.spin.setSingleStep(step)
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
        Datapath is relative to the folder specified in the preference.
        Can be set via UDP (expname=my_experiment/name) or ZMQ (dict(action='expname',value='my_experiment/name'))
'''
        self.expname = ''
        w2 = QWidget()
        l2 = QFormLayout()
        w2.setLayout(l2)
        self.experimentNameEdit = QLineEdit(' ')
        self.experimentNameEdit.returnPressed.connect(self.checkUpdateFilename)
        label = QLabel('Name:')
        label.setToolTip(info)
        self.experimentNameEdit.setToolTip(info)
        l2.addRow(label,self.experimentNameEdit)
        w = QGroupBox('Triggers and acquisition')
        l = QFormLayout()
        w.setLayout(l)
        self.camTriggerToggle = QCheckBox()
        self.camTriggerToggle.setChecked(self.parent.hardware_trigger_event.is_set())
        self.camTriggerToggle.stateChanged.connect(self.toggleHardwareTriggered)
        label = QLabel("Hardware trigger: ")
        label.setToolTip(info)
        info = '''Toggle the hardware trigger mode on cameras that support it.
This will can be differently configured for different cameras.'''
        self.camTriggerToggle.setToolTip(info)
        #l.addRow(label,self.camTriggerToggle) # skipping harware trigger for now.

        self.saveButton = QPushButton('Acquire')
        info = '''The button turns off the camera, starts saving and starts the camera. 
This is the same as pressing the software trigger checkbox, then manual save then the software trigger again.
If the camera is saving this stops the camera.'''
        self.saveButton.setToolTip(info)
        self.snapshotButton = QPushButton('Snapshot')
        def snapshot():
            self.checkUpdateFilename()
            for cam,wid in zip(self.parent.cams,
                                      self.parent.camwidgets):
                if not cam.writer is None:
                    fname = cam.writer.get_filename_path()
                    dataname = cam.writer.dataname
                elif hasattr(cam,'recorder') and not cam.recorder is None:
                    fname = cam.recorder.get_filename_path()
                    dataname = cam.recorder.dataname
                else:
                    fname = None
                    dataname = 'snapshot'
                if not fname is None:
                    fname = pjoin(os.path.dirname(fname),'snapshots',
                                  datetime.today().strftime(
                                      '%Y%m%d_%H%M%S_{0}.tif'.format(dataname)))
                    display('[Snapshot] - {0}'.format(fname))
                    wid.saveImageFromCamera(filename=fname)
        self.snapshotButton.clicked.connect(snapshot)
        self.saveOnStartToggle = QCheckBox()
        self.softTriggerToggle = QCheckBox()
        def saveButton():
            update_shared_date()
            if not self.saveOnStartToggle.isChecked():
                self.softTriggerToggle.setChecked(False)
                sleep(0.1)
                self.saveOnStartToggle.setChecked(True)
                sleep(0.1)
                self.softTriggerToggle.setChecked(True)
                self.saveButton.setText('Stop')                
            else:                
                self.softTriggerToggle.setChecked(False)
                sleep(0.1)
                self.saveOnStartToggle.setChecked(False)
                self.saveButton.setText('Acquire')
        self.saveButton.clicked.connect(saveButton)
        #self.saveButton
        self.softTriggerToggle.setChecked(False)
        self.softTriggerToggle.stateChanged.connect(
            self.toggleSoftwareTriggered)
        label = QLabel("Software trigger: ")
        info = '''Toggle the software trigger to start or stop acquisition using the camera control software.'''
        label.setToolTip(info)
        self.softTriggerToggle.setToolTip(info)
        l.addRow(label,self.softTriggerToggle)

        self.saveOnStartToggle.setChecked(self.parent.save_on_start)
        self.saveOnStartToggle.stateChanged.connect(self.toggleSaveOnStart)

        label = QLabel("Manual save: ")
        info = '''Stream data to disk. The checkbox starts and stops acquisition.'''
        label.setToolTip(info)
        self.saveOnStartToggle.setToolTip(info)
        self.saveButton.setFixedWidth(100)
        l.addRow(label,self.saveOnStartToggle)
        self.udpmessages = QLabel('')
        b1=QFont()
        b1.setPixelSize(16)
        b1.setFamily('Regular')
        b1.setBold(True)
        self.udpmessages.setFont(b1)
        self.udpmessages.setStyleSheet("color: rgb(255,165,0)")
        form.addRow(self.udpmessages)
        self.setLayout(form)
        self.layout = form
        l.addRow(self.saveButton,self.snapshotButton)
        l2.addRow(self.udpmessages)
        form.addRow(w,w2)

    def checkUpdateFilename(self,filename=None):
        if filename is None:
            filename = str(self.experimentNameEdit.text())
        if not self.expname == filename:
            self.parent.set_experiment_name(filename)
            self.expname = filename
        
    def toggleSoftwareTriggered(self,value):
        display('[labcams] Software trigger [{0}]'.format(value))
        if value:
            for cam in self.parent.cams:
                cam.start_acquisition()
                if hasattr(cam.cam,'analog_channels'):
                    display('Sleeping for 1 second for the DAQ to record.')
                    sleep(1)
            tstart[0] = time.time()
        else:
            for cam in self.parent.cams[::-1]:
                if hasattr(cam.cam,'analog_channels'):
                    display('Sleeping for 1 second for the DAQ to record.')
                    sleep(1)
                cam.stop_acquisition()
            camready = 0
            while camready != len(self.parent.cams):
                camready = np.sum([cam.camera_ready.is_set() for cam in self.parent.cams])
                QApplication.processEvents()
            display('[labcams] - All cameras ready to be triggered.')


    def toggleHardwareTriggered(self,value):
        update_shared_date()
        display('Hardware trigger mode pressed [{0}]'.format(value))
        if self.parent.save_on_start:
            self.checkUpdateFilename()
        if value:
            self.parent.hardware_trigger_event.set()
            self.recController.softTriggerToggle.setChecked(True)
            self.recController.saveOnStartToggle.setChecked(True)
            tstart[0] = time.time()
        else:
            #self.toggleSaveOnStart(False)
            # save button does not get unticked (this is a bug)
            self.parent.hardware_trigger_event.clear()
            self.recController.softTriggerToggle.setChecked(False)
            self.recController.saveOnStartToggle.setChecked(False)
        
    def toggleSaveOnStart(self,state):
        update_shared_date()
        self.parent.save_on_start = state
        self.checkUpdateFilename()
        for c,(cam,flg) in enumerate(zip(self.parent.cams,
                                                self.parent.saveflags)):
            if flg:
                cam.set_saving(state)
                if state:
                    self.experimentNameEdit.setDisabled(True)
                else:
                    self.experimentNameEdit.setDisabled(False)
        
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
        self.nchan = frame.shape[-1]
        if hasattr(self.cam,'excitation_trigger'):
            self.nchan = self.cam.excitation_trigger.nchannels.value
            self.frame_buffer = None
        self.displaychannel = -1  # default show all channels
        self.roiwidget = None
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        win = pg.GraphicsLayoutWidget()
        p1 = win.addPlot(title="")
        self.view = pg.ImageItem(background=[1,1,1])
        self.view.setAutoDownsample(True)
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
        self.lastFrame = 0
        if not 'NBackgroundFrames' in parameters.keys() or not parameters['SubtractBackground']:
            self.nAcum = 0
        else:
            self.nAcum = float(parameters['NBackgroundFrames'])
        self.eyeTracker = None
        self.string = '{0}'
        if not self.parameters['save_data']:
            self.string = 'no save -{0}'
        #self.image(np.array(frame),-1)
        size = 600
        #ratio = h/float(w)
        self.hist = None
###        self.setFixedSize(size,int(size*ratio))
        #self.resize(size,int(size*ratio))
        self.addActions()

        #self.show()
    def update(self):
        # handle the excitation module
        if hasattr(self.cam,'excitation_trigger'):
            if self.frame_buffer is None:
                self.frame_buffer = np.zeros([
                    self.cam.cam.h.value,
                    self.cam.cam.w.value,
                    3], dtype = self.cam.cam.dtype)
            cframe = self.cam.nframes.value
            tmp = self.cam.get_img(cframe)
            nchan = self.cam.excitation_trigger.nchannels.value
            self.frame_buffer[:,:,
                              np.mod(cframe,
                                     nchan)] = tmp.squeeze()
            if self.parent.downsample_cameras and not self.reference_toggle.value:
                return self.image(cv2.pyrDown(self.frame_buffer),cframe)
            else:
                return self.image(self.frame_buffer,cframe)
                
        else:
            frame = self.cam.get_img()
        if not frame is None:
            sp = frame.shape
            if self.parent.downsample_cameras and not self.reference_toggle.value:
                frame = cv2.pyrDown(frame)
            if not len(frame.shape) == len(sp):
                frame = frame.reshape((*frame.shape[:2],sp[-1]))
            self.image(frame,self.cam.nframes.value)
            
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
        if hasattr(self.cam.cam,'ctrevents'):
            self.ctract = dict()
            def vchanged(the):
                val = the['action'].value()
                self.cam.cam.eventsQ.put(the['name']+'='+str(val))

            for k in  self.cam.cam.ctrevents.keys():
                self.ctract[k] = dict(**self.cam.cam.ctrevents[k])
                ev = self.ctract[k]
                val = eval('self.cam.cam.' + ev['variable'])
                ev['name'] = k
                ev['action'] = None
                if ev['widget'] == 'slider':
                    ev['action'] = QActionSlider(self,
                                                 k+' [{0:03d}]:'.format(int(val)),
                                                 value = val,
                                                 vmin = ev['min'],
                                                 vmax = ev['max'],
                                                 step = ev['step'])
                elif ev['widget'] == 'float':
                    ev['action'] = QActionFloat(self,k,
                                                value = val,
                                                vmin = ev['min'],
                                                vmax = ev['max'],
                                                step = ev['step'])
                    
                if not ev['action'] is None:
                        #e.sublab.setText(k + ' [{0:03d}]:'.format(int(val)))
                    self.functs.append(partial(vchanged,self.ctract[k]))
                    ev['action'].link(self.functs[-1]) 
                    self.addAction(ev['action'])
            
        sep = QAction(self)
        sep.setSeparator(True)
        self.addAction(sep)
        if self.nchan > 1:
            displaychan = QActionSlider(self,'display channel',
                                       value = self.displaychannel,
                                       vmin = -1,
                                       vmax = self.nchan-1)
            def change_chan(value):
                self.displaychannel = int(value)
                if not self.roiwidget is None:
                    self.roiwidget.reset()
            displaychan.link(change_chan) 
            self.addAction(displaychan)
        # Slider
        toggleSubtract = QActionSlider(self,'Nsubtract [{0:03d}]:'.format(int(self.nAcum)),
                                       value = 0,
                                       vmin = 0,
                                       vmax = 200)
        toggleSubtract.link(lambda x: toggleSubtract.sublab.setText(
            'Nsubtract [{0:03d}]:'.format(int(x))))
        def vchanged(val):
            self.nAcum = float(np.floor(val))
            if not self.roiwidget is None:
                self.roiwidget.reset()

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
        
        self.autorange_toggle = QActionCheckBox(self,'Auto range',self.autoRange)
            
        self.autorange_toggle.link(self.toggleAutoRange)
        self.addAction(self.autorange_toggle)
        
        # histogram
        tEt = QAction('Histogram',self)
        tEt.triggered.connect(self.histogramWin)
        self.addAction(tEt)

        tEt = QAction('Saturation mode',self)
        tEt.triggered.connect(self.saturationMode)
        self.addAction(tEt)
        
        # Save
        ts = QActionCheckBox(self,'Save camera',  self.parent.saveflags[self.iCam])
        def toggleSaveCam():
            self.parameters['save_data'] = not self.parameters['save_data']
            self.parent.saveflags[self.iCam] = self.parameters['save_data']
            ts.checkbox.setChecked(self.parameters['save_data'])
            if not self.parameters['save_data']:
                self.string = 'no save - {0}'
            else:
                self.string = '{0}'            
        ts.link(toggleSaveCam)
        self.addAction(ts)
        self.reference_toggle = QActionCheckBox(self,'alignment reference',  False)
        self.reference_toggle.link(self.toggle_reference)
        self.addAction(self.reference_toggle)
        
    def toggle_reference(self,filename):
        if self.parameters['reference_channel'] is None:
            if not type(filename) is str:
                fdlg = QFileDialog().getOpenFileName(
                    self,
                    'Load reference image')
                filename = str(fdlg[0])

                print('Selected {0}'.format(filename))
            else:
                self.reference_toggle.checkbox.disconnect()
                self.reference_toggle.checkbox.setChecked(True)
                self.reference_toggle.link(self.toggle_reference)
                self.reference_toggle.value = True
        else:
            self.reference_toggle.checkbox.disconnect()
            self.reference_toggle.checkbox.setChecked(False)
            self.reference_toggle.link(self.toggle_reference)
            self.reference_toggle.value = False
            self.parameters['reference_channel'] = None
            return        
        if type(filename) is str and os.path.exists(filename):
            try:
                from skimage.io import imread
                from skimage.transform import resize
            except:
                from tifffile import imread
            display(filename)
            reference = imread(filename).squeeze()
            if len(reference.shape) > 2:
                reference = reference.mean(axis = -1)
            if 'resize' in dir(): # reshape if possible/needed
                reference = resize(reference,
                                   output_shape = self.view.image.shape)
            self.parameters['reference_channel'] = reference
            self.reference_toggle.checkbox.setChecked(True)

    def toggleAutoRange(self,value):
        self.autoRange = value #not self.autoRange
        if not self.autorange_toggle.checkbox.isChecked == value:
            self.autorange_toggle.checkbox.setChecked(self.autoRange)
        
    def histogramWin(self):
        if self.hist is None:
            histTab = QDockWidget("histogram cam {0}".format(self.iCam), self)
            histTab.setObjectName("histogram cam {0}".format(self.iCam))
            widget = QWidget()
            layout = QGridLayout()
            widget.setLayout(layout)
            win = pg.GraphicsLayoutWidget()
            p1 = win.addPlot()
            p1.getViewBox().invertY(True)
            p1.hideAxis('left')
            p1.hideAxis('bottom')
            
            self.hist = pg.HistogramLUTItem()
            self.hist.axis.setPen('k')
            p1.addItem(self.hist)
            self.hist.setImageItem(self.view)
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
        try:
            histstate = self.hist.saveState()
        except Exception as err:
            display('[ERROR] - could not save histogram state. "pip install pyqtgraph --upgrade" might solve it.')
            print(err)
        def closefun(ev):
            try:
                self.hist.restoreState(histstate)
            except Exception as err:
                print(err)
                pass
            self.hist = None
            ev.accept()
        histTab.closeEvent = closefun
        
    def saturationMode(self):
        if self.hist is None:
            self.histogramWin()
        if not self.hist.gradient is None:
            self.hist.gradient.addTick(0.751, color=pg.mkColor('#ff2d00'))
            self.hist.gradient.addTick(1, color=pg.mkColor('#ff2d00'))
            self.hist.gradient.addTick(0.75, color=pg.mkColor('#ffffff'))
            self.toggleAutoRange(False)
            dt = self.view.image.dtype
            self.hist.setLevels(np.iinfo(dt).min,np.iinfo(dt).max)

        
    def addROI(self,roi = None,smoothing_k = 1):
        if self.roiwidget is None:
            self.roiwidget = ROIPlotWidget(roi_target = self.p1,
                                           view = self.view,
                                           parent = self,
                                           smoothing_k = smoothing_k)
            roiTab = QDockWidget("roi cam {0}".format(self.iCam), self)
            roiTab.setObjectName("roi cam {0}".format(self.iCam))
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
            roiTab.resize(600,150)
            self.roiwidget.qtab = roiTab # to place it later if needed
            
            def closetab(ev):
                # This probably does not clean up memory...
                if not self.roiwidget is None:
                    [self.p1.removeItem(r)
                     for r in self.roiwidget.items()]
                    del self.roiwidget
                    self.roiwidget = None
                ev.accept()
            roiTab.closeEvent = closetab
        self.roiwidget.add_roi(roi)

    def toggleEyeTracker(self):
        if self.parameters['TrackEye']:
            self.eyeTracker = None
            if hasattr(self,'trackerpar'):
                self.trackerpar.close()
                self.trackerTab.close()
                [self.p1.removeItem(c) for c in self.tracker_roi.items()]
        self.parameters['TrackEye'] = not self.parameters['TrackEye']
        self.etrackercheck.checkbox.setChecked(self.parameters['TrackEye'])

    def saveImageFromCamera(self,filename=None):
        update_shared_date()
        frame = self.parent.cams[self.iCam].get_img_with_virtual_channels()
        
        if filename is None:
            self.parent.timer.stop()
            filename = QFileDialog.getSaveFileName(self,
                                               'Select filename to save.')
            self.parent.timer.start()
        if type(filename) is tuple:
            filename = filename[0]
        if filename:
            folder = os.path.dirname(filename)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            from tifffile import imsave
            if len(frame.shape)==3:
                frame = frame.transpose([2,0,1]).squeeze()
            imsave(str(filename),
                   frame,
                   metadata = {
                       'Camera':str(self.iCam)})
            display('Saved camera frame for cam: {0}'.format(self.iCam))
        else:
            display('Snapshot aborted.')
        
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
        self.trackerTab.setObjectName("mptracker cam {0}".format(self.iCam))
        self.eyeTracker.parameters['crTrack'] = True
        self.eyeTracker.parameters['sequentialCRMode'] = False
        self.eyeTracker.parameters['sequentialPupilMode'] = False
        self.tracker_roi = EyeROIWidget()
        [self.p1.addItem(c) for c in  self.tracker_roi.items()]
        self.trackerpar = MptrackerParameters(self.eyeTracker,image,eyewidget=self.tracker_roi)
        if self.parent.saveflags[self.iCam]:
            self.trackerToggle = QCheckBox()
            if not self.parent.cams[self.iCam].writer is None:
                pass
                #self.trackerToggle.setChecked(self.parent.writers[self.iCam].trackerFlag.is_set())
            #self.trackerToggle.stateChanged.connect(self.trackerSaveToggle)
            self.trackerpar.pGridSave.addRow(
                QLabel("Save cameras: "),self.trackerToggle)
        self.restracker = [0]
        self.addROI(self.restracker)
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
        writer = self.parent.cams[self.iCam].writer
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
            if self.parameters['Equalize']: # histogram equalization
                try: 
                    tmp = cv2.equalizeHist(tmp).reshape(image.shape)
                except:
                    pass
            if self.nAcum > 0:  # subtraction 
                tmp = tmp.astype(np.float32)
                frame = (tmp - self.lastFrame)
                self.lastFrame = ((1.-1./self.nAcum)*self.lastFrame +
                                  (1./self.nAcum)*tmp)
            else:
                self.lastFrame = 0
                frame = tmp
            if not self.roiwidget is None:
                self.roiwidget.update(frame,iFrame=nframe)
            if bool(self.parameters['TrackEye']):
                if self.eyeTracker is None:
                    self._open_mptracker(image[:,:,0])
                self.restracker[0] = np.nanmax(self.eyeTracker.apply(image[:,:,0])[2])
                self.displaychannel = -1
                if not self.eyeTracker.concatenateBinaryImage:
                    (x1,y1,w,h) = self.eyeTracker.parameters['imagecropidx']
                    if frame.shape[2] != 3:
                        frame = cv2.cvtColor(frame[:,:,0],cv2.COLOR_GRAY2RGB)
                    frame[y1:y1+h,x1:x1+w] = self.eyeTracker.img
                else:
                    frame = self.eyeTracker.img

            self.text.setText(self.string.format(nframe))
            if not self.displaychannel == -1:
                frame = frame[:,:,self.displaychannel]

            if self.parameters['reference_channel'] is None:
                if self.displaychannel == -1 and frame.shape[2]==2:
                    f = frame.copy()
                    frame = np.zeros((f.shape[0],f.shape[1],3),dtype = f.dtype)
                    frame[:,:,1] = f[:,:,0]
                    frame[:,:,2] = f[:,:,1]
                self.view.setImage(frame.squeeze(),
                                   autoLevels=self.autoRange, autoDownsample=True)
            else:
                frame = frame.squeeze()
                ref = self.parameters['reference_channel']
                im = np.stack([ref/np.max(ref),frame/np.max(frame),np.zeros_like(frame)]).transpose([1,2,0])
                self.view.setImage(im,autoDownsample=True)
            self.lastnFrame = nframe


class ROIPlotWidget(QWidget):
    def __init__(self, roi_target= None, view=None,
                 npoints = 1200, parent = None, smoothing_k = 1):
        super(ROIPlotWidget,self).__init__()	
        layout = QGridLayout()
        self.parent=parent
        self.setLayout(layout)
        self.view = view
        self.qtab = None
        self.roi_target = roi_target
        self.smoothing_k = smoothing_k
        win = pg.GraphicsLayoutWidget()
        self.p1 = win.addPlot()
        self.p1.getAxis('bottom').setPen('k') 
        self.p1.getAxis('left').setPen('k') 
        layout.addWidget(win,0,0)
        self.N = npoints
        self.rois = []
        self.plots = []
        self.buffers = []
        self.baseline = []

    def add_roi(self,roi = None):
        pencolor = colors[
            np.mod(len(self.plots),len(colors))]
        if not type(roi) is list:
            roi = pg.RectROI(pos=[100,100],
                             size=100,
                             pen=pencolor)
            self.roi_target.addItem(roi)
        self.rois.append(roi)
        self.plots.append(pg.PlotCurveItem(pen=pg.mkPen(
        color=pencolor, width=penwidth)))
        self.p1.addItem(self.plots[-1])
        buf = np.zeros([2,self.N],dtype=np.float32)
        buf[0,:] = np.nan
        buf[1,:] = 0
        self.buffers.append(buf)
        self.baseline.append(0)

    def items(self):
        return self.rois

    def closeEvent(self,ev):
        for roi in self.rois:
            self.roi_target.removeItem(roi)
        ev.accept()

    def reset(self):
        for ib in range(len(self.buffers)):
            self.buffers[ib][0,:] = np.nan
            self.baseline[ib] = 0
    def update(self,img,iFrame):
        
        ichan = -1
        if not self.parent is None:
            ichan = self.parent.displaychannel
        ctime = time.time() - tstart[0]
        if len(self.buffers):
            if (ctime  - np.nanmax(self.buffers[0][0,:])) < 0:
                print('resetting')
                self.reset()
        for i,(roi,plot) in enumerate(zip(self.rois,self.plots)):
            if type(roi) is list:
                r = np.array(roi)[-1]
            else:
                r = np.mean(roi.getArrayRegion(img[:,:,ichan], self.view)).copy()
            buf = np.roll(self.buffers[i], -1, axis = 1)
            buf[0,-1] = ctime
            alpha = 1
            if not np.isnan(r):
                alpha = np.clip(self.smoothing_k,0,1)
                self.baseline[i] +=  alpha*(r-self.baseline[i])
            buf[1,-1] = r - self.baseline[i]
            self.buffers[i] = buf
            ii = (~np.isnan(buf[0,:])) & (~np.isnan(buf[1,:]))
            plot.setData(x = buf[0,ii],
                         y = buf[1,ii])

class CamStimTriggerWidget(QWidget):
    def __init__(self,port = None,ino=None, outQ = None, cam = None):
        super(CamStimTriggerWidget,self).__init__()
        if (ino is None) and (not port is None):
            from .cam_stim_trigger import CamStimInterface
            ino = CamStimInterface(port = port,outQ = outQ)
        self.ino = ino
        self.cam = cam
        self.setObjectName("CamStimTrigger")
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

            if len(self.ino.modes):
                wcombo = QComboBox()
                wcombo.addItems(self.ino.modes)
                wcombo.setCurrentIndex(len(self.ino.modes)-1)
                wcombo.currentIndexChanged.connect(self.setMode)
                self.ino.set_mode(len(self.ino.modes))
                form.addRow(wcombo)

            wsync = QLabel()
            wsyncstr = 'sync {0} - frame {1}'
            def update_count():
                if ino.sync.value:
                    wsyncstr = '<b>sync {0} - frame {1}<\b>'
                else:
                    wsyncstr = 'sync {0} - frame {1}'               
                wsync.setText(wsyncstr.format(ino.sync_count.value,
                                              ino.sync_frame_count.value))
            
            form.addRow(wsync)
            self.t = QTimer()
            self.t.timeout.connect(update_count)
            self.t.start(100)
        self.setLayout(form)
            
    def setMode(self,i):
        self.ino.set_mode(i+1)
        self.ino.check_nchannels()
        sleep(0.1)
        if not self.cam is None:
            self.cam.nchan = self.ino.nchannels.value
        
    def close(self):
        self.ino.close()
        self.ino.join()


class SettingsDialog(QDialog):
    def __init__(self, settings = None):
        super(SettingsDialog,self).__init__()
        self.setWindowTitle('labcams')
        from .utils import _SERVER_SETTINGS,_RECORDER_SETTINGS,_OTHER_SETTINGS
        if settings is None:
            settings = {}
            for s in _SERVER_SETTINGS.keys():
                if not s.endswith('_help'):
                    if type(_SERVER_SETTINGS[s]) is list:
                        settings[s] = _SERVER_SETTINGS[s][0]
                    else:
                        settings[s] = _SERVER_SETTINGS[s]
                for s in _OTHER_SETTINGS.keys():
                    if not s.endswith('_help'):
                        settings[s] = _OTHER_SETTINGS[s]

            settings['cams'] = []
        self.currentcam = None    
        self.settings = settings
        layout = QFormLayout()
        self.setLayout(layout)

        from PyQt5.QtWidgets import QListWidget,QTabWidget
        
        self.cams_listw = QListWidget()
        for i,c in enumerate(settings['cams']):
            self.cams_listw.addItem('{0} - {1}'.format(c['name'],c['driver']))
            self.currentcam = i
        btadd = QPushButton('Add')
        layout.addRow('Cameras',btadd)
        btremove = QPushButton('Remove')
        nw = QWidget()
        nl = QHBoxLayout()
        nl.addWidget(btadd)
        nl.addWidget(btremove)
        nw.setLayout(nl)
        layout.addRow('Cameras',nw)
        def addcamera():
            self.settings['cams'].append(DEFAULTS['cams'][-1])
            c = self.settings['cams'][-1]
            self.cams_listw.addItem('{0} - {1}'.format(c['name'],
                                                       c['driver']))
        self.camwidget = CamSettingsDialog(settings = self.settings)

        def camselect():
            idx = self.cams_listw.currentRow()
            self.currentcam = idx
            self.camwidget.set_camera(idx)
            
        self.cams_listw.itemClicked.connect(camselect)
        btadd.clicked.connect(addcamera)
        b1 = QGroupBox()
        b1.setTitle('Remote (network) access settings')
        lay = QFormLayout(b1)
        for k in _SERVER_SETTINGS.keys():
            if not k.endswith('_help'):
                if not k in self.settings.keys():
                    self.settings[k] = _SERVER_SETTINGS[k]
                    if type(_SERVER_SETTINGS[k]) is list:
                        self.settings[k] = self.settings[k][0]
                if type(_SERVER_SETTINGS[k]) is list:
                    # then it is an option menu
                    par = QComboBox()
                    for i in _SERVER_SETTINGS[k]:
                        par.addItem(i)
                    print(self.settings[k])
                    index = par.findText(self.settings[k])
                    if index >= 0:
                        par.setCurrentIndex(index)
                else:
                    par = QLineEdit()
                    par.setText(str(self.settings[k]))
                lay.addRow(QLabel(k),par)
        layout.addRow(self.cams_listw,b1)
        layout.addRow(self.camwidget)
        b2 = QGroupBox()
        b2.setTitle('General settings')
        lay = QFormLayout(b2)
        for k in _OTHER_SETTINGS.keys():
            if not k.endswith('_help'):
                par = QLineEdit()
                if not k in self.settings.keys():
                    self.settings[k] = _OTHER_SETTINGS[k]
                par.setText(str(self.settings[k]))
                lay.addRow(QLabel(k),par)
        layout.addRow(b2)
        
        self.show()

class CamSettingsDialog(QWidget):
    def __init__(self, settings = None):
        super(CamSettingsDialog,self).__init__()
        if settings is None:
            settings = dict()
        self.settings = settings
        self.current = 0
        self.cam = dict()
        
        layout = QFormLayout()
        self.setLayout(layout)
        from .utils import _CAMERA_SETTINGS,_RECORDER_SETTINGS,_CAMERAS
        self.b1 = QGroupBox()
        self.b1.setTitle('Camera settings')
        self.b1_lay = QFormLayout(self.b1)
        self.drivername = QComboBox()
        for k in _CAMERAS.keys():
            self.drivername.addItem(_CAMERAS[k])
        self.b1_w = []
        w1 = QWidget()
        l = QFormLayout()
        w1.setLayout(l)
        l.addRow('Camera driver',self.drivername)
        self.drivername.currentIndexChanged.connect(self.set_driver)
        w2 = QWidget()
        l = QFormLayout()
        w2.setLayout(l)
        self.camname = QLineEdit()
        self.camname.setText('cam1')
        l.addRow('Name',self.camname)
        self.b1_lay.addRow(w1,w2)
        self.b2 = QGroupBox()
        self.b2.setTitle('Recorder settings')
        self.b2_lay = QFormLayout(self.b2)
        par = QComboBox()
        for i in _RECORDER_SETTINGS['recorder']:
            par.addItem(i)
        self.b2_w = []
        self.b2_lay.addRow('Recorder format',par)
        self.use_queue = QCheckBox()
        self.use_queue.setChecked(True)
        self.b2_lay.addRow('Use frame queue',self.use_queue)
        layout.addRow(self.b1)
        layout.addRow(self.b2)

    def set_camera(self,idx):
        self.current = idx
        self.camsettings = self.settings['cams'][self.current]
        self.set_driver(self.camsettings['driver'])
        
    def set_driver(self,value=None):
        from .utils import _CAMERA_SETTINGS,_CAMERAS
        drivers = [k for k in _CAMERAS.keys()]
        if not value is None:
            if type(value) is int:
                camdriver = drivers[value]
            else:
                camdriver = value.lower()
            if not len(self.camsettings):
                self.camsettings = dict(_CAMERA_SETTINGS[camdriver],driver = camdriver)
            # check that what is in the settings is not overwritten.
            self.drivername.setCurrentIndex(drivers.index(camdriver)) 
        self.camsettings['driver'] = camdriver
        self.set_camera_widgets()
        
    def set_camera_widgets(self):
        if len(self.b1_w):
            for i in self.b1_w:
                self.b1_lay.removeRow(i[0])
        self.b1_w = []
        from .utils import _CAMERA_SETTINGS,_CAMERAS
        sett = self.camsettings
        print(sett)
        for k in sett.keys():
            if not k in _CAMERA_SETTINGS[self.camsettings['driver']]:
                continue
            if type(sett[k]) is list:
                # then it is an option menu
                par = QComboBox()
                for i in sett[k]:
                    par.addItem(i)
                index = par.findText(self.settings[k])
                if index >= 0:
                    par.setCurrentIndex(index)
            else:
                par = QLineEdit()
            par.setText(str(self.camsettings[k]))
            l = QLabel(k)
            self.b1_lay.addRow(l,par)
            self.b1_w.append([l,par])

class DAQPlotWidget(QWidget):
    def __init__(self,
                 daq,
                 parent = None,
                 parameters = None):
        super(DAQPlotWidget,self).__init__()
        self.parent = parent
        self.daq = daq
        self.parameters = parameters
        layout = QGridLayout()
        self.setLayout(layout)

        win = pg.GraphicsLayoutWidget()
        self.p1 = win.addPlot()
        self.p1.getAxis('bottom').setPen('k') 
        self.p1.getAxis('left').setPen('k') 
        layout.addWidget(win,0,0)
        self.plots = []
        self.N = self.daq.data_buffer.shape[1]
        for i in range(self.daq.data_buffer.shape[0]):
            
            pencolor = colors[np.mod(i,len(colors))]
            self.plots.append(pg.PlotCurveItem(pen=pg.mkPen(
                color=pencolor, width=penwidth)))
            self.p1.addItem(self.plots[-1])

        chan = [self.daq.analog_channels[k] for k in self.daq.analog_channels.keys()]
        chan += [self.daq.digital_channels[k] for k in self.daq.digital_channels.keys()]
        self.p1.getAxis('left').setTicks([[
            ((1*i),p) for i,p in enumerate(chan)]])

    def update(self):
        for i, plot in enumerate(self.plots):
            Y = self.daq.data_buffer[i]
            if i<self.daq.ai_num_channels:
                # divide by int16:
                Y = Y.astype('float32')/32767
            plot.setData(x = np.arange(0,self.N),
                         y = Y*0.7 + i)
