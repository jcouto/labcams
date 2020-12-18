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

from .utils import *
from .cams import *
from .io import *
from .widgets import *

LOGO = '''
                                             MMM
                                           MMMMMM
    MMM:               .MMMM             MMMM MMMMMMMM
    MMM:               .MMMM            MMMMM MMMMMMMM      
    MMM:               .MMMM             MMMM  MMMMMM        MM 
    MMM:  :MMMMMMMMM.  .MMMMOMMMMMM       MN     MMM      MMMMM 
    MMM:  :M     MMMM  .MMMMM?+MMMMM    MMMMMMMMMMMMMMM7MMMMMMM  
    MMM:         OMMM  .MMMM    MMMM    MMMMMMMMMMMMMMMMMMMMMMM 
    MMM:  .MMMMMMMMMM  .MMMM    ?MMM    MMMMMMMMMMMMMMMMMMMMMMM 
    MMM:  MMMM  .8MMM  .MMMM    ZMMM    MMMMMMMMMMMMMMMMMMMMMMM 
    MMM:  MMM=...8MMM  .MMMM    MMMM    MMMMMMMMMMMMMMM.MMMMMMM  
    MMM:  MMMMMMMMMMM  .MMMMMMMMMMM                        MMMM 
    MMM:   MMMMM 8MMM  .MMMM:MMMMZ                            M 

         MMMMMMN  =MMMMMMMM     MMMM.MMMM$ .+MMMM      MMMMMMM: 
       MMMMMMMMM  +MMMMMMMMM$   MMMMMMMMMMMMMMMMMM   MMMMMMMMM8 
      MMMM               MMMM   MMMM   MMMM    MMM+  MMM8       
      MMMZ          OMMMMMMMM   MMMM   NMMM    MMM?  MMMMMMM$   
      MMMI        MMMMM  MMMM   MMMM   NMMM    MMM?   ZMMMMMMMM 
      MMMM       7MMM    MMMM   MMMM   NMMM    MMM?        MMMM 
       MMMMD+7MM  MMMN   MMMM   MMMM   NMMM    MMM?  MM$:.7MMMM   
        MMMMMMMM  ZMMMMMOMMMM   MMMM   NMMM    MMM?  MMMMMMMM+                                                              
                          https://bitbucket.org/jpcouto/labcams
'''

N_UDP = 1024

