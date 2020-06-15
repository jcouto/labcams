#! /usr/bin/env python
# Classes to save files from a multiprocessing queue
import time
import sys
from multiprocessing import Process,Queue,Event,Array,Value
from ctypes import c_long, c_char_p
from datetime import datetime
import time
import sys
from .utils import display
import numpy as np
import os
from glob import glob
from os.path import join as pjoin
from tifffile import imread, TiffFile
from tifffile import TiffWriter as twriter
import pandas as pd
from skvideo.io import FFmpegWriter
import cv2

VERSION = '0.5'

class GenericWriter(object):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=0,
                 sleeptime = 1./30,
                 incrementruns=True):
        if not hasattr(self,'extension'):
            self.extension = 'nan'
        self.saved_frame_count = 0
        self.runs = 0
        self.write = False
        self.close = False
        self.sleeptime = sleeptime # seconds
        self.framesperfile = framesperfile
        self.filename = ''
        self.datafolder = datafolder
        self.dataname = dataname
        self.foldername = None
        self.incrementruns = incrementruns
        self.fd = None
        self.inQ = inQ
        self.parQ = None
        self.today = datetime.today().strftime('%Y%m%d')
        self.logfile = None
        self.nFiles = 0
        runname = 'run{0:03d}'.format(self.runs)
        self.path_format = pathformat
        self.path_keys =  dict(datafolder=self.datafolder,
                               dataname=self.dataname,
                               filename=self.filename,
                               today = self.today,
                               run = runname,
                               nfiles = '{0:08d}'.format(0),
                               extension = self.extension)
    def _stop_write(self):
        self.write = False
    def stop(self):
        self.write = False
    def set_filename(self,filename):
        self._stop_write()
        self.filename = filename
        display('Filename updated: ' + self.get_filename())

    def get_filename(self):
        return str(self.filename[:]).strip(' ')

    def open_file(self,nfiles = None,frame = None):
        self.path_keys['run'] = 'run{0:03d}'.format(self.runs)
        nfiles = self.nFiles
        self.path_keys['nfiles'] = '{0:08d}'.format(nfiles)
        self.path_keys['filename'] = self.get_filename()

        filename = (self.path_format+'.{extension}').format(**self.path_keys)
        folder = os.path.dirname(filename)
        
        if not os.path.exists(folder):
            os.makedirs(folder)
        if not self.fd is None:
            self.close_file()
        self._open_file(filename,frame)
        # Create a log file
        if self.logfile is None:
            self._open_logfile()
        self.nFiles += 1
        display('Opened: '+ filename)        
        self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + filename + '\n')

    def _open_logfile(self):
        self.path_keys['run'] = 'run{0:03d}'.format(self.runs)
        nfiles = self.nFiles
        self.path_keys['nfiles'] = '{0:08d}'.format(nfiles)
        self.path_keys['filename'] = self.get_filename()

        filename = (self.path_format+'.{extension}').format(**self.path_keys)

        logfname = filename.replace('.{extension}'.format(
            **self.path_keys),'.camlog')
        self.logfile = open(logfname,'w')
        self.logfile.write('# Camera: {0} log file'.format(
            self.dataname) + '\n')
        self.logfile.write('# Date: {0}'.format(
            datetime.today().strftime('%d-%m-%Y')) + '\n')
        self.logfile.write('# labcams version: {0}'.format(
            VERSION) + '\n')                
        self.logfile.write('# Log header:' + 'frame_id,timestamp' + '\n')

    def _open_file(self,filename,frame):
        pass

    def _write(self,frame,frameid,timestamp):
        pass

    def save(self,frame,metadata):
        return self._handle_frame((frame,metadata))
    
    def _handle_frame(self,buff):
        if buff[0] is None:
            # Then parameters were passed to the queue
            display('[Writer] - Received None...')
            return None,None
        if len(buff) == 1:
           # check message:
            msg = buff[0]
            if msg in ['STOP']:
                display('Stopping writer.')
                self._stop_write()
            elif msg.startswith('#'):
                if self.logfile is None:
                    self._open_logfile()
                self.logfile.write(msg + '\n')
            return None,msg
        else:
            frame,(frameid,timestamp,) = buff
            if (self.fd is None or
                (self.framesperfile > 0 and np.mod(self.saved_frame_count,
                                                   self.framesperfile)==0)):
                self.open_file(frame = frame)
                if not self.inQ is None:
                    display('Queue size: {0}'.format(self.inQ.qsize()))

                    self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - '
                                       + 'Queue: {0}'.format(self.inQ.qsize())
                                       + '\n')
            self._write(frame,frameid,timestamp)
            
            if np.mod(frameid,7000) == 0:
                if self.inQ is None:
                    display('[{0} - frame:{1}]'.format(
                        self.dataname,frameid))
                else:
                    display('[{0} - frame:{1}] Queue size: {2}'.format(
                        self.dataname,frameid,self.inQ.qsize()))
            self.logfile.write('{0},{1}\n'.format(frameid,
                                                  timestamp))
            self.saved_frame_count += 1
        return frameid,frame
    
    def close_run(self):
        if not self.logfile is None:
            self.close_file()
            self.logfile.write('# [' +
                               datetime.today().strftime(
                                   '%y-%m-%d %H:%M:%S')+'] - ' +
                               "Wrote {0} frames on {1} ({2} files).".format(
                                   self.saved_frame_count,
                                   self.dataname,
                                   self.nFiles) + '\n')
            self.logfile.close()
            self.logfile = None
            self.runs += 1
        if not self.saved_frame_count == 0:
            display("Wrote {0} frames on {1} ({2} files).".format(
                self.saved_frame_count,
                self.dataname,
                self.nFiles))

