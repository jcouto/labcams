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

def display(msg):
    try:
        sys.stdout.write('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg + '\n')
        sys.stdout.flush()
    except:
        pass


preferencepath = pjoin(os.path.expanduser('~'), 'labcams')

defaultPreferences = {'datapaths':dict(dataserverpaths = ['/quadraraid/data',
                                                          '/mnt/nerffs01/mouselab/data'],
                                       onephotonpaths = '1photon/raw',
                                       logpaths = 'presentation',
                                       facecampaths = 'facecam',
                                       eyecampaths = 'eyecam',
                                       analysis = 'analysis')}


def getPreferences():
    ''' Reads the parameters from the home directory.

    pref = getPreferences(expname)

    User parameters like folder location, file preferences, paths...
    Joao Couto - May 2018
    '''
    if not os.path.isdir(preferencepath):
        os.makedirs(preferencepath)
        print('Creating .preference folder ['+preferencepath+']')

    preffile = pjoin(preferencepath,'preferences.json')
    if not os.path.isfile(preffile):
        with open(preffile, 'w') as outfile:
            json.dump(defaultPreferences, outfile, sort_keys = True, indent = 4)
            print('Saving default preferences to: ' + preffile)
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
        logpath = pjoin(server,datapaths['logpaths'],expname)
        logfile = glob(logpath + '.log')
        if len(logfile):
            logfile = logfile[0]
            break
    assert not logfile is None, "Could not find log for:{0}".format(expname)
    return logfile
