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
from .utils import *
from multiprocessing import Process,Queue,Event,Array,Value
from multiprocessing.shared_memory import SharedMemory # this breaks compatibility with python < 3.8
from ctypes import c_long, c_char_p, c_wchar
import ctypes
from datetime import datetime
import time
import sys
from .utils import display,shared_date
import numpy as np
import os
from glob import glob
from os.path import join as pjoin
from tifffile import imread, TiffFile
from tifffile import TiffWriter as twriter
import pandas as pd
from skvideo.io import FFmpegWriter
import cv2

# TODO: check if ffmpeg is working when initializing and using the ffmpeg writer.
VERSION = '0.7'

class GenericWriter(object):
    def __init__(self,
                 cam = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=0,
                 sleeptime = 1./30,
                 virtual_channels = None,
                 incrementruns=True,
                 **kwargs):
        if not hasattr(self,'extension'):
            self.extension = '.nan'
        self.cam = None
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
        self.parQ = None
        self.today = datetime.today().strftime('%Y%m%d')
        self.nchannels = Value('i',1)
        self.logfile = None
        self.nFiles = 0
        runname = 'run{0:03d}'.format(self.runs)
        self.virtual_channels = virtual_channels
        if self.virtual_channels is None:
            self.virtual_channels = Value('i',0)

        self.path_format = pathformat
        self.path_keys =  dict(datafolder = self.datafolder,
                               dataname = self.dataname,
                               filename = self.filename,
                               today = self.today,
                               datetime = shared_date[:],
                               year = shared_date[:4],
                               month = shared_date[4:6],
                               day = shared_date[6:8],
                               hours = shared_date[9:11],
                               minutes = shared_date[11:13],
                               seconds = shared_date[13:],
                               run = runname,
                               nfiles = '{0:08d}'.format(0),
                               extension = self.extension,
                               **kwargs)
        if self.framesperfile > 0:
            if not '{nfiles}' in self.path_format:
                self.path_format += '_{nfiles}'
        if not cam is None:
            self.init_cam(cam)
            
    def init_cam(self,cam):
        ''' Sets camera specific variables - happens after camera load'''
        if not hasattr(cam,'membuffer_name'):
            return
        self.frame_rate = None
        if self.cam is None:
            self.cam = dict(buffer_name = cam.membuffer_name,
                            buffer_len = cam.membuffer_len,
                            queue = cam.queue,
                            dtype = cam.dtype,
                            h = cam.h,
                            w = cam.w,
                            nchannels = cam.nchan,
                            frame_rate = cam.fs)
            self.inQ = self.cam['queue']
        if hasattr(cam,'frame_rate'):
            self.frame_rate = cam.fs.value
        self.nchannels = self.cam['nchannels']
        self.h = self.cam['h']
        self.w = self.cam['w']
        if self.virtual_channels.value == 0:    # to set the filename in the binary file for instance.
            self.virtual_channels.value = self.nchannels.value
        
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
        self.path_keys['datetime'] = shared_date[:]
        self.path_keys['year'] = shared_date[:4]
        self.path_keys['month'] = shared_date[4:6]
        self.path_keys['day'] = shared_date[6:8]
        self.path_keys['hours'] = shared_date[9:11]
        self.path_keys['minutes'] = shared_date[11:13]
        self.path_keys['seconds'] = shared_date[13:]
        
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
        
        self.logfile = open(logfname,'w',encoding = 'utf-8')
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
            display('[Recorder] - Received None...')
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
                 cam = None,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=0,
                 sleeptime = 1./30,
                 virtual_channels = None,
                 incrementruns=True,
                 save_trigger = None,
                 **kwargs):
        GenericWriter.__init__(self,
                               cam = cam,
                               loggerQ=loggerQ,
                               filename=filename,
                               datafolder=datafolder,
                               dataname=dataname,
                               virtual_channels = virtual_channels,
                               pathformat=pathformat,
                               framesperfile=framesperfile,
                               sleeptime=sleeptime,
                               incrementruns=incrementruns,
                               **kwargs)
        Process.__init__(self)
        self.write = save_trigger
        if self.write is None:
            self.write = Event()
        self.close = Event()
        self.filename = Array('u',' ' * 1024)
        self.parQ = Queue(MAX_QUEUE_SIZE)
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
        qsize = self.inQ.qsize()
        if qsize > 1000:
            display('[{0}] Queue size: {1}'.format(
                self.dataname,qsize))
            while not self.inQ.empty():
                self.inQ.get()
            display('######################################## ISSUE RECORDING. FRAME COUNT ON QUEUE TOO HIGH. DROPPING FRAMES. #########################')
            display('########################################          THIS IS NOT NORMAL, CHECK THE SETTINGS.              #########################')
            if not self.logfile is None:
                self.logfile.write('# ISSUE RECORDING. FRAME COUNT ON QUEUE TOO HIGH. DROPPING FRAMES.')
                self.logfile.write('# THIS IS NOT NORMAL, CHECK THE INSTALATION.')
        buf = None
        if not buff[0] is None:
            if len(buff) > 1:
                buf = self.get_frame(buff[0])
                buff = [buf, *buff[1:]]
        return self._handle_frame(buff)

    def _init_shared_mem(self):
        dtype = self.cam['dtype']
        try:
            dtype = dtype()
        except:
            pass
        if not hasattr(self,'membuffer'):
            self.membuffer = SharedMemory(name = self.cam['buffer_name'])
        buffsize = [self.h.value,self.w.value,self.nchannels.value]
        self.nbuffers = int(self.cam['buffer_len'] // np.prod(buffsize+[dtype.itemsize]))
        buffsize = [self.nbuffers] + buffsize
        self.imgs = np.ndarray(buffsize,
                               buffer = self.membuffer.buf,
                               dtype = dtype)

    def get_frame(self,frame_index = None):
        if frame_index is None:
            frame_index = self.nframes.value
        return self.imgs[frame_index % self.nbuffers].squeeze()
        
    def run(self):
        while not self.close.is_set():
            self.saved_frame_count = 0
            self.nFiles = 0
            if not self.parQ.empty():
                self.getFromParQueue()
            self._init_shared_mem()
            while self.write.is_set() and not self.close.is_set():
                while self.inQ.qsize() > 0:
                    frameid,frame = self.get_from_queue_and_save()
                # spare the processor just in case...
                time.sleep(self.sleeptime)
            time.sleep(self.sleeptime)
            # If queue is not empty, empty if to disk.
            while self.inQ.qsize() > 0:
                frameid,frame = self.get_from_queue_and_save()
            #display('Queue is empty. Proceding with close.')
            # close the run
            self.close_run()
        
class TiffWriter(GenericWriterProcess):
    def __init__(self,
                 cam,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'cam',
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 framesperfile=256,
                 sleeptime = 1./30,
                 incrementruns=True,
                 compression=None,
                 **kwargs):
        self.extension = '.tif'
        super(TiffWriter,self).__init__(cam = cam,
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
                 cam,
                 loggerQ = None,
                 filename = pjoin('dummy','run'),
                 dataname = 'eyecam',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 framesperfile=0,
                 sleeptime = 1./300,
                 virtual_channels = None,
                 incrementruns=True,**kwargs):
        self.extension = '_{nchannels}_{H}_{W}_{dtype}.dat'
        super(BinaryWriter,self).__init__(cam = cam,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          datafolder=datafolder,
                                          dataname=dataname,
                                          pathformat = pathformat,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          virtual_channels = virtual_channels,
                                          incrementruns=incrementruns,
                                          **kwargs)
        self.buf = []
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        dtype = frame.dtype
        if dtype == np.float32:
            dtype='float32'
        elif dtype == np.uint8:
            dtype='uint8'
        else:
            dtype='uint16'
        filename = filename.format(nchannels = self.virtual_channels.value,
                                   W=self.w.value,
                                   H=self.h.value,
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
nvenc_presets = {0:'default (medium)',
                 1:'slow',
                 2:'medium',
                 3:'fast',
                 4:'hp',
                 5:'hq',
                 6:'bd',
                 8:'llhq',
                 9:'llhp',
                 10:'lossless',
                 11:'losslesshp'}
class FFMPEGWriter(GenericWriterProcess):
    def __init__(self,
                 cam,
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
                 preset = None,
                 compression=None,
                 bitrate = '5M',
                 **kwargs):
        self.extension = '.avi'
        super(FFMPEGWriter,self).__init__(cam = cam,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          datafolder=datafolder,
                                          dataname=dataname,
                                          pathformat = pathformat,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns,
                                          **kwargs)
        self.compression = compression
        if self.compression is None:
            self.compression = 0
        if type(preset) == str:
            preset =[nvenc_presets[k] for k in  nvenc_presets.keys()].index(preset)
        self.preset = preset
        if hwaccel is None:
            if self.compression == 0:
                self.compression = 25
            self.doutputs = {'-format':'h264',
                             '-pix_fmt':'gray',
                             '-vcodec':'libx264',
                             '-threads':str(10),
                             '-crf':str(self.compression)}
        else:            
            if hwaccel == 'intel':
                if self.compression == 0:
                    self.compression = 25
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
                                 '-tune': 'hq',
                                 '-qmin': '0',
                                 '-g': '250',
                                 '-bf': '3',
                                 '-b_ref_mode':'middle',
                                 '-temporal-aq': '1',
                                 '-rc-lookahead':'20',
                                 '-i_qfactor': '0.75',
                                 '-b_qfactor': '1.1',
                                 '-maxrate':'25M',
                                 '-b:v':bitrate,
                                 '-threads':str(1)}
                preset = 'NA'
                if not self.preset is None:
                    print('Using preset for compression')
                    self.doutputs['-preset'] = str(self.preset)
                    preset = nvenc_presets[self.preset]

                if not self.compression is None:
                    comp = self.compression
                    if type(self.compression) is str:
                        if ':' in self.compression: # then parse the bitrate
                            comp = self.compression.split(':')
                        else:
                            comp = [str(self.compression)]
                        self.compression = comp[0]
                        self.doutputs['-cq:v'] = comp[0]
                        #self.doutputs['-rc:v'] = 'vbr_hq'
                        if len(comp)>1:
                            self.doutputs['-b:v'] = comp[1]
                            bitrate = comp[1]
        self.hwaccel = hwaccel
        display('[FFMPEG] - Using compression (preset {0}) {1}  - bitrate {3} for the {2} encoder.'.format(
            preset,
            self.compression,
            hwaccel,
            bitrate))
        
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
        self.fd = None

    def _open_file(self,filename,frame = None):
        if frame is None:
            raise ValueError('[Recorder] Need to pass frame to open a file.')
        self.frame_rate = self.cam['frame_rate'].value
        if self.frame_rate is None or self.frame_rate == 0:
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
            return
        elif len(frame.shape) == 3 and (frame.shape[-1] == 3):
            self.doutputs['-pix_fmt'] = 'yuv420p'
            display('Camera has 3 channels; recording in yuv420p.')
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
                 cam,
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
                 fourcc = 'X264',**kwargs):
        self.extension = '.avi'
        super(OpenCVWriter,self).__init__(cam = cam,
                                          loggerQ=loggerQ,
                                          filename=filename,
                                          datafolder=datafolder,
                                          pathformat = pathformat,
                                          dataname=dataname,
                                          framesperfile=framesperfile,
                                          sleeptime=sleeptime,
                                          incrementruns=incrementruns,
                                          **kwargs)
        cv2.setNumThreads(6)
        self.compression = 17
        if not compression is None:
            if compression > 0:
                self.compression = compression
        self.fourcc = cv2.VideoWriter_fourcc(*fourcc)
        
    def close_file(self):
        if not self.fd is None:
            self.fd.release()
        self.fd = None

    def _open_file(self,filename,frame = None):
        self.isColor = False
        if len(frame.shape) < 2:
            self.isColor = True
        self.fd = cv2.VideoWriter(filename,
                                  cv2.CAP_FFMPEG,#cv2.CAP_DSHOW,#cv2.CAP_INTEL_MFX,
                                  self.fourcc,120,(self.w.value,self.h.value),self.isColor)

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
                 compression=None,
                 hwaccel = None,**kwargs):
        self.extension = '.avi'
        self.nchannels = cam.nchan

        super(FFMPEGCamWriter,self).__init__(cam = cam,
                                             filename=filename,
                                             datafolder=datafolder,
                                             dataname=dataname,
                                             pathformat = pathformat,
                                             framesperfile=framesperfile,
                                             incrementruns=incrementruns,
                                             **kwargs)

        self.compression = compression
        if self.compression is None:
            self.compression = 0
        if hwaccel is None:
            self.doutputs = {'-format':'h264',
                             '-pix_fmt':'gray',
                             '-vcodec':'libx264',
                             '-threads':str(10),
                             '-crf':str(self.compression)}
        else:            
            if hwaccel == 'intel':
                if self.compression == 0:
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
                    self.compression = 25
                self.doutputs = {'-vcodec':'h264_nvenc',
                                 '-pix_fmt':'yuv420p',
                                 #'-cq:v':str(self.compression),
                                 '-threads':str(1),
                                 '-preset':str(self.compression)}
        self.hwaccel = hwaccel
        display('Using compression {0} for the {1} FFMPEG encoder.'.format(
            self.compression, hwaccel))

    def close_file(self):
        if not self.fd is None:
            self.fd.close()
            print("------->>> Closed file.")
        self.fd = None

    def _open_file(self,filename,frame = None):
        if frame is None:
            raise ValueError('[Recorder] Need to pass frame to open a file.')
        self.frame_rate = self.cam['frame_rate'].value
        if self.frame_rate is None or self.frame_rate == 0:
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
                 virtual_channels = None,
                 incrementruns=True,**kwargs):
        self.extension = '_{nchannels}_{H}_{W}_{dtype}.dat'
        super(BinaryCamWriter,self).__init__(cam = cam,
                                             filename=filename,
                                             datafolder=datafolder,
                                             dataname=dataname,
                                             pathformat = pathformat,
                                             virtual_channels = virtual_channels,
                                             framesperfile=framesperfile,
                                             incrementruns=incrementruns,
                                             **kwargs)                

    def close_file(self):
        if not self.fd is None:
            self.fd.close()
            print("------->>> Closed file.")
        self.fd = None

    def _open_file(self,filename,frame = None):
        dtype = frame.dtype
        if dtype == np.float32:
            dtype='float32'
        elif dtype == np.uint8:
            dtype='uint8'
        else:
            dtype='uint16'
        filename = filename.format(nchannels = self.virtual_channels.value,
                                   W=self.w.value,
                                   H=self.h.value, dtype=dtype)
        self.parsed_filename = filename
        self.fd = open(filename,'wb')

    def _write(self,frame,frameid,timestamp):
        self.fd.write(frame)