class GenericWriterProcess(Process,GenericWriter):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=0,
                 sleeptime = 1./30,
                 incrementruns=True):
        GenericWriter.__init__(self,inQ = inQ,
                               loggerQ=loggerQ,
                               filename=filename,
                               dataname=dataname,
                               pathformat=pathformat,
                               framesperfile=framesperfile,
                               sleeptime=sleeptime,
                               incrementruns=incrementruns)
        Process.__init__(self)
        self.write = Event()
        self.close = Event()
        self.filename = Array('u',' ' * 1024)
        self.inQ = inQ
        self.parQ = Queue()
        self.daemon = True

    def _stop_write(self):
        self.write.clear()

    def set_filename(self,filename):
        self._stop_write()
        for i in range(len(self.filename)):
            self.filename[i] = ' '
        for i in range(len(filename)):
            self.filename[i] = filename[i]
        display('Filename updated: ' + self.get_filename())
    
    def stop(self):
        self._stop_write()
        self.close.set()
        self.join()
        
    def _write(self,frame,frameid,timestamp):
        pass
    
    def get_from_queue_and_save(self):
        buff = self.inQ.get()
        return self._handle_frame(buff)

    def run(self):
        while not self.close.is_set():
            self.saved_frame_count = 0
            self.nFiles = 0
            if not self.parQ.empty():
                self.getFromParQueue()
            while self.write.is_set() and not self.close.is_set():
                while not self.inQ.empty():
                    frameid,frame = self.get_from_queue_and_save()
                # spare the processor just in case...
                time.sleep(self.sleeptime)
            time.sleep(self.sleeptime)
        # If queue is not empty, empty if to disk.
        while not self.inQ.empty():
            frameid,frame = self.get_from_queue_and_save()
            display('Queue is empty. Proceding with close.')
        # close the run
        self.close_run()

