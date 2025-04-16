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

from __future__ import print_function
import cv2
import sys
import os
from functools import partial
from datetime import datetime
from glob import glob
import os
import sys
import json
from os.path import join as pjoin
from scipy.interpolate import interp1d
from tqdm import tqdm
import numpy as np
import time
import pandas as pd
MAX_QUEUE_SIZE = 1500

tstart = [time.time()]

from multiprocessing import Array
from ctypes import c_wchar
shared_date = Array(c_wchar,datetime.now().strftime('%Y%m%d_%H%M%S'))

def update_shared_date():
    shared_date[:] = datetime.now().strftime('%Y%m%d_%H%M%S')

def display(msg):
    try:
        sys.stdout.write('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg + '\n')
        sys.stdout.flush()
    except:
        pass


preferencepath = pjoin(os.path.expanduser('~'), 'labcams')

# This has the cameras and properties
_RECORDER_SETTINGS = {'recorder':['tiff','ffmpeg','binary'],
                      'recorder_help':'Different recorders allow saving data in different formats or using compresssion. Note that the realtime compression enabled by the ffmpeg video recorder can require specific hardware.',
                      'recording_queue':True,
                      'recording_queue_help':'Whether to use an intermediate queue for copying data from the camera, can assure that all data are stored regardless of disk usage; do not use this when recording at very high rates (1kHz) because it may introduce an overhead)'}

_SERVER_SETTINGS = {'server':['udp','zmq','none'],
                    'server_help':'These option allow setting servers to enable controlling the cameras and adding information to the log during recording. ',
                    'server_refresh_time':30,
                    'server_refresh_time_help':'How often to listen to messages (in ms)',
                    'server_port':9999}

_OTHER_SETTINGS = dict(recorder_path = pjoin(os.path.expanduser('~'),'data'),
                       recorder_frames_per_file = 0,
                       recorder_frames_per_file_help = 'number of frames per file (0 is for a single large file)',
                       recorder_sleep_time = 0.03,
                       recorder_path_format = pjoin('{datafolder}',
                                                    '{dataname}',
                                                    '{filename}',
                                                    '{today}_{run}_{nfiles}'))

_CAMERAS = dict(avt='Allied Vision Technology (AVT Mako,Manta... - pymba/Vimba)',
                qimaging = 'QImaging (EMC2 - Legacy driver)',
                opencv = 'OpenCV camera (Webcam, ...)',
                pco = 'PCO imaging - PCO Edge (PCO SDK)',
                ximea = 'Ximea (python sdk)',
                pointgrey = 'FLIR PointGrey - Chameleon 3 (PySpin/FLIR Spinnaker SDK)')
# description and id are mandatory
_CAMERA_SETTINGS = dict(avt = dict(name='camera serial number',
                                   TriggerSource = 'Line1',
                                   TriggerMode = 'LevelHigh',
                                   TriggerSelector = 'FrameStart',
                                   AcquisitionMode = 'Continuous',
                                   AcquisitionFrameCount=1000,
                                   nFrameBuffers=6,
                                   gain = 0,
                                   frameRate=60.),
                        qimaging=dict(exposure=100,
                                      gain=3600,
                                      binning = 4,
                                      triggerType = 0),
                        opencv = dict(id = 0,
                                      frameRate = 0),
                        pco = dict(id = 0,
                                   exposure=33),
                        ximea = dict(id = 0,
                                     exposure=33,
                                     binning = 4),
                        pointgrey = dict(roi = 'full sensor or [X,Y,W,H]',
                                         serial='Camera serial number',
                                         exposure = 7000,
                                         frameRate = 100.,
                                         pxformat='Mono8',
                                         binning = 1,
                                         gamma = 1.0,
                                         hardware_trigger = 'out_line3'))


DEFAULTS = dict(cams = [{'description':'facecam',
                         'name':'Mako G-030B',
                         'driver':'AVT',
                         'gain':10,
                         'frameRate':31.,
                         'TriggerSource':'Line1',
                         'TriggerMode':'LevelHigh',
                         'NBackgroundFrames':1.,
                         'Save':True},
                        {'description':'1photon',
                         'name':'qcam',
                         'id':0,
                         'driver':'QImaging',
                         'gain':1500,
                         'triggerType':1,
                         'binning':2,
                         'exposure':100000,
                         'frameRate':0.1},
                        {'name':'webcam',
                         'driver':'OpenCV',
                         'description':'webcam',
                         'id':0},
                        {'description':'1photon',
                         'driver':'PCO',
                         'exposure':33,
                         'id':0,
                         'name':'pco.edge',
                         'triggerType':0,
                         'recorder':'binary'}],
                recorder_path = pjoin(os.path.expanduser('~'),'data'),
                recorder_frames_per_file = -1,
                recorder_sleep_time = 0.05,
                server_port = 100000,
                compress = 0)


defaultPreferences = DEFAULTS


def getPreferences(preffile = None,create = True):
    ''' Reads the parameters from the home directory.

    pref = getPreferences(expname)

    User parameters like folder location, file preferences, paths...
    Joao Couto - May 2018
    '''
    prefpath = preferencepath
    if preffile is None:
        
        preffile = pjoin(preferencepath,'default.json')
    else:
        prefpath = os.path.dirname(preffile)
    if not os.path.isfile(preffile) and create:
        display('Creating preference file from defaults.')
        if not os.path.isdir(prefpath):
            os.makedirs(prefpath)
        with open(preffile, 'w') as outfile:
            json.dump(defaultPreferences, outfile, sort_keys = True, indent = 4)
            display('Saving default preferences to: ' + preffile)
            print('\t\t\t\t Edit the file before launching.')
            sys.exit(0)

    if os.path.isfile(preffile):
        with open(preffile, 'r') as infile:
            pref = json.load(infile)
        
    return pref


def chunk_indices(nframes, chunksize = 512, min_chunk_size = 16):
    '''
    Gets chunk indices for iterating over an array in evenly sized chunks
    Joao Couto - from wfield
    '''
    chunks = np.arange(0,nframes,chunksize,dtype = int)
    if (nframes - chunks[-1]) < min_chunk_size:
        chunks[-1] = nframes
    if not chunks[-1] == nframes:
        chunks = np.hstack([chunks,nframes])
    return [[chunks[i],chunks[i+1]] for i in range(len(chunks)-1)]


def cameraTimesFromVStimLog(logdata,plog,camidx = 3,nExcessFrames=10):
    '''
    Interpolate cameralog frames to those recorded by pyvstim
    '''
    campulses = plog['cam{0}'.format(camidx)]['value'].iloc[-1] 
    if not ((logdata['frame_id'].iloc[-1] > campulses - nExcessFrames) and
            (logdata['frame_id'].iloc[-1] < campulses + nExcessFrames)):
        print('''WARNING!!

Recorded camera frames {0} dont fit the log {1}. 

Check the log/cables.

Interpolating on the first and last frames.
'''.format(logdata['frame_id'].iloc[-1],campulses))
        logdata['duinotime'] = interp1d(
            plog['cam{0}'.format(camidx)]['value'].iloc[[0,-1]],
            plog['cam{0}'.format(camidx)]['duinotime'].iloc[0,-1],
            fill_value="extrapolate")(logdata['frame_id'])

    else:
        logdata['duinotime'] = interp1d(
            plog['cam{0}'.format(camidx)]['value'],
            plog['cam{0}'.format(camidx)]['duinotime'],
            fill_value="extrapolate")(logdata['frame_id'])
    return logdata


def unpackbits(x,num_bits = 16,output_binary = False):
    '''
    unpacks numbers in bits.
    '''
    if type(x) == pd.core.series.Series:
        x = np.array(x)
    
    xshape = list(x.shape)
    x = x.reshape([-1,1])
    to_and = 2**np.arange(num_bits).reshape([1,num_bits])
    bits = (x & to_and).astype(bool).astype(int).reshape(xshape + [num_bits])
    if output_binary:
        return bits.T
    mult = 1
    sync_idx_onset = np.where(mult*np.diff(bits,axis = 0)>0)
    sync_idx_offset = np.where(mult*np.diff(bits,axis = 0)<0)
    onsets = {}
    offsets = {}
    for ichan in np.unique(sync_idx_onset[1]):
        onsets[ichan] = sync_idx_onset[0][
            sync_idx_onset[1] == ichan]
    for ichan in np.unique(sync_idx_offset[1]):
        offsets[ichan] = sync_idx_offset[0][
            sync_idx_offset[1] == ichan]
    return onsets,offsets