class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, expName = 'test',
                 camDescriptions = [],
                 parameters = {},
                 server = True,
                 saveOnStart = False,
                 triggered = False,
                 software_trigger = True,
                 updateFrequency = 33):
        '''
        Graphical interface for controling labcams.
        '''
        super(LabCamsGUI,self).__init__()
        self.parameters = parameters
        if not 'recorder_frames_per_file' in self.parameters.keys():
            self.parameters['recorder_frames_per_file'] = 0
        self.app = app
        self.updateFrequency=updateFrequency
        self.saveOnStart = saveOnStart
        self.cam_descriptions = camDescriptions
        self.software_trigger = software_trigger
        self.triggered = Event()
        if triggered:
            self.triggered.set()
        else:
            self.triggered.clear()
        if server:
            if not 'server_refresh_time' in self.parameters.keys():
                self.parameters['server_refresh_time'] = 30
            if not 'server' in self.parameters.keys():
                self.parameters['server'] = 'zmq'
            if self.parameters['server'] == 'udp':
                import socket
                self.udpsocket = socket.socket(socket.AF_INET, 
                                     socket.SOCK_DGRAM) # UDP
                self.udpsocket.bind(('0.0.0.0',
                                     self.parameters['server_port']))
                display('Listening to UDP port: {0}'.format(
                    self.parameters['server_port']))
                self.udpsocket.settimeout(.02)
            else:
                import zmq
                self.zmqContext = zmq.Context()
                self.zmqSocket = self.zmqContext.socket(zmq.REP)
                self.zmqSocket.bind('tcp://0.0.0.0:{0}'.format(
                    self.parameters['server_port']))
                display('Listening to ZMQ port: {0}'.format(
                    self.parameters['server_port']))
            self.serverTimer = QTimer()
            self.serverTimer.timeout.connect(self.serverActions)
            self.serverTimer.start(self.parameters['server_refresh_time'])


        # Init cameras
        camdrivers = [cam['driver'].lower() for cam in camDescriptions]
        if 'avt' in camdrivers:
            from .avt import AVT_get_ids
            try:
                avtids,avtnames = AVT_get_ids()
            except Exception as e:
                display('[ERROR] AVT  camera error? Connections? Parameters?')
                print(e)
        self.camQueues = []
        self.saveflags = []
        self.writers = []
        connected_avt_cams = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if not 'Save' in cam.keys():
                cam['Save'] = True
            self.saveflags.append(cam['Save'])
            if not 'recorder' in cam.keys():
                # defaults tiff
                cam['recorder'] = 'tiff'
            if 'saveMethod' in cam.keys():
                cam['recorder'] = cam['saveMethod']
            if not 'compress' in cam.keys():
                cam['compress'] = 0
            if not 'recorder_path_format' in self.parameters.keys():
                self.parameters['recorder_path_format'] = pjoin('{datafolder}','{dataname}','{filename}','{today}_{run}_{nfiles}')

            self.camQueues.append(Queue())
            if 'noqueue' in cam['recorder']:
                recorderpar = dict(
                    recorder = cam['recorder'],
                    datafolder = self.parameters['recorder_path'],
                    framesperfile = self.parameters['recorder_frames_per_file'],
                    pathformat = self.parameters['recorder_path_format'],
                    compression = cam['compress'],
                    filename = expName,
                    dataname = cam['description'])
                if 'ffmpeg' in cam['recorder']:
                    if 'hwaccel' in cam.keys():
                        recorderpar['hwaccel'] = cam['hwaccel']
            else:
                display('Using the queue for recording.')
                recorderpar = None # Use a queue recorder
            if cam['driver'].lower() == 'avt':
                try:
                    from .avt import AVTCam
                except Exception as err:
                    print(err)
                    print(''' 

                    Could not load the Allied Vision Technologies driver. 
    
    If you want to record from AVT cameras install the Vimba SDK and pimba.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json

''')
                    sys.exit(1)
                    
                camids = [(camid,name) for (camid,name) in zip(avtids,avtnames) 
                          if cam['name'] in name]
                camids = [camid for camid in camids
                          if not camid[0] in connected_avt_cams]
                if len(camids) == 0:
                    display('Could not find or already connected to: '+cam['name'])
                    display('Available AVT cameras:')
                    print('\n                -> '+
                          '\n                -> '.join(avtnames))
                    
                    sys.exit()
                cam['name'] = camids[0][1]
                if not 'TriggerSource' in cam.keys():
                    cam['TriggerSource'] = 'Line1'
                if not 'TriggerMode' in cam.keys():
                    cam['TriggerMode'] = 'LevelHigh'
                if not 'TriggerSelector' in cam.keys():
                    cam['TriggerSelector'] = 'FrameStart'
                if not 'AcquisitionMode' in cam.keys():
                    cam['AcquisitionMode'] = 'Continuous'
                if not 'AcquisitionFrameCount' in cam.keys():
                    cam['AcquisitionFrameCount'] = 1000
                if not 'nFrameBuffers' in cam.keys():
                    cam['nFrameBuffers'] = 6
                self.cams.append(AVTCam(camId=camids[0][0],
                                        outQ = self.camQueues[-1],
                                        frameRate=cam['frameRate'],
                                        gain=cam['gain'],
                                        triggered = self.triggered,
                                        triggerSource = cam['TriggerSource'],
                                        triggerMode = cam['TriggerMode'],
                                        triggerSelector = cam['TriggerSelector'],
                                        acquisitionMode = cam['AcquisitionMode'],
                                        nTriggeredFrames = cam['AcquisitionFrameCount'],
                                        nFrameBuffers = cam['nFrameBuffers'],
                                        recorderpar = recorderpar))
                connected_avt_cams.append(camids[0][0])
            elif cam['driver'].lower() == 'qimaging':
                try:
                    from .qimaging import QImagingCam
                except Exception as err:
                    print(err)
                    print(''' 

                    Could not load the QImaging driver. 
    If you want to record from QImaging cameras install the QImaging driver.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the QImaging cam or use the -c option 

''')
                    sys.exit(1)
                    
                if not 'binning' in cam.keys():
                    cam['binning'] = 2
                self.cams.append(QImagingCam(camId=cam['id'],
                                             outQ = self.camQueues[-1],
                                             exposure=cam['exposure'],
                                             gain=cam['gain'],
                                             binning = cam['binning'],
                                             triggerType = cam['triggerType'],
                                             triggered = self.triggered,
                                             recorderpar = recorderpar))
                                        
            elif cam['driver'].lower() == 'opencv':
                self.cams.append(OpenCVCam(camId=cam['id'],
                                           outQ = self.camQueues[-1],
                                           triggered = self.triggered,
                                           **cam,
                                           recorderpar = recorderpar))
            elif cam['driver'].lower() == 'pco':
                try:
                    from .pco import PCOCam
                except Exception as err:
                    print(err)
                    print(''' 

                    Could not load the PCO driver. 

    If you want to record from PCO cameras install the PCO.sdk driver.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the PCO cam or use the -c option

''')

                    sys.exit(1)
                    
                if 'CamStimTrigger' in cam.keys():
                    if not cam['CamStimTrigger'] is None:
                        self.camstim_widget = CamStimTriggerWidget(
                            port = cam['CamStimTrigger']['port'],
                            outQ = self.camQueues[-1])
                        camstim = self.camstim_widget.ino
                else:
                    camstim = None
                if not 'binning' in cam.keys():
                    cam['binning'] = None
                self.cams.append(PCOCam(camId=cam['id'],
                                        binning = cam['binning'],
                                        exposure = cam['exposure'],
                                        outQ = self.camQueues[-1],
                                        acquisition_stim_trigger = camstim,
                                        triggered = self.triggered,
                                        recorderpar = recorderpar))
            elif cam['driver'].lower() == 'ximea':
                try:
                    from .ximeacam import XimeaCam
                except Exception as err:
                    print(''' 

                    Could not load the Ximea driver. 

    If you want to record from Ximea cameras install the Ximea driver.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the ximea cam or use the -c option

''')
                    raise(err)
                self.cams.append(XimeaCam(camId=cam['id'],
                                          binning = cam['binning'],
                                          exposure = cam['exposure'],
                                          outQ = self.camQueues[-1],
                                          triggered = self.triggered,
                                          recorderpar = recorderpar))
            elif cam['driver'].lower() == 'pointgrey':
                try:
                    from .pointgreycam import PointGreyCam
                except Exception as err:
                    print(err)

                    print(''' 

                    Could not load the PointGrey driver.
 
    If you want to record from PointGrey/FLIR cameras install the Spinaker SDK.
    If not you have the wrong config file.

            Edit the file in USERHOME/labcams/default.json and delete the PointGrey cam or use the -c option

''')
                    sys.exit()
                if not 'roi' in cam.keys():
                    cam['roi'] = []
                if not 'pxformat' in cam.keys():
                    cam['pxformat'] = 'Mono8' #'BayerRG8'
                if not 'serial' in cam.keys():
                    # camera serial number
                    cam['serial'] = None 
                if not 'binning' in cam.keys():
                    cam['binning'] = None
                if not 'exposure' in cam.keys():
                    cam['exposure'] = None
                if not 'gamma' in cam.keys():
                    cam['gamma'] = None
                if not 'hardware_trigger' in cam.keys():
                    cam['hardware_trigger'] = None
                if cam['roi'] is str:
                    if ',' in cam['roi']:
                        cam['roi'] = [int(c.strip('[').strip(']')) for c in cam['roi'].split(',')]
                    else:
                        cam['roi'] = []
                self.cams.append(PointGreyCam(camId=cam['id'],
                                              serial = cam['serial'],
                                              gain = cam['gain'],
                                              roi = cam['roi'],
                                              frameRate = cam['frameRate'],
                                              pxformat = cam['pxformat'],
                                              exposure = cam['exposure'],
                                              binning = cam['binning'],
                                              gamma = cam['gamma'],
                                              outQ = self.camQueues[-1],
                                              triggered = self.triggered,
                                              recorderpar = recorderpar,
                                              hardware_trigger = cam['hardware_trigger']))
            else: 
                display('[WARNING] -----> Unknown camera driver' +
                        cam['driver'])
                self.camQueues.pop()
                self.saveflags.pop()
            if not 'recorder_sleep_time' in self.parameters.keys():
                self.parameters['recorder_sleep_time'] = 0.3
            if 'SaveMethod' in cam.keys():
                cam['recorder'] = cam['SaveMethod']
                display('SaveMethod is deprecated, use recorder instead.')
            if not 'noqueue' in cam['recorder']:
                towriter = dict(inQ = self.camQueues[-1],
                                datafolder=self.parameters['recorder_path'],
                                pathformat = self.parameters['recorder_path_format'],
                                framesperfile=self.parameters['recorder_frames_per_file'],
                                sleeptime = self.parameters['recorder_sleep_time'],
                                filename = expName,
                                dataname = cam['description'])
                if  cam['recorder'] == 'tiff':
                    display('Recording to TIFF')
                    self.writers.append(TiffWriter(compression = cam['compress'],
                                                   **towriter))
                elif cam['recorder'] == 'ffmpeg':
                    display('Recording with ffmpeg')
                    if not 'hwaccel' in cam.keys():
                        cam['hwaccel'] = None
                    self.writers.append(FFMPEGWriter(compression = cam['compress'],
                                                     hwaccel = cam['hwaccel'],
                                                     **towriter))
                elif cam['recorder'] == 'binary':
                    display('Recording binary')
                    self.writers.append(BinaryWriter(**towriter))
                elif cam['recorder'] == 'opencv':
                    display('Recording opencv')
                    self.writers.append(OpenCVWriter(compression = cam['compress'],**towriter))
                else:
                    print(''' 

The available recorders are:
    - tiff (multiple tiffstacks - the default)   
    - binary 
    - ffmpeg  Records video format using ffmpeg (hwaccel options: intel, nvidia - remove for no hardware acceleration)
    - opencv  Records video format using openCV

The recorders can be specified with the '"recorder":"ffmpeg"' option in each camera setting of the config file.
''')
                    raise ValueError('Unknown recorder {0} '.format(cam['recorder']))
            else:
                self.writers.append(None)
                
            if 'CamStimTrigger' in cam.keys():
                self.camstim_widget.outQ = self.camQueues[-1]
            # Print parameters
            display('\t Camera: {0}'.format(cam['name']))
            for k in np.sort(list(cam.keys())):
                if not k == 'name' and not k == 'recorder':
                    display('\t\t - {0} {1}'.format(k,cam[k]))
        #self.resize(100,100)

        self.initUI()
        
        self.camerasRunning = False
        if hasattr(self,'camstim_widget'):
            self.camstim_widget.ino.start()
            self.camstim_widget.ino.disarm()

        for cam,writer in zip(self.cams[::-1],self.writers[::-1]):
            cam.start()
            if not writer is None:
                writer.init(cam)
                writer.start()
        
        camready = 0
        while camready != len(self.cams):
            camready = np.sum([cam.camera_ready.is_set() for cam in self.cams])
        display('Initialized cameras.')

        if hasattr(self,'camstim_widget'):
            self.camstim_widget.ino.arm()

        self.triggerCams(soft_trigger = self.software_trigger,
                         save=self.saveOnStart)

    def setExperimentName(self,expname):
        # Makes sure that the experiment name has the right slashes.
        if os.path.sep == '/':
            expname = expname.replace('\\',os.path.sep)
        expname = expname.strip(' ')
        for flg,writer,cam in zip(self.saveflags,self.writers,self.cams):
            if flg:
                if not writer is None:
                    writer.set_filename(expname)
                else:
                    display('Setting serial recorder filename.')
                    cam.eventsQ.put('filename='+expname)
        #time.sleep(0.15)
        self.recController.experimentNameEdit.setText(expname)
        
    def serverActions(self):
        if self.parameters['server'] == 'zmq':
            try:
                message = self.zmqSocket.recv_pyobj(flags=zmq.NOBLOCK)
            except:
                return
            self.zmqSocket.send_pyobj(dict(action='handshake'))
        elif self.parameters['server'] == 'udp':
            try:
                msg,address = self.udpsocket.recvfrom(N_UDP)
            except:
                return
            msg = msg.decode().split('=')
            message = dict(action=msg[0])
            if len(msg) > 1:
                message = dict(message,value=msg[1])
        #display('Server received message: {0}'.format(message))
        if message['action'].lower() == 'expname':
            self.setExperimentName(message['value'])
            self.udpsocket.sendto(b'ok=expname',address)
        elif message['action'].lower() == 'softtrigger':
            self.recController.softTriggerToggle.setChecked(
                int(message['value']))
            self.udpsocket.sendto(b'ok=software_trigger',address)
        elif message['action'].lower() == 'trigger':
            for cam in self.cams:
                cam.stop_acquisition()
            # make sure all cams closed
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                cam.stop_saving()
                #if not writer is None: # Logic moved to inside camera.
                #    writer.write.clear()
            self.triggerCams(soft_trigger = self.software_trigger,save = True)
            self.udpsocket.sendto(b'ok=save_hardwaretrigger',address)
        elif message['action'].lower() == 'settrigger':
            self.recController.camTriggerToggle.setChecked(
                int(message['value']))
            self.udpsocket.sendto(b'ok=hardware_trigger',address)
        elif message['action'].lower() in ['setmanualsave','manualsave']:
            self.recController.saveOnStartToggle.setChecked(
                int(message['value']))
            self.udpsocket.sendto(b'ok=save',address)
        elif message['action'].lower() == 'log':
            for cam in self.cams:
                cam.eventsQ.put('log={0}'.format(message['value']))
            # write on display
            #self.camwidgets[0].text_remote.setText(message['value'])
            self.udpsocket.sendto(b'ok=log',address)
            self.recController.udpmessages.setText(message['value'])
        elif message['action'].lower() == 'ping':
            display('Server got PING.')
            self.udpsocket.sendto(b'pong',address)
        elif message['action'].lower() == 'quit':
            self.udpsocket.sendto(b'ok=bye',address)
            self.close()
    def triggerCams(self,soft_trigger = True, save=False):
        # stops previous saves if there were any
        display("Waiting for the cameras to be ready.")
        for c,cam in enumerate(self.cams):
            while not cam.camera_ready.is_set():
                time.sleep(0.001)
            display('Camera [{0}] ready.'.format(c))
        display('Doing save ({0}) and trigger'.format(save))
        if save:
            for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                                    self.saveflags,
                                                    self.writers)):
                if flg:
                    cam.saving.set()
                    if not writer is None:
                        writer.write.set()
        else:
            for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                                    self.saveflags,
                                                    self.writers)):
                if flg:
                    if not writer is None:
                        cam.stop_saving()
                    #writer.write.clear() # cam stops writer
        #time.sleep(2)
        if soft_trigger:
            for c,cam in enumerate(self.cams):
                cam.start_trigger.set()
            display('Software triggered cameras.')
        
    def experimentMenuTrigger(self,q):
        if q.text() == 'Set refresh time':
            self.timer.stop()
            res = QInputDialog().getDouble(self,"What refresh period do you want?","GUI refresh period",
                                           self.updateFrequency)
            if res[1]:
                self.updateFrequency = res[0]
            self.timer.start(self.updateFrequency)
            #display(q.text()+ "clicked. ")
        
    def initUI(self):
        # Menu
        self.setDockOptions(QMainWindow.AllowTabbedDocks |
                            QMainWindow.AllowNestedDocks
)
        bar = self.menuBar()
        editmenu = bar.addMenu("Options")
        editmenu.addAction("Set refresh time")
        editmenu.triggered[QAction].connect(self.experimentMenuTrigger)
        self.setWindowTitle("labcams")
        self.tabs = []
        self.camwidgets = []
        self.recController = RecordingControlWidget(self)
        #self.setCentralWidget(self.recController)
        self.recControllerTab = QDockWidget("",self)
        self.recControllerTab.setWidget(self.recController)
        self.addDockWidget(
            Qt.TopDockWidgetArea,
            self.recControllerTab)
        self.recController.setFixedHeight(self.recController.layout.sizeHint().height())
        for c,cam in enumerate(self.cams):
            tt = ''
            if self.saveflags[c]:
                tt +=  ' - ' + self.cam_descriptions[c]['description'] +' ' 
            self.tabs.append(QDockWidget("Camera: "+str(c) + tt,self))
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w,cam.nchan),
                                                              dtype=cam.dtype),
                                             iCam = c,
                                             parent = self,
                                             parameters = self.cam_descriptions[c]))
            self.tabs[-1].setWidget(self.camwidgets[-1])
            self.tabs[-1].setFloating(False)
            self.tabs[-1].setAllowedAreas(Qt.LeftDockWidgetArea |
                                          Qt.RightDockWidgetArea |
                                          Qt.BottomDockWidgetArea |
                                          Qt.TopDockWidgetArea)
            self.tabs[-1].setFeatures(QDockWidget.DockWidgetMovable |
                                      QDockWidget.DockWidgetFloatable)
            self.addDockWidget(
                Qt.BottomDockWidgetArea,
                self.tabs[-1])
            self.tabs[-1].setMinimumHeight(300)
            # there can only be one of these for now?
            if hasattr(self,'camstim_widget'):
                self.camstim_tab = QDockWidget("Camera excitation control",self)
                self.camstim_tab.setWidget(self.camstim_widget)
                self.addDockWidget(
                    Qt.LeftDockWidgetArea,
                self.camstim_tab)
            display('Init view: ' + str(c))
        self.timer = QTimer()
        self.timer.timeout.connect(self.timerUpdate)
        self.timer.start(self.updateFrequency)
        #self.move(0, 0)
        self.show()
            	
    def timerUpdate(self):
        for c,cam in enumerate(self.cams):
            try:
                #self.camwidgets[c].image(frame,cam.nframes.value)
                frame = cam.get_img()
                if not frame is None:
                    self.camwidgets[c].image(frame,cam.nframes.value) #frame
            except Exception as e:
                display('Could not draw cam: {0}'.format(c))
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(
                    exc_tb.tb_frame.f_code.co_filename)[1]
                print(e, fname, exc_tb.tb_lineno)

    def closeEvent(self,event):
        if hasattr(self,'serverTimer'):
            self.serverTimer.stop()
        self.timer.stop()
        if hasattr(self,'camstim_widget'):
            self.camstim_widget.ino.disarm()
            self.camstim_widget.close()
            
        display('Acquisition stopped (close event).')
        for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                            self.saveflags,
                                            self.writers)):
            if flg:
                cam.stop_saving()
                #writer.write.clear() # logic moved inside writer
                if not writer is None:
                    writer.stop()
            cam.close()
        for c in self.cams:
            c.join()
        for c,(cam,flg,writer) in enumerate(zip(self.cams,
                                                self.saveflags,
                                                self.writers)):
            if flg:
                if not writer is None:
                    writer.join()
        pg.setConfigOption('crashWarning', False)
        event.accept()


