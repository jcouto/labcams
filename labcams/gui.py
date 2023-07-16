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
                 server = False,
                 save_on_start = False,
                 hardware_trigger = False,
                 software_trigger = True,
                 update_frequency = 33):
        '''
        Graphical interface for controling labcams.
        '''
        super(LabCamsGUI,self).__init__()

        self.software_trigger = software_trigger # one trigger per camera so we can control the timing (daq sleeps before)
        self.hardware_trigger_event = Event()
        if hardware_trigger:
            self.hardware_trigger_event.set()
        else:
            self.hardware_trigger_event.clear()
        
        self.parameters = parameters
        self.app = app
        self.plugins = []
        self.update_frequency = update_frequency
        self.save_on_start = save_on_start
        self.cam_descriptions = camDescriptions
        self.zmqsocket = None
        self.udpsocket = None
        if not 'downsample_display' in self.parameters.keys():
            self.downsample_cameras = False
        else:
            self.downsample_cameras = self.parameters['downsample_display']
        if server:
            if not 'server_refresh_time' in self.parameters.keys():
                self.parameters['server_refresh_time'] = 5
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
                self.zmqsocket = self.zmqContext.socket(zmq.REP)
                self.zmqsocket.bind('tcp://0.0.0.0:{0}'.format(
                    self.parameters['server_port']))
                display('Listening to ZMQ port: {0}'.format(
                    self.parameters['server_port']))
            self.server_timer = QTimer()
            self.server_timer.timeout.connect(self.server_actions)
            self.server_timer.start(self.parameters['server_refresh_time'])
        
        # Init cameras
        if not 'recorder_path_format' in self.parameters.keys():
            print('Using default recorder_path_format value.')
            self.parameters['recorder_path_format'] = pjoin('{datafolder}',
                                                            '{dataname}',
                                                            '{filename}',
                                                            '{today}_{run}_{nfiles}')
        if not 'recorder_path' in self.parameters.keys():
            self.parameters['recorder_path'] = pjoin(os.path.expanduser('~'),'data'),

        if not 'recorder_frames_per_file' in self.parameters.keys():
            self.parameters['recorder_frames_per_file'] = 0

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
        connected_avt_cams = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if not 'save_data' in cam.keys():   # to disable the saving for an individual camera
                cam['save_data'] = True
            self.saveflags.append(cam['save_data'])                
            cam = dict(cam,
                       filename = expName,
                       recorder_path = self.parameters['recorder_path'],
                       recorder_path_format = self.parameters['recorder_path_format'])
            # default recorder
            if not 'recorder' in cam.keys():
                cam['recorder'] = dict(format='tiff',  
                                       method = 'queue',
                                       compression = 0,
                                       frames_per_file = 1024,
                                       sleep_time = 0.3)
            self.cams.append(Camera(**cam,
                                    hardware_trigger_event = self.hardware_trigger_event))
            if hasattr(self.cams[-1],'excitation_trigger'):
                self.excitation_trigger = self.cams[-1].excitation_trigger
                self.excitation_trigger_widget = CamStimTriggerWidget(
                    ino = self.cams[-1].excitation_trigger,
                    cam = self.cams[-1].cam)
                self.camstim_tab = QDockWidget("Camera excitation control",self)
                self.camstim_tab.setObjectName("Cam stim")

                self.camstim_tab.setWidget(self.excitation_trigger_widget)
                self.addDockWidget(
                    Qt.LeftDockWidgetArea,
                    self.camstim_tab)
            # Print parameters
            display('\t Camera: {0}'.format(cam['name']))
            for k in np.sort(list(cam.keys())):
                if not k == 'name' and not k == 'recorder':
                    display('\t\t - {0} {1}'.format(k,cam[k]))
        self.initUI()
        
        self.camerasRunning = False
        
        for cam in self.cams[::-1]:
            cam.start()
        
        camready = 0
        while camready != len(self.cams):
            camready = np.sum([cam.camera_ready.is_set() for cam in self.cams])
        display('[labcams] - Initialized cameras.')
        
        self.recController.saveOnStartToggle.setChecked(self.save_on_start)
        self.recController.softTriggerToggle.setChecked(self.software_trigger)
        self.settings = QSettings('labcams','labcams')
        try:
            self.restoreGeometry(self.settings.value("geometry", ""))
            self.restoreState(self.settings.value("windowState",""))
        except Exception as err:
            print(err)
            display("Could not restore locations")


    def set_experiment_name(self,expname):
        # Makes sure that the experiment name has the right slashes.
        if os.path.sep == '/':
            expname = expname.replace('\\',os.path.sep)
        expname = expname.strip(' ')
        for flg,cam in zip(self.saveflags,self.cams):
            if flg:
                cam.set_filename(expname)
        self.recController.experimentNameEdit.setText(expname)

    def server_reply(self,msg, msgtype = 'ok',address = None):
        if not self.zmqsocket is None:
            self.zmqsocket.send_pyobj(dict(action=msgtype,
                                           value = msg))
        if not self.udpsocket is None and not address is None:
            self.udpsocket.sendto('{0}={1}'.format(msgtype,msg).encode(),address)
                
    def server_actions(self): # all this should be moved to a class somewhere else.
        if not self.zmqsocket is None:
            try:
                message = self.zmqsocket.recv_pyobj(flags=zmq.NOBLOCK)
            except:
                return
        elif self.parameters['server'] == 'udp':
            try:
                msg,address = self.udpsocket.recvfrom(N_UDP)
            except:
                return
            msg = msg.decode().split('=')
            message = dict(action=msg[0])
            if len(msg) > 1:
                message = dict(message,value=msg[1])
            display('Server received message: {0}'.format(message))            
        if message['action'].lower() == 'expname':
            self.set_experiment_name(message['value'])
            self.server_reply(msg = message['action'].lower(),address = address)
        elif message['action'].lower() in ['softtrigger','software_trigger','settrigger','trigger']:
            self.recController.softTriggerToggle.setChecked(
                int(message['value']))
            self.server_reply(msg = 'trigger',address = address)
        elif message['action'].lower() == ['hardtrigger','hardware_trigger']:
            self.recController.camTriggerToggle.setChecked(
                int(message['value']))
            self.server_reply(msg = 'save_hardwaretrigger',address = address) 
        elif message['action'].lower() in ['save','setmanualsave','manualsave','acquire']:
            self.recController.saveOnStartToggle.setChecked(
                int(message['value']))
            self.server_reply(msg = 'save',address = address) 
        elif message['action'].lower() == 'log':
            for c in self.cams:
                c.cam.eventsQ.put('log={0}'.format(message['value']))
            self.recController.udpmessages.setText(message['value'])
            self.server_reply(msg = 'log',address = address) 
        elif message['action'].lower() == 'snapshot':
            foldername = message['value']
            if not os.path.exists(foldername):
                os.path.makedirs(foldername)
                display('Created {0}'.format(foldername))
            display('Getting snapshots to {0}'.format(foldername))
            update_shared_date()
            for icam,cam in enumerate(self.cams):
                frame = cam.get_img_with_virtual_channels()
                dataname = cam.recorder_parameters['dataname']
                fname = pjoin(os.path.dirname(foldername),'snapshots',
                              shared_date[:]+'_{0}.tif'.format(dataname))
                from tifffile import imsave
                if len(frame.shape) > 2:
                    frame = frame.transpose([2,0,1]).squeeze()
                    
                imsave(fname,
                       frame,
                       metadata = {
                           'Camera':str(icam)})
            self.server_reply(msg = 'snapshots',address = address)
        elif message['action'].lower() == 'startplugin':
            # starts a plugin remotely if not there yet.
            pluginname = message['value']
            loaded_plugins = [p.name for p in self.plugins]
            if pluginname in loaded_plugins:
                print('{0} plugin is already loaded. '.format(pluginname))
            else:
                for l in self.plugins_handles:
                    if pluginname == l['name']:
                        display('Loading {0}'.format(l['name']))
                        self.plugins.append(l['plugin'](self))
        elif message['action'].lower() == 'pluginmsg':
            for p in self.plugins:
                p.parse_command(message['value'])
                
        elif message['action'].lower() == 'load_reference':
            foldername = message['value']
            if not os.path.exists(foldername):
                display('No folder: {0}'.format(foldername))
                self.server_reply(msg = 'no_folder',msgtype = 'error',address = address) 
                return
            for icam,cam in enumerate(self.cams):
                files = glob(pjoin(foldername,'*_{0}.tif').format(
                    cam.recorder_parameters['dataname']))
                if len(files):
                    self.camwidgets[icam].toggle_reference(filename = files[0])
            self.server_reply(msg = 'load_reference',address = address)
        elif message['action'].lower() == 'hide_reference':
            for icam,cam in enumerate(self.cams):
                self.camwidgets[icam].toggle_reference(filename = '')
            self.server_reply(msg = 'hide_reference',address = address) 
        elif message['action'].lower() == 'ping':
            display('Server got PING.')
            self.server_reply(msg = 'pong',address = address) 
        elif message['action'].lower() == 'quit':
            self.udpsocket.sendto(b'ok=bye',address)
            self.server_reply(msg = 'bye',address = address) 
            self.close()

    def experiment_pluginmenu_trigger(self,q):
        for l in self.plugins_handles:
            if q.text() == l['name']:
                display('Loading {0}'.format(l['name']))
                self.plugins.append(l['plugin'](self))
    def experiment_menu_trigger(self,q):
        if q.text() == 'Set refresh time':
            self.timer.stop()
            res = QInputDialog().getDouble(self,"What refresh period do you want?","GUI refresh period",
                                           self.update_frequency)
            if res[1]:
                self.update_frequency = res[0]
            self.timer.start(self.update_frequency)
        
    def initUI(self):
        # Menu
        self.setDockOptions(QMainWindow.AllowTabbedDocks |
                            QMainWindow.AllowNestedDocks
)
        bar = self.menuBar()
        editmenu = bar.addMenu("Options")
        toggle_downsample = QActionCheckBox(self,'Downsample display',
                                            self.downsample_cameras)
        def tdownsample():
            self.downsample_cameras = not self.downsample_cameras
            toggle_downsample.checkbox.setChecked(self.downsample_cameras)
        toggle_downsample.link(tdownsample)
        editmenu.addAction(toggle_downsample)
        editmenu.addAction("Set refresh time")
        editmenu.triggered[QAction].connect(self.experiment_menu_trigger)
        pluginmenu = bar.addMenu("Plugins")
        from .plugins import load_plugins
        self.plugins_handles = load_plugins()
        for l in self.plugins_handles: 
             pluginmenu.addAction(l['name'])
             pluginmenu.triggered[QAction].connect(self.experiment_pluginmenu_trigger)
        self.setWindowTitle("labcams")
        self.tabs = []
        self.camwidgets = []
        self.recController = RecordingControlWidget(self)
        #self.setCentralWidget(self.recController)
        self.recControllerTab = QDockWidget("",self)
        self.recControllerTab.setObjectName("control_acquisition")
        self.recControllerTab.setWidget(self.recController)
        self.addDockWidget(
            Qt.TopDockWidgetArea,
            self.recControllerTab)
        self.recController.setFixedHeight(self.recController.layout.sizeHint().height())
        for c,cam in enumerate(self.cams):
            tt = ''
            if self.saveflags[c]:
                tt +=  ' - ' + self.cam_descriptions[c]['name'] +' ' 
            self.tabs.append(QDockWidget("Camera: "+str(c) + tt,self))
            self.tabs[-1].setObjectName("camera"+str(c))
            if hasattr(cam.cam,"h") and hasattr(cam.cam,"w"): # then it must be a camera
                self.camwidgets.append(CamWidget(frame = np.zeros((cam.cam.h.value,
                                                                   cam.cam.w.value,
                                                                   cam.cam.nchan.value),
                                                                  dtype=cam.cam.dtype),
                                                 iCam = c,
                                                 parent = self,
                                                 parameters = self.cam_descriptions[c]))
                self.camwidgets[-1].setMinimumHeight(300)

            else: # NIDAQ is the only other camera so add that widget
                self.camwidgets.append(DAQPlotWidget(daq = cam.cam,
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
            display('Initialized camera view: ' + str(c))
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(self.update_frequency)
        #self.move(0, 0)
        self.show()
            	
    def update_timer(self):
        for c,cam in enumerate(self.cams):
            self.camwidgets[c].update()
            try:
                pass
            except Exception as e:
                display('Could not draw cam: {0}'.format(c))
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(
                    exc_tb.tb_frame.f_code.co_filename)[1]
                print(e, fname, exc_tb.tb_lineno)
        for p in self.plugins:  # update plugins
            try:
                p.update()
            except Exception as err:
                display('Could not update plugin')
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(
                    exc_tb.tb_frame.f_code.co_filename)[1]
                print(e, fname, exc_tb.tb_lineno)
            
    def closeEvent(self,event):
        # try to save settings?
        
        self.settings.setValue('geometry',self.saveGeometry())
        self.settings.setValue('windowState',self.saveState())
        if hasattr(self,'server_timer'):
            self.server_timer.stop()
            if hasattr(self,'udpsocket') and not self.udpsocket is None:
                self.udpsocket.close()
        self.timer.stop()            
        display('Acquisition stopped (close event).')
        for cam in self.cams:
            cam.stop_acquisition()
        for cam in self.cams:
            cam.close()
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
                   hardware_trigger = opts.triggered)
    sys.exit(app.exec_())
    
if __name__ == '__main__':
    from multiprocessing import set_start_method
    set_start_method("spawn")
    main()
