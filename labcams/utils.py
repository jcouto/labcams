from __future__ import print_function
import cv2
import sys
import os
from functools import partial
if sys.executable.endswith("pythonw.exe"):
    sys.stdout = sys.stdout = None
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

tstart = [time.time()]


def display(msg):
    try:
        sys.stdout.write('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg + '\n')
        sys.stdout.flush()
    except:
        pass


preferencepath = pjoin(os.path.expanduser('~'), 'labcams')

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
                recorder_path = 'I:\\data',
                recorder_frames_per_file = 256,
                recorder_sleep_time = 0.05,
                server_port = 100000,
                compress = 0,
                datapaths = dict(dataserverpaths = ['I:\\data',
                                                    'P:\\',
                                                    '/quadraraid/data',
                                                    '/mnt/nerffs01/mouselab/data'],
                                 onephotonpaths = '1photon/raw',
                                 logpaths = 'presentation',
                                 facecampaths = 'facecam',
                                 eyecampaths = 'eyecam',
                                 analysispaths = 'analysis'))


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



def findVStimLog(expname):
    prefs = getPreferences()
    datapaths = prefs['datapaths']
    logfile = None
    for server in datapaths['dataserverpaths']:
        logpath = pjoin(server,datapaths['logpaths'],*expname)
        logfile = glob(logpath + '.log')
        if len(logfile):
            logfile = logfile[0]
            break
    assert not logfile is None, "Could not find log for:{0}".format(expname)
    return logfile



def triggeredTrials(camdata,
                    camtime,
                    stimtimes,
                    tpre = 2,
                    global_baseline = False,
                    do_df_f = True,
                    display_progress = True):
    dt = np.mean(np.diff(camtime))
    stimavgs = []
    wpre = int(int(np.ceil(tpre/dt)))
    for iStim in np.unique(stimtimes[:,0]):
        (_,iTrials,starttimes,endtimes) = stimtimes[stimtimes[:,0]==iStim,:].T
        duration =  np.max(np.round(endtimes - starttimes))
        wdur = int(np.ceil(duration/dt))
        wpost = int(wdur+wpre)
        ntrials = len(iTrials)
        stimavg = np.zeros([ntrials,wpre+wpost,
                            camdata.shape[1],
                            camdata.shape[2]],dtype=np.float32)
        for i,(iTrial,time) in tqdm(enumerate(
            zip(iTrials,starttimes))) if display_progress else enumerate(
            zip(iTrials,starttimes)):
            ii = np.where(camtime < time)[0][-1]
            F = camdata[ii-wpre:ii+wpost:1,:,:].astype(np.float32)
            if global_baseline:
                baseline = F[:].min(axis = 0)
            else:
                baseline = F[:wpre].mean(axis = 0)
            if do_df_f:
                stimavg[i] = (F - baseline)/baseline
            else:
                stimavg[i] = F - baseline
        stimavg[:,:,:10,:10] = np.min(stimavg)
        stimavg[:,wpre:wpost,:10,:10] = np.max(stimavg)
        stimavgs.append(stimavg)
    return stimavgs

def triggeredAverage(camdata,
                     camtime,
                     stimtimes,
                     tpre = 2.,
                     global_baseline = False,
                     do_df_f = True,display_progress = True):
    dt = np.mean(np.diff(camtime))
    stimavgs = []
    wpre = int(int(np.ceil(tpre/dt)))
    for iStim in np.unique(stimtimes[:,0]):
        (_,iTrials,starttimes,endtimes) = stimtimes[stimtimes[:,0]==iStim,:].T
        duration =  np.max(np.round(endtimes - starttimes))
        wdur = int(np.ceil(duration/dt))
        wpost = int(wdur+wpre)
        ntrials = len(iTrials)
        stimavg = np.zeros([wpre+wpost,
                            camdata.shape[1],
                            camdata.shape[2]],dtype=np.float32)
        for i,(iTrial,time) in tqdm(enumerate(
                zip(iTrials,starttimes)),total = ntrials) if display_progress else enumerate(
            zip(iTrials,starttimes)):
            ii = np.where(camtime < time)[0][-1]
            F = camdata[ii-wpre:ii+wpost:1,:,:].astype(np.float32)
            if global_baseline:
                baseline = F[:].min(axis = 0)
            else:
                baseline = F[:wpre].mean(axis = 0)
            if do_df_f:
                stimavg += (F - baseline)/baseline
            else:
                stimavg += F - baseline
        stimavg /= float(ntrials)
        stimavg[:,:10,:10] = np.min(stimavg)
        stimavg[wpre:wpost,:10,:10] = np.max(stimavg)
        stimavgs.append(stimavg)
    return stimavgs


def binFramesToLaps(laps,time,position,frames, lapspace = None,
                    velocity = None,
                    velocityThreshold = 1., beltLength=150.,baseline = None,
                    method=lambda x : np.nanmean(x,axis=0)):
    '''
    Bins a set of frames to lap position.
        - laps is [numberOfLaps,2] the start and stop time of each lap
    
    '''
    if lapspace is None:
        lapspace = np.arange(0,beltLength,1.)
    lapX = np.zeros((lapspace.shape[0]-1,frames.shape[1],frames.shape[2],),
                    dtype=np.float32)
    #lapX[:] = np.nan
    for k,l in tqdm(enumerate(range(laps.shape[0]))):
        s,e = laps[l,:]
        
        if not velocity is None:
            idx = np.where((time>=s) & (time<e) &
                          (velocity > velocityThreshold))[0].astype(int)
        else:
            idx = np.where((time>=s) & (time<e))[0].astype(int)
        x = frames[idx,:,:]
        pos = position[idx]
        inds = np.digitize(pos, lapspace)
        
        for i in np.unique(inds)[:-1]: 
            tmp = x[(inds==i),:,:].astype(np.float32)
            if not baseline is None:
                tmp = (tmp -  baseline)/baseline
            lapX[i-1,:,:] += method(tmp)/float(laps.shape[0])
    return lapX

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