'''
        if self.trackerFlag.is_set():
            # MPTRACKER hack
            display('Running eye tracker.')
            if self.tracker is None:
                import cv2
                cv2.setNumThreads(1)
                from mptracker import MPTracker
                self.tracker = MPTracker()
                self._updateTrackerPar()
            if self.trackerfile is None:
                self.trackerfile = pjoin(folder,
                                         '{0}_run{1:03d}.eyetracker'.format(
                                             self.today,
                                             self.runs.value))
                display('[TiffWriter] Started eye tracker storing dict.')
                self._trackerres = dict(ellipsePix = [],
                                        pupilPix = [],
                                        crPix = [])
        else:
            self.tracker = None
            self._close_trackerfile()

  RUN:
                    if not frameid is None and not self.tracker is None:
                        try:
                            res = self.tracker.apply(frame)
                        except Exception as e:
                            print(e)
                            res = ((0,0),(np.nan,np.nan),
                                   (np.nan,np.nan),
                                   (np.nan,np.nan,np.nan))
                        self._storeTrackerResults(res)

    def _close_trackerfile(self):
        if not self.trackerfile is None:
            from mptracker.io import exportResultsToHDF5
            self.tracker.parameters['points'] = self.tracker.ROIpoints
            if len(self.tracker.parameters['points']) < 4:
                (x1,y1,w,h) = self.tracker.parameters['imagecropidx']
                self.tracker.parameters['points'] = [[y1+h/2,0],
                                                     [0,x1+w/2],
                                                     [y1+h/2,x1+w],
                                                     [y1+h,x1+w/2]]
            self._trackerres = dict(
                ellipsePix = np.array(self._trackerres['ellipsePix']),
                pupilPix = np.array(self._trackerres['pupilPix']),
                crPix = np.array(self._trackerres['crPix']),
                reference  = [self.tracker.parameters['points'][0],
                              self.tracker.parameters['points'][2]])
            res = exportResultsToHDF5(self.trackerfile,
                                      self.tracker.parameters,
                                      self._trackerres)
            if not res is None:
                if res:
                    display('[TiffWriter] Saving tracker results to {0}'.format(self.trackerfile))
            else:
                display('[TiffWriter] Could not save tracker results to {0}'.format(self.trackerfile))
            self._trackerres = None
            self.trackerfile = None
            
    def _updateTrackerPar(self):
        if not self.trackerpar is None and not self.tracker is None:
            print('Updating eye tracker parameters.')
            for k in self.trackerpar.keys():
                self.tracker.parameters[k] = self.trackerpar[k]
                display('\t\t {0}: {1}'.format(k,self.trackerpar[k]))
            self.tracker.setROI(self.trackerpar['points'])

    def getFromParQueue(self):
        buff = self.parQ.get()
        if buff[0] is None:
            # Then parameters were passed to the queue
            display('[TiffWriter] - Received tracker parameters.')
            self.trackerpar = buff[1]
            self._updateTrackerPar()
        
    def _storeTrackerResults(self,res):
        cr_pos,pupil_pos,pupil_radius,pupil_ellipse_par = res
        self._trackerres['ellipsePix'].append(
            np.hstack([pupil_radius,pupil_ellipse_par]))
        self._trackerres['pupilPix'].append(pupil_pos)
        self._trackerres['crPix'].append(cr_pos)

        if not self.trackerfile is None:
            try:
                self._close_trackerfile()
            except Exception as err:
                display("There was an error when trying to save the tracker results.")
                print(err)


'''

        
class TiffWriter(GenericWriterProcess):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=256,
                 sleeptime = 1./30,
                 incrementruns=True,
                 compression=None):
        self.extension = 'tif'
        super(TiffWriter,self).__init__(inQ = inQ,
                                        loggerQ=loggerQ,
                                        filename=filename,
                                        dataname=dataname,
                                        pathformat=pathformat,
                                        framesperfile=framesperfile,
                                        sleeptime=sleeptime,
                                        incrementruns=incrementruns)
        self.compression = None
        if not compression is None:
            if compression > 0:
                self.compression = compression

        self.tracker = None
        self.trackerfile = None
        self.trackerFlag = Event()
        self.trackerpar = None

    def close_file(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.fd = twriter(filename)

    def _write(self,frame,frameid,timestamp):
        self.fd.save(frame,
                     compress=self.compression,
                     description='id:{0};timestamp:{1}'.format(frameid,
                                                               timestamp))

################################################################################
################################################################################
################################################################################
class BinaryWriter(GenericWriterProcess):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=0,
                 sleeptime = 1./300,
                 incrementruns=True):
        self.extension = '{wid}_{hei}.bin'
        super(BinaryWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          dataname=dataname,
                                          pathformat = pathformat,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns)
        self.w = None
        self.h = None
        self.buf = []
    def close_file(self):
        if not self.fd is None:
            if len(self.buf):
                self.fd.write(np.stack(self.buf))
                self.buf = []
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        filename = filename.format(wid=self.w,hei=self.h) 
        self.fd = open(filename,'wb')
    def _write(self,frame,frameid,timestamp):
        if len(self.buf) > 1000:
            self.fd.write(np.stack(self.buf))
            display('Wrote {0} frames - {1}'.format(len(self.buf),frameid))
            self.buf = [];
        self.buf.append(frame)

