from labcams.plugins import *
from labcams.widgets import *
import serial

class LickDetector(BasePlugin):
    def __init__(self, gui, duinoport = None,
                 camidx = None,
                 thresholds = [6,6],
                 use_dlc = True,
                 baudrate = 1000000):
        super(LickDetector,self).__init__(name = 'LickDetector',
                                          gui = gui)
        if len(gui.camwidgets) == 1:
            camidx = 0
        self.preferencefile = pjoin(preferencepath,'lickdetector.settings.json')
        self.subjectname = None
        if os.path.exists(self.preferencefile):
            with open(self.preferencefile, 'r') as infile:
                self.pref = json.load(infile)
        else:
            self.pref = dict(duinoport = duinoport,
                             camidx = camidx,
                             subjects = dict(),
                             dlc_model_path = pjoin(os.path.dirname(self.preferencefile),
                                                    'lick_detector',
                                                    'dlc_lick'),
                             use_dlc = True)

        if self.pref['camidx'] is None:
            from PyQt5.QtWidgets import QInputDialog
            self.pref['camidx'] = QInputDialog.getInt(
                None,'labcams',
                'Select a camera to add the LickDetector')[0]
        display('[LickDetector] - using cam {0}'.format(self.pref['camidx']))
        self.camwidget = gui.camwidgets[self.pref['camidx']]
        if not use_dlc:
            self.dlc = None
            self.camwidget.addROI(smoothing_k = 0.01)
            self.roi0 = self.camwidget.roiwidget.rois[0]
            self.roi0.setPos((200,130)),self.roi0.setSize((10,6))
            self.camwidget.addROI(smoothing_k = 0.01)
            self.roi1 = self.camwidget.roiwidget.rois[1]
            self.roi1.setPos((100,130)),self.roi1.setSize((10,6))
            # refresh the values faster
            self.roiwidget = self.camwidget.roiwidget
            self.roiwidget.qtab.setFloating(False)
        else:
            from dlclive import DLCLive
            self.dlc = DLCLive(self.pref['dlc_model_path'])
            self.dlc.init_inference()
            # add points
            self.spoutpoints = pg.ScatterPlotItem(size=20, brush=pg.mkBrush(31, 119, 180, 128))
            self.lickpoints = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(214, 39, 40, 128))
            self.nosepoints = pg.ScatterPlotItem(size=5, brush=pg.mkBrush(255, 127, 14, 128))            
            self.camwidget.p1.addItem(self.spoutpoints)
            self.camwidget.p1.addItem(self.nosepoints)
            self.camwidget.p1.addItem(self.lickpoints)

        gui.timer.stop()
        gui.update_frequency = 3
        gui.timer.start(gui.update_frequency)
    
        self.thresholds = thresholds
        if self.pref['duinoport'] is None:
            from PyQt5.QtWidgets import QInputDialog
            self.pref['duinoport'] = str(QInputDialog.getText(
                None,'labcams',
                'Select a serial port for the LickDetector.')[0])
        self.port = self.pref['duinoport']
        self.connect_duino()
        self.values = [False,False]
        self.save_settings()
    
    def connect_duino(self):
        if not self.port is None:
            try:
                self.usb = serial.Serial(port = self.port)
                self.usb.reset_output_buffer()
                self.usb.reset_input_buffer()
                display("[LickDetector] - Connected to {0}".format(self.port))
                                
            except:
                display("Failed to connect to {0}".format(self.port))

    def save_settings(self):
        with open(self.preferencefile, 'w') as outfile:
            json.dump(self.pref, outfile,
                      sort_keys = True, indent = 4)         
        
    def _parse_command(self,command,msg):
        if command.lower() == 'loadsettings':
            if msg in self.pref['subjects'].keys():
                print('Loading settings for {0}'.format(msg))
                p = self.pref['subjects'][msg]
                if self.dlc is None:
                    self.roi0.setPos(p['roi0_pos'])
                    self.roi0.setSize(p['roi0_size'])
                    self.roi1.setPos(p['roi1_pos'])
                    self.roi1.setSize(p['roi1_size'])
                    self.thresholds = p['thresholds']
        elif command.lower() == 'savesettings':
            if self.dlc is None:
                p0 = self.roi0.pos()
                s0 = self.roi0.size()
                p1 = self.roi1.pos()
                s1 = self.roi1.size()
                p = dict(roi0_pos = (p0[0],p0[1]),
                         roi0_size = (s0[0],s0[1]),
                         roi1_pos = (p1[0],p1[1]),
                         roi1_size = (s1[0],s1[1]),
                         thresholds = self.thresholds)
                self.pref['subjects'][msg] = p
                print('Saving settings for {0}'.format(msg))            
                self.save_settings()
            
    def update(self):
        if self.dlc is None:
            values = [f[-1,-1] for f in self.roiwidget.buffers]
            if not hasattr(self,'usb'):
                return
            for i,v in  enumerate(values): 
                if v>self.thresholds[i]:
                    cmd = '@U{0:1d}\n'.format(i).encode()
                    self.usb.write(cmd)
                    self.values[i] = True
                elif self.values[i]:
                    cmd = '@D{0:1d}\n'.format(i).encode()
                    self.usb.write(cmd)
                    self.values[i] = False
        else: # run dlc model
            frame = self.camwidget.cam.get_img()
            pose = self.dlc.get_pose(frame)
            detection_radius = 50
            
            # set the points
            s = pose[-2:]
            idx = s[:,2]>0.8
            self.spoutpoints.setData(x = s[idx,0],y = s[idx,1])
            n = pose[3:-2]
            idx = n[:,2]>0.8
            self.nosepoints.setData(x = n[idx,0],y = n[idx,1])
            t = pose[:3]
            idx = t[:,2]>0.8
            self.lickpoints.setData(x = t[idx,0],y = t[idx,1])

            # check if that worked
            spout_r = np.array([0,0])
            spout_l = np.array([0,0])
            if pose[-2][-1] > 0.8: # update if certain
                spout_l = pose[-1][:-1]
            if pose[-1][-1] > 0.8:
                spout_r = pose[-2][:-1]

            tongue = None
            if np.sum(pose[:3,2]) > 2.8: # need some confidence for this
                tongue = pose[:3,:2]
            if not tongue is None:
                dist_l = np.abs(tongue[1,:] - spout_l)
                dist_r = np.abs(tongue[1,:] - spout_r)
                licks = (np.sum(dist_l<detection_radius)==2,np.sum(dist_r<detection_radius)==2)
                for i,v in enumerate(licks):
                    if v and not self.values[i]:
                        cmd = '@U{0:1d}\n'.format(i).encode()
                        self.usb.write(cmd)
                        self.values[i] = True
            for i,v in enumerate(self.values):
                if self.values[i] and tongue is None:
                    cmd = '@D{0:1d}\n'.format(i).encode()
                    self.usb.write(cmd)
                    self.values[i] = False
            
