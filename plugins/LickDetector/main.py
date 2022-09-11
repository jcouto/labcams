from labcams.plugins import *
import serial

class LickDetector(BasePlugin):
    def __init__(self, gui, duinoport = None,
                 camidx = None,
                 thresholds = [6,6],
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
                             subjects = dict())
        if self.pref['camidx'] is None:
            from PyQt5.QtWidgets import QInputDialog
            self.pref['camidx'] = QInputDialog.getInt(
                None,'labcams',
                'Select a camera to add the LickDetector')[0]
        display('[LickDetector] - using cam {0}'.format(self.pref['camidx']))
        self.camwidget = gui.camwidgets[self.pref['camidx']] 
        self.camwidget.addROI()
        self.roi0 = self.camwidget.roiwidget.rois[0]
        self.roi0.setPos((200,130)),self.roi0.setSize((10,6))
        self.camwidget.addROI()
        self.roi1 = self.camwidget.roiwidget.rois[1]
        self.roi1.setPos((100,130)),self.roi1.setSize((10,6))
        # refresh the values faster
        gui.timer.stop()
        gui.update_frequency = 3
        gui.timer.start(gui.update_frequency)
    
        self.roiwidget = self.camwidget.roiwidget
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
                self.roi0.setPos(p['roi0_pos'])
                self.roi0.setSize(p['roi0_size'])
                self.roi1.setPos(p['roi1_pos'])
                self.roi1.setSize(p['roi1_size'])
        elif command.lower() == 'savesettings':
            p0 = self.roi0.pos()
            s0 = self.roi0.size()
            p1 = self.roi1.pos()
            s1 = self.roi1.size()
            p = dict(roi0_pos = (p0[0],p0[1]),
                     roi0_size = (s0[0],s0[1]),
                     roi1_pos = (p1[0],p1[1]),
                     roi1_size = (s1[0],s1[1]))
            self.pref['subjects'][msg] = p
            print('Saving settings for {0}'.format(msg))            
            self.save_settings()
            
    def update(self):
        values = [f[-1,-1] for f in self.roiwidget.buffers]
        if not hasattr(self,'usb'):
            return
        for i,v in  enumerate(values): 
            if v>self.thresholds[i]:
                cmd = '@U{0:1d}\n'.format(i).encode()
                self.usb.write(cmd)
                self.values[i] = True
            else:
                if self.values[i]:
                    cmd = '@D{0:1d}\n'.format(i).encode()
                    self.usb.write(cmd)
                    self.values[i] = False