################################################################################
################################################################################
################################################################################
class FFMPEGWriter(GenericWriterProcess):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=0,
                 sleeptime = 1./30,
                 frame_rate = 30.,
                 incrementruns=True,
                 hwaccel = None,
                 compression=None):
        self.extension = 'avi'
        super(FFMPEGWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          dataname=dataname,
                                          pathformat = pathformat,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns)
        self.compression = 17
        if not compression is None:
            if compression > 0:
                self.compression = compression
        if frame_rate <= 0:
            frame_rate = 30.
            display('Using frame rate 30 (this value can be set with the frame_rate argument).')
        self.frame_rate = frame_rate
        self.w = None
        self.h = None
        if hwaccel is None:
            self.doutputs = {'-format':'h264',
                             '-pix_fmt':'gray',
                             '-vcodec':'libx264',
                             '-threads':str(10),
                             '-crf':str(self.compression)}
        else:            
            if hwaccel == 'intel':
                self.doutputs = {'-format':'h264',
                                 '-pix_fmt':'yuv420p',#'gray',
                                 '-vcodec':'h264_qsv',#'libx264',
                                 '-global_quality':str(25), # specific to the qsv
                                 '-look_ahead':str(1), 
                                 #preset='veryfast',#'ultrafast',
                                 '-threads':str(1),
                                 '-crf':str(self.compression)}
            elif hwaccel == 'nvidia':
                self.doutputs = {'-vcodec':'h264_nvenc',
                                 '-pix_fmt':'yuv420p',
                                 '-cq:v':'19',
                                 '-preset':'fast'}
        self.doutputs['-r'] =str(self.frame_rate)
        self.hwaccel = hwaccel
        
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        self.fd = FFmpegWriter(filename,
                               outputdict=self.doutputs)

    def _write(self,frame,frameid,timestamp):
        self.fd.writeFrame(frame)

################################################################################
################################################################################
class FFMPEGWriter_legacy(GenericWriterProcess):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=0,
                 hwaccel='nvidia',
                 sleeptime = 1./30,
                 frame_rate = 30.,
                 incrementruns=True,
                 compression=None):
        '''This version wasnt closing files.'''
        self.extension = 'avi'
        super(FFMPEGWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          dataname=dataname,
                                          pathformat=pathformat,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns)
        self.compression = 17
        if not compression is None:
            if compression > 0:
                self.compression = compression
        if frame_rate <= 0:
            frame_rate = 30.
            display('Using frame rate 30 (this value can be set with the frame_rate argument).')
        self.frame_rate = frame_rate
        self.dinputs = dict(format='rawvideo',
                            pix_fmt='gray',
                            s='{}x{}')
        self.w = None
        self.h = None
        if hwaccel == 'intel':
            self.doutputs = {'format':'h264',
                             'pix_fmt':'yuv420p',#'gray',
                             'vcodec':'h264_qsv',#'libx264',
                             'global_quality':str(25), # specific to the qsv
                             'look_ahead':str(1), 
                             #preset='veryfast',#'ultrafast',
                             'threads':str(1),
                             'crf':str(self.compression)}
        elif hwaccel == 'nvidia':
            self.doutputs = {'vcodec':'h264_nvenc',
                             'pix_fmt':'yuv420p',
                             'cq:v':19,
                             'preset':'fast'}
        self.doutputs['r'] =str(self.frame_rate)

    def close_file(self):
        if not self.fd is None:
            self.fd.stdin.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        indict = dict(**self.dinputs)
        if len(frame.shape)> 2:
            indict['pix_fmt'] = 'bgr24'
        indict['s'] = indict['s'].format(self.w,self.h)
        import ffmpeg
        self.fd = (ffmpeg
                   .input('pipe:',**indict)
                   .output(filename,**self.doutputs)
                   .overwrite_output()
                   .run_async(pipe_stdin=True))

    def _write(self,frame,frameid,timestamp):
        self.fd.stdin.write(frame.tobytes())

