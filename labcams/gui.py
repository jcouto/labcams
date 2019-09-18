import sys
import os
from .utils import display,getPreferences
from .cams import *
from .io import *
from .widgets import *
from multiprocessing import Queue,Event

class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, expName = 'test',
                 camDescriptions = [],
                 parameters = {},
                 server = True,
                 saveOnStart = False,
                 triggered = False,
                 updateFrequency = 50):
        super(LabCamsGUI,self).__init__()
        display('Starting labcams interface.')
        self.parameters = parameters
        self.app = app
        self.updateFrequency=updateFrequency
        self.saveOnStart = saveOnStart
        self.cam_descriptions = camDescriptions
        self.triggered = Event()
        if triggered:
            self.triggered.set()
        else:
            self.triggered.clear()
        # Init cameras
        camdrivers = [cam['driver'] for cam in camDescriptions]
        if 'AVT' in camdrivers:
            try:
                avtids,avtnames = AVT_get_ids()
            except Exception as e:
                display('AVT camera error? Connections? Parameters?')
                print(e)
        self.camQueues = []
        self.writers = []
        connected_avt_cams = []
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to camera [" + str(c) + '] : '+cam['name'])
            if not 'Save' in cam.keys():
                cam['Save'] = True
            if cam['driver'] == 'AVT':
                from .avt import AVTCam
                camids = [(camid,name) for (camid,name) in zip(avtids,avtnames) 
                          if cam['name'] in name]
                camids = [camid for camid in camids
                          if not camid[0] in connected_avt_cams]
                print(cam['name'])
                if len(camids) == 0:
                    display('Could not find or already connected to: '+cam['name'])
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
                self.camQueues.append(Queue())                
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
                                        nFrameBuffers = cam['nFrameBuffers']))
                connected_avt_cams.append(camids[0][0])
            elif cam['driver'] == 'QImaging':
                from .qimaging import QImagingCam
                self.camQueues.append(Queue())
                if not 'binning' in cam.keys():
                    cam['binning'] = 2
                self.cams.append(QImagingCam(camId=cam['id'],
                                             outQ = self.camQueues[-1],
                                             exposure=cam['exposure'],
                                             gain=cam['gain'],
                                             binning = cam['binning'],
                                             triggerType = cam['triggerType'],
                                             triggered = self.triggered))
            elif cam['driver'] == 'OpenCV':
                self.camQueues.append(Queue())
                self.cams.append(OpenCVCam(camId=cam['id'],
                                           outQ = self.camQueues[-1],
                                           triggered = self.triggered,
                                           **cam))
            elif cam['driver'] == 'PCO':
                from .pco import PCOCam
                self.camQueues.append(Queue())
                from .pixelfly import PCOCam
                self.cams.append(PCOCam(camId=cam['id'],
                                        binning = cam['binning'],
                                        exposure = cam['exposure'],
                                        outQ = self.camQueues[-1],
                                        triggered = self.triggered))
            else:
            	display('[WARNING] -----> Unknown camera driver' + cam['driver'])

            if cam['Save']:
                if not 'compress' in self.parameters:
                    self.parameters['compress'] = 0
                self.writers.append(TiffWriter(inQ = self.camQueues[-1],
                                               dataFolder=self.parameters['recorder_path'],
                                               framesPerFile=self.parameters['recorder_frames_per_file'],
                                               sleepTime = self.parameters['recorder_sleep_time'],
                                               compression = self.parameters['compress'],
                                               filename = expName,
                                               dataName = cam['description']))
            else:
                self.writers.append(None)
            # Print parameteres
            display('\t Camera: {0}'.format(cam['name']))
            for k in np.sort(list(cam.keys())):
                if not k == 'name':
                    display('\t\t - {0} {1}'.format(k,cam[k]))
            if cam['Save']:
                self.writers[-1].daemon = True
            self.cams[-1].daemon = True
