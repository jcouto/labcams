from __future__ import print_function
import sys
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
                         #'SubtractBackground':True,
                         'NBackgroundFrames':1.,
                         'Save':True},
                        {'description':'eyecam',
                         'name':'GC660M',
                         'driver':'AVT',
                         'gain':10,
                         'TrackEye':True,
                         'frameRate':31.,
                         'TriggerSource':'Line1',
                         'TriggerMode':'LevelHigh',
                         'Save':True},
                        {'description':'1photon',
                         'name':'qcam',
                         'id':0,
                         'driver':'QImaging',
                         'gain':1500,#1600,#3600
                         'triggerType':1,
                         'binning':2,
                         'exposure':100000,
                         'frameRate':0.1}],
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


def getPreferences(preffile = None,create = False):
    ''' Reads the parameters from the home directory.

    pref = getPreferences(expname)

    User parameters like folder location, file preferences, paths...
    Joao Couto - May 2018
    '''
    if preffile is None:
        preffile = pjoin(preferencepath,'default.json')

    if not os.path.isfile(preffile) and create:
        display('Creating preference file from defaults.')
        if not os.path.isdir(preferencepath):
            os.makedirs(preferencepath)
        with open(preffile, 'w') as outfile:
            json.dump(defaultPreferences, outfile, sort_keys = True, indent = 4)
            display('Saving default preferences to: ' + preffile)
    if os.path.isfile(preffile):
        if not os.path.isdir(preferencepath):
            os.makedirs(preferencepath)
            print('Creating preferences folder ['+preferencepath+']')
    with open(preffile, 'r') as infile:
        pref = json.load(infile)
    return pref


def cameraTimesFromVStimLog(logdata,plog,camidx = 3,nExcessFrames=10):
    '''
    Interpolate cameralog frames to those recorded by pyvstim
    '''
    campulses = plog['cam{0}'.format(camidx)]['value'].iloc[-1] 
    assert ((logdata['frame_id'].iloc[-1] > campulses - nExcessFrames) and
            (logdata['frame_id'].iloc[-1] < campulses + nExcessFrames)),"Camera pulse dont fit the log. Check the log."
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
