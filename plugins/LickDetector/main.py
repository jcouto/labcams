from labcams.plugins import *
import serial

class LickDetector(BasePlugin):
    def __init__(self, gui, duinoport = None,
                 camidx = None,
                 thresholds = [6,6],
                 baudrate = 1000000):
        if len(gui.camwidgets) == 1:
            camidx = 0
        if camidx is None:
            from PyQt5.QtWidgets import QInputDialog
            camidx = QInputDialog.getInt(None,'labcams','Select a camera to add the LickDetector')[0]
        display('[LickDetector] - using cam {0}'.format(camidx))

        self.camwidget = gui.camwidgets[camidx] # cam zero is the one on the licks
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
        if duinoport is None:
            from PyQt5.QtWidgets import QInputDialog
            duinoport = str(QInputDialog.getText(None,'labcams','Select a serial port for the LickDetector.')[0])
        
        self.port = duinoport
        self.connect_duino()
        self.values = [False,False]
    
    def connect_duino(self):
        if not self.port is None:
            try:
                self.usb = serial.Serial(port = self.port)
                self.usb.reset_output_buffer()
                self.usb.reset_input_buffer()
                display("[LickDetector] - Connected to {0}".format(self.port))
                                
            except:
                display("Failed to connect to {0}".format(self.port))

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