def main():

    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    import os
    import json
    parser = ArgumentParser(description=LOGO + '\n\n  Multiple camera control and recording.',formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('file',
                        metavar='file',
                        type=str,
                        default=None,
                        nargs="?")
    parser.add_argument('-d','--make-config',
                        type=str,
                        default = None,
                        action='store')
    parser.add_argument('-w','--wait',
                        default = False,
                        action='store_true')
    parser.add_argument('-t','--triggered',
                        default=False,
                        action='store_true')
    parser.add_argument('-c','--cam-select',
                        type=int,
                        nargs='+',
                        action='store')
    parser.add_argument('--no-server',
                        default=False,
                        action='store_true')
    parser.add_argument('--bin-to-mj2',
                        default=False,
                        action='store_true')
    parser.add_argument('--mj2-rate',
                        default=30.,
                        action='store')
    
    opts = parser.parse_args()

    if opts.bin_to_mj2:
        from labcams.io import mmap_dat
        
        fname = opts.file
        
        assert not fname is None, "Need to supply a binary filename to compress."
        assert os.path.isfile(fname), "File {0} not found".format(fname)
        ext = os.path.splitext(fname)[-1]
        assert ext in ['.dat','.bin'], "File {0} needs to be binary.".format(fname)  
        stack = mmap_dat(fname)
        stack_to_mj2_lossless(stack, fname, rate = opts.mj2_rate)
        print('Converted {0}'.format(fname.replace(ext,'.mov')))
        sys.exit(0)
        
    if not opts.make_config is None:
        from .widgets import SettingsDialog
        app = QApplication(sys.argv)
        s = SettingsDialog(getPreferences())
        sys.exit(app.exec_())
        fname = opts.make_config
        getPreferences(fname, create=True)
        sys.exit(s.exec_())
    parameters = getPreferences(opts.file)
    cams = parameters['cams']
    if not opts.cam_select is None:
        cams = [parameters['cams'][i] for i in opts.cam_select]

    app = QApplication(sys.argv)
    w = LabCamsGUI(app = app,
                   camDescriptions = cams,
                   parameters = parameters,
                   server = not opts.no_server,
                   software_trigger = not opts.wait,
                   triggered = opts.triggered)
    sys.exit(app.exec_())
    
if __name__ == '__main__':
    main()