#        self.resize(500,700)

        self.initUI()
        
        if server:
            import zmq
            self.zmqContext = zmq.Context()
            self.zmqSocket = self.zmqContext.socket(zmq.REP)
            self.zmqSocket.bind('tcp://0.0.0.0:{0}'.format(self.parameters['server_port']))
            display('Listening to port: {0}'.format(self.parameters['server_port']))
        self.camerasRunning = False
        for cam,writer in zip(self.cams,self.writers):
            cam.start()
            if not writer is None:
                writer.start()
        camready = 0
        while camready != len(self.cams):
            camready = np.sum([cam.camera_ready.is_set() for cam in self.cams])
        display('Initialized cameras.')
        self.zmqTimer = QTimer()
        self.zmqTimer.timeout.connect(self.zmqActions)
        self.zmqTimer.start(100)
        self.triggerCams(save=self.saveOnStart)

    def setExperimentName(self,expname):
        # Makes sure that the experiment name has the right slashes.
        if os.path.sep == '/':
            expname = expname.replace('\\',os.path.sep)
        for writer in self.writers:
            if not writer is None:
                writer.setFilename(expname)
        time.sleep(0.5)
        self.recController.experimentNameEdit.setText(expname)
        
    def zmqActions(self):
        import zmq
        try:
            message = self.zmqSocket.recv_pyobj(flags=zmq.NOBLOCK)
        except zmq.error.Again:
            return
        self.zmqSocket.send_pyobj(dict(action='handshake'))
        if message['action'] == 'expName':
            self.setExperimentName(message['value'])
        elif message['action'] == 'trigger':
            for cam in self.cams:
                cam.stop_acquisition()
            # make sure all cams closed
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                cam.saving.clear()
                if not writer is None:
                    writer.write.clear()
            self.triggerCams(save = True)

    def triggerCams(self,save=False):
        # stops previous saves if there were any
        display("Waiting for the cameras to be ready.")
        for c,cam in enumerate(self.cams):
            while not cam.camera_ready.is_set():
                time.sleep(0.02)
            display('Camera {{0}} ready.'.format(c))
        display('Doing save ({0}) and trigger'.format(save))
        if save:
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                if not writer is None:
                    cam.saving.set()
                    writer.write.set()
        else:
            for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
                if not writer is None:
                    cam.saving.clear()
                    writer.write.clear()
        #time.sleep(2)
        for c,cam in enumerate(self.cams):
            cam.start_trigger.set()
        display('Software triggered cameras.')
        
    def experimentMenuTrigger(self,q):
        display(q.text()+ "clicked. ")
        
    def initUI(self):
        # Menu
        self.setDockOptions(QMainWindow.AllowTabbedDocks |
                            QMainWindow.AllowNestedDocks
)
        from .widgets import CamWidget,RecordingControlWidget
        bar = self.menuBar()
        editmenu = bar.addMenu("Experiment")
        editmenu.addAction("New")
        editmenu.triggered[QAction].connect(self.experimentMenuTrigger)
        self.setWindowTitle("labcams")
        self.tabs = []
        self.camwidgets = []
        self.recController = RecordingControlWidget(self)
        self.setCentralWidget(self.recController)
        
        for c,cam in enumerate(self.cams):
            tt = ''
            if not self.writers[c] is None:
                tt +=  ' - ' + self.writers[c].dataName +' ' 
            self.tabs.append(QDockWidget("Camera: "+str(c) + tt,self))
            self.camwidgets.append(CamWidget(frame = np.zeros((cam.h,cam.w,cam.nchan),
                                                              dtype=cam.dtype),
                                             iCam = c,
                                             parent = self,
                                             parameters = self.cam_descriptions[c]))
            self.tabs[-1].setWidget(self.camwidgets[-1])
            self.tabs[-1].setFloating(False)
            self.tabs[-1].setAllowedAreas(Qt.LeftDockWidgetArea |
                                          Qt.LeftDockWidgetArea |
                                          Qt.BottomDockWidgetArea |
                                          Qt.TopDockWidgetArea)
            self.tabs[-1].setFeatures(QDockWidget.DockWidgetMovable |
                                      QDockWidget.DockWidgetFloatable)
            self.addDockWidget(
                Qt.LeftDockWidgetArea,
                self.tabs[-1])
            self.tabs[-1].setMinimumHeight(200)
            display('Init view: ' + str(c))

        self.timer = QTimer()
        self.timer.timeout.connect(self.timerUpdate)
        self.timer.start(self.updateFrequency)
        self.camframes = []
        for c,cam in enumerate(self.cams):
            self.camframes.append(cam.img)
        self.move(0, 0)
        self.show()
            	
    def timerUpdate(self):
        for c,(cam,frame) in enumerate(zip(self.cams,self.camframes)):
            try:
                self.camwidgets[c].image(frame,cam.nframes.value)
            except Exception as e:
                display('Could not draw cam: {0}'.format(c))
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(
                    exc_tb.tb_frame.f_code.co_filename)[1]
                print(e, fname, exc_tb.tb_lineno)
    def closeEvent(self,event):
        self.zmqTimer.stop()
        self.timer.stop()
        for cam in self.cams:
            cam.stop_acquisition()
        display('Acquisition stopped (close event).')
        for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
            if not writer is None:
                cam.saving.clear()
                writer.write.clear()
                writer.stop()
            cam.close()
        for c in self.cams:
            c.join()
        for c,(cam,writer) in enumerate(zip(self.cams,self.writers)):
            if not writer is None:
                display('   ' + self.cam_descriptions[c]['name']+
                        ' [ Acquired:'+
                        str(cam.nframes.value) + ' - Saved: ' + 
                        str(writer.frameCount.value) +']')
                writer.join()
        from .widgets import pg
        pg.setConfigOption('crashWarning', False)
        event.accept()