################################################################################
################################################################################
################################################################################
class OpenCVWriter(GenericWriter):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=0,
                 sleeptime = 1./30,
                 incrementruns=True,
                 compression=None,
                 frame_rate = 30.,
                 fourcc = 'X264'):
        self.extension = 'avi'
        super(OpenCVWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          pathformat = pathformat,
                                          dataname=dataname,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns)
        cv2.setNumThreads(6)
        self.compression = 17
        if not compression is None:
            if compression > 0:
                self.compression = compression
        self.fourcc = cv2.VideoWriter_fourcc(*fourcc)
        self.w = None
        self.h = None
        
    def close_file(self):
        if not self.fd is None:
            self.fd.release()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        self.isColor = False
        if len(frame.shape) < 2:
            self.isColor = True
        self.fd = cv2.VideoWriter(filename,
                                  cv2.CAP_FFMPEG,#cv2.CAP_DSHOW,#cv2.CAP_INTEL_MFX,
                                  self.fourcc,120,(self.w,self.h),self.isColor)

    def _write(self,frame,frameid,timestamp):
        if len(frame.shape) < 2:
            frame = cv2.cvtColor(frame,cv2.COLOR_GRAY2RGB)
        self.fd.write(frame)

        
################################################################################
################################################################################
################################################################################

class FFMPEGCamWriter(GenericWriter):
    def __init__(self,
                 cam,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=0,
                 incrementruns=True,
                 crf=None):
        self.extension = 'avi'
        super(FFMPEGCamWriter,self).__init__(cam=cam,
                                             filename=filename,
                                             dataname=dataname,
                                             pathformat = pathformat,
                                             framesperfile=framesperfile,
                                             incrementruns=incrementruns)
        self.crf = 17
        if not crf is None:
            if crf > 0:
                self.crf = crf
        self.dinputs = dict(format='rawvideo',
                            pix_fmt='gray',
                            s='{}x{}')
        self.w = None
        self.h = None
        
    def close_file(self):
        if not self.fd is None:
            self.fd.stdin.close()
            self.fd.wait()
            print("------->>> Closed file.")
        self.fd = None

    def _open_file(self,filename,frame):
        self.doutputs = dict(format='h264',
                             pix_fmt='nv12',#'yuv420p',#'gray',
                             vcodec='h264_qsv',#'libx264',
                             global_quality=17,
                             look_ahead=1, 
                             #preset='veryfast',#'ultrafast',
                             threads = 1,
                             r = self.cam.frame_rate,
                             crf=self.crf)
        self.w = self.cam.w
        self.h = self.cam.h
        self.nchan = self.cam.nchan
        indict = dict(**self.dinputs)
        if self.nchan> 2:
            indict['pix_fmt'] = 'bgr24'
        indict['s'] = indict['s'].format(self.w,self.h)
        self.fd = (ffmpeg
                   .input('pipe:',**indict)
                   .output(filename,**self.doutputs)
                   .overwrite_output()
                   .run_async(pipe_stdin=True))

    def _write(self,frame,frameid,timestamp):
        self.fd.stdin.write(frame.tobytes())

