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

VERSION = '0.6'

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
            self.extension = '.nan'
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
        if self.framesperfile > 0:
            if not '{nfiles}' in self.path_format:
                self.path_format += '_{nfiles}'

    def init(self,cam):
        ''' Sets camera specific variables - happens after camera load'''
        self.frame_rate = None
        if hasattr(cam,'frame_rate'):
            self.frame_rate = cam.frame_rate
        self.nchannels = 1
        if hasattr(cam,'nchan'):
            self.nchannels = cam.nchan

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

    def get_filename_path(self):
        self.path_keys['run'] = 'run{0:03d}'.format(self.runs)
        nfiles = self.nFiles
        self.path_keys['nfiles'] = '{0:08d}'.format(nfiles)
        self.path_keys['filename'] = self.get_filename()
        filename = (self.path_format+'{extension}').format(**self.path_keys)
        folder = os.path.dirname(filename)
        if folder == '':
            filename = pjoin(os.path.abspath(os.path.curdir),filename)
            folder = os.path.dirname(filename)
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except Exception as e:
                print("Could not create folder {0}".format(folder))
                print(e)
        return filename

    def open_file(self,nfiles = None,frame = None):
        filename = self.get_filename_path()
        if not self.fd is None:
            self.close_file()
        self._open_file(filename,frame)
        # Create a log file
        if self.logfile is None:
            self._open_logfile()
        self.nFiles += 1
        if hasattr(self,'parsed_filename'):
            filename = self.parsed_filename
        display('Opened: '+ filename)        
        self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + filename + '\n')

    def _open_logfile(self):
        #self.path_keys['run'] = 'run{0:03d}'.format(self.runs)
        #nfiles = self.nFiles
        #self.path_keys['nfiles'] = '{0:08d}'.format(nfiles)
        #self.path_keys['filename'] = self.get_filename()

        #filename = (self.path_format+'{extension}').format(**self.path_keys)
        filename = self.get_filename_path()
        logfname = filename.replace('{extension}'.format(
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
                display('[Recorder] Stopping the recorder.')
                self._stop_write()
            elif msg.startswith('#'):
                if self.logfile is None:
                    self._open_logfile()
                self.logfile.write(msg + '\n')
            return None,msg
        else:
            frame,(metadata) = buff
            if (self.fd is None or
                (self.framesperfile > 0 and np.mod(self.saved_frame_count,
                                                   self.framesperfile)==0)):
                self.open_file(frame = frame)
                if not self.inQ is None:
                    display('Queue size: {0}'.format(self.inQ.qsize()))

                    self.logfile.write('# [' + datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - '
                                       + 'Queue: {0}'.format(self.inQ.qsize())
                                       + '\n')
            frameid, timestamp = metadata[:2] 
            self._write(frame,frameid,timestamp)
            if np.mod(frameid,7000) == 0:
                if self.inQ is None:
                    display('[{0} - frame:{1}]'.format(
                        self.dataname,frameid))
                else:
                    display('[{0} - frame:{1}] Queue size: {2}'.format(
                        self.dataname,frameid,self.inQ.qsize()))
            self.logfile.write(','.join(['{0}'.format(a) for a in metadata]) + '\n')
            self.saved_frame_count += 1
        return frameid,frame
    
    def close_run(self):
        
        if not self.logfile is None:
            # Check if there are comments on the queue
            while not self.inQ.empty():
                buff = self.inQ.get()
                frameid,frame = self._handle_frame(buff)
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
            display('[Recorder] Closing the logfile {0}.'.format(self.dataname))
            self.runs += 1
        if not self.saved_frame_count == 0:
            display("[Recorder] Wrote {0} frames on {1} ({2} files).".format(
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
                               datafolder=datafolder,
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
                while self.inQ.qsize():
                    frameid,frame = self.get_from_queue_and_save()
                # spare the processor just in case...
                time.sleep(self.sleeptime)
            time.sleep(self.sleeptime)
            # If queue is not empty, empty if to disk.
            while self.inQ.qsize():
                frameid,frame = self.get_from_queue_and_save()
            #display('Queue is empty. Proceding with close.')
            # close the run
            self.close_run()
        
class TiffWriter(GenericWriterProcess):
    def __init__(self,
                 inQ = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'cam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=256,
                 sleeptime = 1./30,
                 incrementruns=True,
                 compression=None):
        self.extension = '.tif'
        super(TiffWriter,self).__init__(inQ = inQ,
                                        loggerQ=loggerQ,
                                        datafolder=datafolder,
                                        filename=filename,
                                        dataname=dataname,
                                        pathformat=pathformat,
                                        framesperfile=framesperfile,
                                        sleeptime=sleeptime,
                                        incrementruns=incrementruns)
        self.compression = None
        if not compression is None:
            if compression > 9:
                display('Can not use compression over 9 for the TiffWriter')
            elif compression > 0:
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
        self.extension = '_{nchannels}_{H}_{W}_{dtype}.dat'
        super(BinaryWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          datafolder=datafolder,
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
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        dtype = frame.dtype
        if dtype == np.float32:
            dtype='float32'
        elif dtype == np.uint8:
            dtype='uint8'
        else:
            dtype='uint16'
        filename = filename.format(nchannels = self.nchannels,
                                   W=self.w,
                                   H=self.h,
                                   dtype=dtype) 
        self.parsed_filename = filename
        self.fd = open(filename,'wb')
        
    def _write(self,frame,frameid,timestamp):
        self.fd.write(frame)
        if np.mod(frameid,5000) == 0: 
            display('Wrote frame id - {0}'.format(frameid))
        
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
                 incrementruns=True,
                 hwaccel = None,
                 frame_rate = None,
                 compression=17):
        self.extension = '.avi'
        super(FFMPEGWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          datafolder=datafolder,
                                          dataname=dataname,
                                          pathformat = pathformat,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns)
        self.compression = compression
        if frame_rate is None:
            frame_rate = 0
        if frame_rate <= 0:
            frame_rate = 30.
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
                if self.compression == 0:
                    display('Using compression 17 for the intel Media SDK encoder')
                    self.compression = 17
                self.doutputs = {'-format':'h264',
                                 '-pix_fmt':'yuv420p',#'gray',
                                 '-vcodec':'h264_qsv',#'libx264',
                                 '-global_quality':str(25), # specific to the qsv
                                 '-look_ahead':str(1),
                                 #preset='veryfast',#'ultrafast',
                                 '-threads':str(1),
                                 '-crf':str(self.compression)}
            elif hwaccel == 'nvidia':
                if self.compression == 0:
                    display('Using compression 25 for the NVIDIA encoder')
                    self.compression = 25
                self.doutputs = {'-vcodec':'h264_nvenc',
                                 '-pix_fmt':'yuv420p',
                                 '-cq:v':str(self.compression),
                                 '-threads':str(1),
                                 '-preset':'medium'}
        self.hwaccel = hwaccel
        
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        if frame is None:
            raise ValueError('[Recorder] Need to pass frame to open a file.')
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        if self.frame_rate is None:
            self.frame_rate = 0
        if self.frame_rate == 0:
            display('Using 30Hz frame rate for ffmpeg')
            self.frame_rate = 30
        
        self.doutputs['-r'] =str(self.frame_rate)
        self.dinputs = {'-r':str(self.frame_rate)}

        # does a check for the datatype, if uint16 then save compressed lossless
        if frame.dtype in [np.uint16] and len(frame.shape) == 2:
            self.fd = FFmpegWriter(filename.replace(self.extension,'.mov'),
                                   inputdict={'-pix_fmt':'gray16le',
                                              '-r':str(self.frame_rate)}, # this is important
                                   outputdict={'-c:v':'libopenjpeg',
                                               '-pix_fmt':'gray16le',
                                               '-r':str(self.frame_rate)})
        else:
            self.fd = FFmpegWriter(filename,
                                   inputdict=self.dinputs,
                                   outputdict=self.doutputs)
            
    def _write(self,frame,frameid,timestamp):
        self.fd.writeFrame(frame)

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
                 fourcc = 'X264'):
        self.extension = '.avi'
        super(OpenCVWriter,self).__init__(inQ = inQ,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          datafolder=datafolder,
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
                 inQ = None,
                 incrementruns=True,
                 compression=None,
                 hwaccel = None):
        self.extension = '.avi'
        self.cam = cam
        self.nchannels = cam.nchan

        super(FFMPEGCamWriter,self).__init__(filename=filename,
                                             datafolder=datafolder,
                                             dataname=dataname,
                                             pathformat = pathformat,
                                             framesperfile=framesperfile,
                                             incrementruns=incrementruns,
                                             inQ = inQ)

        self.compression = compression
        if self.compression is None:
            self.compression = 0
        frame_rate = cam.frame_rate
        if frame_rate is None:
            frame_rate = 0
        if frame_rate <= 0:
            frame_rate = 30.
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
                if self.compression == 0:
                    display('Using compression 17 for the intel Media SDK encoder')
                    self.compression = 17
                self.doutputs = {'-format':'h264',
                                 '-pix_fmt':'yuv420p',#'gray',
                                 '-vcodec':'h264_qsv',#'libx264',
                                 '-global_quality':str(25), # specific to the qsv
                                 '-look_ahead':str(1),
                                 #preset='veryfast',#'ultrafast',
                                 '-threads':str(1),
                                 '-crf':str(self.compression)}
            elif hwaccel == 'nvidia':
                if self.compression == 0:
                    display('Using compression 25 for the NVIDIA encoder')
                    self.compression = 25
                self.doutputs = {'-vcodec':'h264_nvenc',
                                 '-pix_fmt':'yuv420p',
                                 '-cq:v':str(self.compression),
                                 '-threads':str(1),
                                 '-preset':'medium'}
        self.hwaccel = hwaccel
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
            print("------->>> Closed file.")
        self.fd = None

    def _open_file(self,filename,frame = None):
        if frame is None:
            raise ValueError('[Recorder] Need to pass frame to open a file.')
        self.w = frame.shape[1]
        self.h = frame.shape[0]
        if self.frame_rate is None:
            self.frame_rate = 0
        if self.frame_rate == 0:
            display('Using 30Hz frame rate for ffmpeg')
            self.frame_rate = 30
        
        self.doutputs['-r'] =str(self.frame_rate)
        self.dinputs = {'-r':str(self.frame_rate)}

        # does a check for the datatype, if uint16 then save compressed lossless
        if frame.dtype in [np.uint16] and len(frame.shape) == 2:
            self.fd = FFmpegWriter(filename.replace(self.extension,'.mov'),
                                   inputdict={'-pix_fmt':'gray16le',
                                              '-r':str(self.frame_rate)}, # this is important
                                   outputdict={'-c:v':'libopenjpeg',
                                               '-pix_fmt':'gray16le',
                                               '-r':str(self.frame_rate)})
        else:
            self.fd = FFmpegWriter(filename,
                                   inputdict=self.dinputs,
                                   outputdict=self.doutputs)
            
    def _write(self,frame,frameid,timestamp):
        self.fd.writeFrame(frame)

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
                 inQ = None,
                 incrementruns=True):
        self.extension = '_{nchannels}_{H}_{W}_{dtype}.dat'
        self.cam = cam
        self.nchannels = cam.nchan
        super(BinaryCamWriter,self).__init__(filename=filename,
                                             datafolder=datafolder,
                                             dataname=dataname,
                                             inQ = inQ,
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
        dtype = frame.dtype
        if dtype == np.float32:
            dtype='float32'
        elif dtype == np.uint8:
            dtype='uint8'
        else:
            dtype='uint16'
        filename = filename.format(nchannels = self.nchannels,
                                   W=self.w,
                                   H=self.h, dtype=dtype)
        self.parsed_filename = filename
        self.fd = open(filename,'wb')

    def _write(self,frame,frameid,timestamp):
        self.fd.write(frame)
        
class TiffCamWriter(GenericWriter):
    def __init__(self,
                 cam,
                 filename = pjoin('dummy','run'),
                 dataname = 'cam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=256,
                 sleeptime = 1./300,
                 inQ = None,
                 incrementruns=True,
                 compression = None):
        self.extension = '.tif'
        self.cam = cam
        super(TiffCamWriter,self).__init__(datafolder=datafolder,
                                           filename=filename,
                                           inQ = inQ,
                                           dataname=dataname,
                                           pathformat=pathformat,
                                           framesperfile=framesperfile,
                                           sleeptime=sleeptime,
                                           incrementruns=incrementruns)
        self.compression = None
        if not compression is None:
            self.compression = np.clip(compression,0,9)
            
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
            print("------->>> Closed file.")
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.fd = twriter(filename)

    def _write(self,frame,frameid,timestamp):
        self.fd.save(frame,
                     compress=self.compression,
                     description='id:{0};timestamp:{1}'.format(frameid,timestamp))
        
################################################################################
################################################################################
################################################################################

def parseCamLog(fname, readTeensy = False):
    logheaderkey = '# Log header:'
    comments = []
    with open(fname,'r') as fd:
        for line in fd:
            if line.startswith('#'):
                line = line.strip('\n').strip('\r')
                comments.append(line)
                if line.startswith(logheaderkey):
                    columns = line.strip(logheaderkey).strip(' ').split(',')

    logdata = pd.read_csv(fname, 
                          delimiter=',',
                          header=None,
                          comment='#',
                          engine='c')
    col = [c for c in logdata.columns]
    for icol in range(len(col)):
        if icol <= len(columns)-1:
            col[icol] = columns[icol]
        else:
            col[icol] = 'var{0}'.format(icol)
    logdata.columns = col
    if readTeensy:
        # get the sync pulses and frames along with the LED
        def _convert(string):
            try:
                val = int(string)
            except ValueError as err:
                val = float(string)
            return val

        led = []
        sync= []
        ncomm = []
        for l in comments:
            if l.startswith('#LED:'):
                led.append([_convert(f) for f in  l.strip('#LED:').split(',')])
            elif l.startswith('#SYNC:'):
                sync.append([0.] + [_convert(f) for f in  l.strip('#SYNC:').split(',')])
            elif l.startswith('#SYNC1:'):
                sync.append([1.] + [_convert(f) for f in  l.strip('#SYNC1:').split(',')])
            else:
                ncomm.append(l)
        sync = pd.DataFrame(sync, columns=['sync','count','frame','timestamp'])
        led = pd.DataFrame(led, columns=['led','frame','timestamp'])
        return logdata,led,sync,ncomm
    return logdata,comments

parse_cam_log = parseCamLog

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

def mmap_dat(filename,
             mode = 'r',
             nframes = None,
             shape = None,
             dtype='uint16'):
    '''
    Loads frames from a binary file as a memory map.
    This is useful when the data does not fit to memory.
    
    Inputs:
        filename (str)       : fileformat convention, file ends in _NCHANNELS_H_W_DTYPE.dat
        mode (str)           : memory map access mode (default 'r')
                'r'   | Open existing file for reading only.
                'r+'  | Open existing file for reading and writing.                 
        nframes (int)        : number of frames to read (default is None: the entire file)
        shape (list|tuple)   : dimensions (NCHANNELS, HEIGHT, WIDTH) default is None
        dtype (str)          : datatype (default uint16) 
    Returns:
        A memory mapped  array with size (NFRAMES,[NCHANNELS,] HEIGHT, WIDTH).

    Example:
        dat = mmap_dat(filename)

    Joao Couto - from wfield
    '''
    
    if not os.path.isfile(filename):
        raise OSError('File {0} not found.'.format(filename))
    if shape is None or dtype is None: # try to get it from the filename
        meta = os.path.splitext(filename)[0].split('_')
        if shape is None:
            try: # Check if there are multiple channels
                shape = [int(m) for m in meta[-4:-1]]
            except ValueError:
                shape = [int(m) for m in meta[-3:-1]]
        if dtype is None:
            dtype = meta[-1]
    dt = np.dtype(dtype)
    if nframes is None:
        # Get the number of samples from the file size
        nframes = int(os.path.getsize(filename)/(np.prod(shape)*dt.itemsize))
    dt = np.dtype(dtype)
    return np.memmap(filename,
                     mode=mode,
                     dtype=dt,
                     shape = (int(nframes),*shape))


def stack_to_mj2_lossless(stack,fname, rate = 30):
    '''
    Compresses a uint16 stack with FFMPEG and libopenjpeg
    
    Inputs:
        stack                : array or memorymapped binary file
        fname                : output filename (will change extension to .mov)
        rate                 : rate of the mj2 movie [30 Hz default]

    Example:
       from labcams.io import * 
       fname = '20200710_140729_2_540_640_uint16.dat'
       stack = mmap_dat(fname)
       stack_to_mj2_lossless(stack,fname, rate = 30)
    '''
    ext = os.path.splitext(fname)[1]
    assert len(ext), "[mj2 conversion] Need to pass a filename {0}.".format(fname)
    
    if not ext == '.mov':
        print('[mj2 conversion] Changing extension to .mov')
        outfname = fname.replace(ext,'.mov')
    else:
        outfname = fname
    assert stack.dtype == np.uint16, "[mj2 conversion] This only works for uint16 for now."

    nstack = stack.reshape([-1,*stack.shape[2:]]) # flatten if needed    
    sq = FFmpegWriter(outfname, inputdict={'-pix_fmt':'gray16le',
                                              '-r':str(rate)}, # this is important
                      outputdict={'-c:v':'libopenjpeg',
                                  '-pix_fmt':'gray16le',
                                  '-r':str(rate)})
    from tqdm import tqdm
    for i,f in tqdm(enumerate(nstack),total=len(nstack)):
        sq.writeFrame(f)
    sq.close()
    