class BinaryDAQWriter(GenericWriter):
    def __init__(self,
                 daq,
                 filename = pjoin('dummy','run'),
                 dataname = 'daq',
                 datafolder=pjoin(os.path.expanduser('~'),'data'),
                 pathformat = pjoin('{datafolder}','{dataname}','{filename}',
                                    '{today}_{run}_{nfiles}'),
                 incrementruns=True,**kwargs):
        self.extension = '_{nchannels}_{dtype}.nidq.bin'
        self.daq = daq
        super(BinaryDAQWriter,self).__init__(cam = daq,
                                             filename=filename,
                                             datafolder=datafolder,
                                             dataname=dataname,
                                             pathformat = pathformat,
                                             framesperfile=-1,
                                             incrementruns=incrementruns,
                                             **kwargs)
        self.nchannels = daq.ai_num_channels + daq.di_num_channels
        self.nbytes = 0
    def close_file(self):
        if not self.fd is None:
            self.fd.close()
            print("------->>> Closed nidq.bin file.")
            # create the metadata:
            with open(self.parsed_filename.replace('.bin','.meta'),'w') as f:
                f.write('fileSizeBytes={0}\n'.format(self.nbytes))
                f.write('fileTimeSecs={0}\n'.format(self.nsamples/self.daq.srate))
                f.write('niSampRate={0}\n'.format(self.daq.srate))
                f.write('niAiRangeMax={0}\n'.format(self.daq.ai_range[1]))
                f.write('niAiRangeMin={0}\n'.format(self.daq.ai_range[0]))
                f.write('niMAGain={0}\n'.format(1))
                f.write('niMNGain={0}\n'.format(1))
                f.write('snsMnMaXaDw=0,0,{0},{1}\n'.format(self.daq.ai_num_channels,
                                                            self.daq.di_num_channels))                
                f.write('nSavedChans={0}\n'.format(self.nchannels))
                f.write('typeThis=nidq\n')
                p = []
                for k in self.daq.digital_channels.keys():
                    p.append('({0},{1})'.format(k,self.daq.digital_channels[k]))
                f.write('digitalChannelNames={0}\n'.format(','.join(p)))
                p = []
                for k in self.daq.analog_channels.keys():
                    p.append('({0},{1})'.format(k,self.daq.analog_channels[k]))
                f.write('analogChannelNames={0}\n'.format(','.join(p)))
        self.fd = None

    def open_file(self,nfiles = None,data = None):
        filename = self.get_filename_path()
        if not self.fd is None:
            self.close_file()
        self._open_file(filename,data)
        self.nFiles += 1
        if hasattr(self,'parsed_filename'):
            filename = self.parsed_filename
        display('Opened: '+ filename)

    def _open_file(self,filename,data = None):
        dtype = data.dtype
        if dtype == np.float32:
            dtype='float32'
        elif dtype == np.int16:
            dtype='int16'
        elif dtype == np.uint8:
            dtype='uint8'
        else:
            dtype='uint16'
        filename = filename.format(nchannels = self.nchannels,
                                   dtype=dtype)
        self.parsed_filename = filename
        self.fd = open(filename,'wb')
        self.nsamples = 0
        self.nbytes = 0

    def save(self, data,metadata = None):
        if self.fd is None:
            self.open_file(data = data)
        return self._write(data)
    
    def _write(self,data):
        self.fd.write(data)
        self.nbytes += data.nbytes
        self.nsamples += data.shape[1]
        
    def close_run(self):
        self.close_file()
        self.runs += 1
    
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
                 incrementruns=True,
                 compression = None,**kwargs):
        self.extension = '.tif'
        super(TiffCamWriter,self).__init__(cam = cam,
                                           datafolder=datafolder,
                                           filename=filename,
                                           dataname=dataname,
                                           pathformat=pathformat,
                                           framesperfile=framesperfile,
                                           sleeptime=sleeptime,
                                           incrementruns=incrementruns,
                                           **kwargs)
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
    with open(fname,'r',encoding = 'utf-8') as fd:
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
        if len(sync):
            sync = pd.DataFrame(sync,
                                columns=['sync','count','frame','timestamp'])
        if len(led):
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
    