################################################################################
################################################################################
################################################################################

class BinaryCamWriter(GenericWriter):
    def __init__(self,
                 cam,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=0,
                 incrementruns=True):
        self.extension = '{hei}_{wid}.bin'
        self.cam = cam
        super(BinaryCamWriter,self).__init__(filename=filename,
                                             dataname=dataname,
                                             pathformat = pathformat,
                                             framesperfile=framesperfile,
                                             incrementruns=incrementruns)
        self.w = None
        self.h = None

    def close_file(self):
        if not self.fd is None:
            self.fd.close()
            print("------->>> Closed file.")
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        filename = filename.format(wid=self.w,hei=self.h) 
        self.fd = open(filename,'wb')

    def _write(self,frame,frameid,timestamp):
        self.fd.write(frame)
        
        
################################################################################
################################################################################
################################################################################

def parseCamLog(fname,convertToSeconds = True):
    logheaderkey = '# Log header:'
    comments = []
    with open(fname,'r') as fd:
        for line in fd:
            if line.startswith('#'):
                line = line.strip('\n').strip('\r')
                comments.append(line)
                if line.startswith(logheaderkey):
                    columns = line.strip(logheaderkey).strip(' ').split(',')

    logdata = pd.read_csv(fname,names = columns, 
                          delimiter=',',
                          header=None,
                          comment='#',
                          engine='c')
    if convertToSeconds or '1photon' in comments[0]:
        logdata['timestamp'] /= 10000.
    return logdata,comments


class TiffStack(object):
    def __init__(self,filenames):
        if type(filenames) is str:
            filenames = np.sort(glob(pjoin(filenames,'*.tif')))
        
        assert type(filenames) in [list,np.ndarray], 'Pass a list of filenames.'
        self.filenames = filenames
        for f in filenames:
            assert os.path.exists(f), f + ' not found.'
        # Get an estimate by opening only the first and last files
        framesPerFile = []
        self.files = []
        for i,fn in enumerate(self.filenames):
            if i == 0 or i == len(self.filenames)-1:
                self.files.append(TiffFile(fn))
            else:
                self.files.append(None)                
            f = self.files[-1]
            if i == 0:
                dims = f.series[0].shape
                self.shape = dims
            elif i == len(self.filenames)-1:
                dims = f.series[0].shape
            framesPerFile.append(np.int64(dims[0]))
        self.framesPerFile = np.array(framesPerFile, dtype=np.int64)
        self.framesOffset = np.hstack([0,np.cumsum(self.framesPerFile[:-1])])
        self.nFrames = np.sum(framesPerFile)
        self.curfile = 0
        self.curstack = self.files[self.curfile].asarray()
        N,self.h,self.w = self.curstack.shape[:3]
        self.dtype = self.curstack.dtype
        self.shape = (self.nFrames,self.shape[1],self.shape[2])
    def getFrameIndex(self,frame):
        '''Computes the frame index from multipage tiff files.'''
        fileidx = np.where(self.framesOffset <= frame)[0][-1]
        return fileidx,frame - self.framesOffset[fileidx]
    def __getitem__(self,*args):
        index  = args[0]
        if not type(index) is int:
            Z, X, Y = index
            if type(Z) is slice:
                index = range(Z.start, Z.stop, Z.step)
            else:
                index = Z
        else:
            index = [index]
        img = np.empty((len(index),self.h,self.w),dtype = self.dtype)
        for i,ind in enumerate(index):
            img[i,:,:] = self.getFrame(ind)
        return np.squeeze(img)
    def getFrame(self,frame):
        ''' Returns a single frame from the stack '''
        fileidx,frameidx = self.getFrameIndex(frame)
        if not fileidx == self.curfile:
            if self.files[fileidx] is None:
                self.files[fileidx] = TiffFile(self.filenames[fileidx])
            self.curstack = self.files[fileidx].asarray()
            self.curfile = fileidx
        return self.curstack[frameidx,:,:]
    def __len__(self):
        return self.nFrames