def main():
    from argparse import ArgumentParser
    import os
    import json
    
    parser = ArgumentParser(description='Script to control and record from cameras.')
    parser.add_argument('preffile',
                        metavar='configfile',
                        type=str,
                        default=None,
                        nargs="?")
    parser.add_argument('-d','--make-config',
                        type=str,
                        default = None,
                        action='store')
    parser.add_argument('--triggered',
                        default=False,
                        action='store_true')
    parser.add_argument('-c','--cam-select',
                        type=int,
                        nargs='+',
                        action='store')
    parser.add_argument('--no-server',
                        default=False,
                        action='store_true')
    parser.add_argument('-a','--analyse',
                        default=False,
                        action='store_true')
    parser.add_argument('--laps-trigger',
                        default=False,
                        action='store_true')
    parser.add_argument('--analysis-global-baseline',
                        default=False,
                        action='store_true')
    parser.add_argument('--analysis-df-f',
                        default=False,
                        action='store_true')
    opts = parser.parse_args()
    if not opts.make_config is None:
        fname = opts.make_config
        getPreferences(fname,create=True)
        sys.exit()
    parameters = getPreferences(opts.preffile)
    cams = parameters['cams']
    if not opts.cam_select is None:
        cams = [parameters['cams'][i] for i in opts.cam_select]

    if not opts.analyse:
        app = QApplication(sys.argv)
        w = LabCamsGUI(app = app,
                       camDescriptions = cams,
                       parameters = parameters,
                       server = not opts.no_server,
                       triggered = opts.triggered)
        sys.exit(app.exec_())
    else:
        app = QApplication(sys.argv)
        fname = os.path.abspath(str(QFileDialog.getExistingDirectory(None,"Select Directory of the run to process",
                                                     parameters['datapaths']['dataserverpaths'][0])))
        from .utils import cameraTimesFromVStimLog,findVStimLog
        from .io import parseCamLog,TiffStack
        from tqdm import tqdm
        import numpy as np
        from glob import glob
        import os
        from os.path import join as pjoin
        from pyvstim import parseVStimLog as parseVStimLog,parseProtocolFile,getStimuliTimesFromLog
        if not "linux" in sys.platform:
            fname = pjoin(*fname.split("/"))
        expname = fname.split(os.path.sep)[-2:]
        camlogext = '.camlog'
        camlogfile = glob(pjoin(fname,'*'+camlogext))
        if not len(camlogfile):
            display('Camera logfile not found in: {0}'.format(fname))
            import ipdb
            ipdb.set_trace()
            sys.exit()
        else:
            camlogfile = camlogfile[0]
        camlog = parseCamLog(camlogfile)[0]
        logfile = findVStimLog(expname)
        if not len(logfile):
            display('Could not find log file.')
            sys.exit()
        plog,pcomms = parseVStimLog(logfile)
        camidx = 3
        camlog = cameraTimesFromVStimLog(camlog,plog,camidx = camidx)
        camdata = TiffStack(fname)
        camtime = np.array(camlog['duinotime']/1000.)
        if not opts.laps_trigger:
            protopts,prot = parseProtocolFile(logfile.replace('.log','.prot'))
            (stimtimes,stimpars,stimoptions) = getStimuliTimesFromLog(
                logfile,plog)
            tpre = 0
            if 'BlankDuration' in protopts.keys():
                tpre = float(protopts['BlankDuration'])/2.
            stimavgs = triggeredAverage(
                camdata,camtime,
                stimtimes,
                tpre = tpre,
                global_baseline = opts.analysis_global_baseline,
                do_df_f = opts.analysis_df_f)
            # remove loops if there
            for iStim in range(len(stimavgs)):
                nloops = 0
                for p in prot.iloc[iStim]:
                    if isinstance(p, str):
                        if 'loop' in p:
                            nloops = int(p.strip(')').split(',')[-1])
                if nloops > 0:
                    display('Handling loops for stim {0}.'.format(iStim))
                    idx = np.where(stimavgs[iStim][:,0,0] >
                                   np.min(stimavgs[iStim][:,0,0]))[0]
                    looplen = int(np.ceil(np.shape(stimavgs[iStim][idx])
                                          [0]/nloops))
                    single_loop = np.zeros([looplen,
                                            stimavgs[iStim].shape[1],
                                            stimavgs[iStim].shape[2]],
                                           dtype = np.float32)
                    for nloop in range(nloops):
                        single_loop += stimavgs[iStim][
                            idx[0] + nloop*looplen : idx[0] +
                            (nloop+1)*looplen,:,:]
                    single_loop /= float(nloops)
                    stimavgs[iStim] = single_loop
            for iStim,savg in enumerate(stimavgs):
                fname = pjoin(parameters['datapaths']['dataserverpaths'][0],
                              parameters['datapaths']['analysispaths'],
                              expname[0],expname[1],'stimaverages_cam{0}'.format(camidx),
                              'stim{0}.tif'.format(iStim))
                if not os.path.isdir(os.path.dirname(fname)):
                    os.makedirs(os.path.dirname(fname))
                from tifffile import imsave
                display(fname)
                imsave(fname,savg)
        else:
            from pyvstim import treadmillBehaviorFromRelativePosition
            (behaviortime,position,
             displacement,velocity,
             laptimes) = treadmillBehaviorFromRelativePosition(
                 np.array(plog['position']['duinotime'])/1000.,
                 np.array(plog['position']['value']))
            from scipy.interpolate import interp1d

            npos = interp1d(behaviortime,position,
                            fill_value = "extrapolate",
                            bounds_error=False)(camtime)
            nvel = interp1d(behaviortime,velocity,
                            fill_value = 0,
                            bounds_error=False)(camtime)
            laps = np.vstack([laptimes[:-1],laptimes[1:]]).T

            stillframes = np.where(nvel*150. < 1.)[0]
            if not len(stillframes):
                display('Mouse was always running?')
                stillframes = np.arange(1000)
            display("There are {0} still frames.".format(len(stillframes)))
            if len(stillframes) > 1000:
                stillframes = stillframes[:1000]
            tmp = camdata[stillframes,:,:]
            baseline = np.nanmin(tmp.astype(np.float32),axis =0)
            #import pylab as plt
            #plt.imshow(baseline)
            #plt.show()
            display('Computing the lap maps for {0} laps.'.format(len(laps)))
            lapFrames = binFramesToLaps(laps,camtime,
                                        npos*150.,
                                        camdata,baseline = baseline)
            fname = pjoin(parameters['datapaths']['dataserverpaths'][0],
                          parameters['datapaths']['analysispaths'],
                          expname[0],expname[1],'stimaverages_cam{0}'.format(
                              camidx),
                          'lapFrames.tif')
            if not os.path.isdir(os.path.dirname(fname)):
                os.makedirs(os.path.dirname(fname))
            from tifffile import imsave
            imsave(fname,lapFrames)
            display('Saved {0}'.format(fname))
        sys.exit()
if __name__ == '__main__':
    main()
