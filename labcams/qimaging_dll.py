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

'''
This is adapted from:
LFDisplay - GUI for a light field microscope
Credits to Petr Baudis

https://github.com/nemaload/LFDisplay

'''

import ctypes
import platform
import Queue
import threading
import gc
import struct

class Error(Exception):
    pass

if platform.system() in ('Windows','Microsoft'):
    try:
        _dll = ctypes.WinDLL('QCamDriver.dll')
    except WindowsError:
        _dll = ctypes.WinDLL('QCamDriverx64.dll')

    FUNCTYPE = ctypes.WINFUNCTYPE
elif platform.system() == 'Darwin':
    _dll = ctypes.CDLL('QCam.framework/Versions/Current/QCam')
    FUNCTYPE = ctypes.CFUNCTYPE
else:
    raise Error('The QCam Python wrapper is not supported on '+platform.system())

# camera description
class QCam_CamListItem(ctypes.Structure):
    _fields_ = [('cameraId',ctypes.c_ulong),
                ('cameraType',ctypes.c_ulong),
                ('uniqueId',ctypes.c_ulong),
                ('isOpen',ctypes.c_ulong),
                ('_reserved',ctypes.c_ulong*10)]
# frame description
class QCam_Frame(ctypes.Structure):
    _fields_ = [('pBuffer',ctypes.c_void_p),
                ('bufferSize',ctypes.c_ulong),
                ('format',ctypes.c_ulong),
                ('width',ctypes.c_ulong),
                ('height',ctypes.c_ulong),
                ('size',ctypes.c_ulong),
                ('bits',ctypes.c_ushort),
                ('frameNumber',ctypes.c_ushort),
                ('bayerPattern',ctypes.c_ulong),
                ('errorCode',ctypes.c_ulong),
                ('timeStamp',ctypes.c_ulong),
                ('_reserved',ctypes.c_ulong*8)]
# settings
class QCam_Settings(ctypes.Structure):
    _fields_ = [('size',ctypes.c_ulong),
                ('_private_data',ctypes.c_ulong * 64)]
    def __init__(self, *args, **kwds):
        ctypes.Structure.__init__(self, *args, **kwds)
        self.size = ctypes.sizeof(ctypes.c_ulong)*65

# types
QCam_Err=ctypes.c_int
QCam_Info=ctypes.c_int
QCam_Handle=ctypes.c_void_p
UNSIGNED64=ctypes.c_ulonglong

QCam_Param=ctypes.c_int
QCam_ParamS32=ctypes.c_int
QCam_Param64=ctypes.c_int

# callback function
QCam_AsyncCallback = FUNCTYPE(None,
                              ctypes.c_void_p, ctypes.c_ulong, QCam_Err, ctypes.c_ulong)

# function prototypes

_dll.QCam_LoadDriver.restype = QCam_Err
_dll.QCam_LoadDriver.argtypes = []

_dll.QCam_ReleaseDriver.restype = None
_dll.QCam_ReleaseDriver.argtypes = []

_dll.QCam_LibVersion.restype = QCam_Err
_dll.QCam_LibVersion.argtypes = [ctypes.POINTER(ctypes.c_ushort),
                                 ctypes.POINTER(ctypes.c_ushort),
                                 ctypes.POINTER(ctypes.c_ushort)]

_dll.QCam_ListCameras.restype = QCam_Err
_dll.QCam_ListCameras.argtypes = [ctypes.POINTER(QCam_CamListItem),
                                  ctypes.POINTER(ctypes.c_ulong)]

_dll.QCam_OpenCamera.restype = QCam_Err
_dll.QCam_OpenCamera.argtypes = [ctypes.c_ulong,
                                 ctypes.POINTER(QCam_Handle)]

_dll.QCam_CloseCamera.restype = QCam_Err
_dll.QCam_CloseCamera.argtypes = [QCam_Handle]

_dll.QCam_GetSerialString.restype = QCam_Err
_dll.QCam_GetSerialString.argtypes = [QCam_Handle,
                                      ctypes.c_char_p,
                                      ctypes.c_ulong]

_dll.QCam_GetInfo.restype = QCam_Err
_dll.QCam_GetInfo.argtypes = [QCam_Handle,
                              QCam_Info,
                              ctypes.POINTER(ctypes.c_ulong)]

_dll.QCam_ReadDefaultSettings.restype = QCam_Err
_dll.QCam_ReadDefaultSettings.argtypes = [QCam_Handle,
                                          ctypes.POINTER(QCam_Settings)]

_dll.QCam_ReadSettingsFromCam.restype = QCam_Err
_dll.QCam_ReadSettingsFromCam.argtypes = [QCam_Handle,
                                          ctypes.POINTER(QCam_Settings)]

_dll.QCam_SendSettingsToCam.restype = QCam_Err
_dll.QCam_SendSettingsToCam.argtypes = [QCam_Handle,
                                        ctypes.POINTER(QCam_Settings)]

_dll.QCam_PreflightSettings.restype = QCam_Err
_dll.QCam_PreflightSettings.argtypes = [QCam_Handle,
                                        ctypes.POINTER(QCam_Settings)]

_dll.QCam_TranslateSettings.restype = QCam_Err
_dll.QCam_TranslateSettings.argtypes = [QCam_Handle,
                                        ctypes.POINTER(QCam_Settings)]

_dll.QCam_GetParam.restype = QCam_Err
_dll.QCam_GetParam.argtypes = [ctypes.POINTER(QCam_Settings),
                               QCam_Param,
                               ctypes.POINTER(ctypes.c_ulong)]

_dll.QCam_GetParamS32.restype = QCam_Err
_dll.QCam_GetParamS32.argtypes = [ctypes.POINTER(QCam_Settings),
                                  QCam_ParamS32,
                                  ctypes.POINTER(ctypes.c_long)]

_dll.QCam_GetParam64.restype = QCam_Err
_dll.QCam_GetParam64.argtypes = [ctypes.POINTER(QCam_Settings),
                                 QCam_Param64,
                                 ctypes.POINTER(UNSIGNED64)]

_dll.QCam_SetParam.restype = QCam_Err
_dll.QCam_SetParam.argtypes = [ctypes.POINTER(QCam_Settings),
                               QCam_Param,
                               ctypes.c_ulong]

_dll.QCam_SetParamS32.restype = QCam_Err
_dll.QCam_SetParamS32.argtypes = [ctypes.POINTER(QCam_Settings),
                                  QCam_ParamS32,
                                  ctypes.c_long]

_dll.QCam_SetParam64.restype = QCam_Err
_dll.QCam_SetParam64.argtypes = [ctypes.POINTER(QCam_Settings),
                                 QCam_Param64,
                                 ctypes.c_ulonglong]

_dll.QCam_GetParamMin.restype = QCam_Err
_dll.QCam_GetParamMin.argtypes = [ctypes.POINTER(QCam_Settings),
                                  QCam_Param,
                                  ctypes.POINTER(ctypes.c_ulong)]

_dll.QCam_GetParamS32Min.restype = QCam_Err
_dll.QCam_GetParamS32Min.argtypes = [ctypes.POINTER(QCam_Settings),
                                     QCam_ParamS32,
                                     ctypes.POINTER(ctypes.c_long)]

_dll.QCam_GetParam64Min.restype = QCam_Err
_dll.QCam_GetParam64Min.argtypes = [ctypes.POINTER(QCam_Settings),
                                    QCam_Param64,
                                    ctypes.POINTER(UNSIGNED64)]

_dll.QCam_GetParamMax.restype = QCam_Err
_dll.QCam_GetParamMax.argtypes = [ctypes.POINTER(QCam_Settings),
                                  QCam_Param,
                                  ctypes.POINTER(ctypes.c_ulong)]

_dll.QCam_GetParamS32Max.restype = QCam_Err
_dll.QCam_GetParamS32Max.argtypes = [ctypes.POINTER(QCam_Settings),
                                     QCam_ParamS32,
                                     ctypes.POINTER(ctypes.c_long)]

_dll.QCam_GetParam64Max.restype = QCam_Err
_dll.QCam_GetParam64Max.argtypes = [ctypes.POINTER(QCam_Settings),
                                    QCam_Param64,
                                    ctypes.POINTER(UNSIGNED64)]

_dll.QCam_GetParamSparseTable.restype = QCam_Err
_dll.QCam_GetParamSparseTable.argtypes = [ctypes.POINTER(QCam_Settings),
                                          QCam_Param,
                                          ctypes.POINTER(ctypes.c_ulong),
                                          ctypes.POINTER(ctypes.c_int)]

_dll.QCam_GetParamSparseTableS32.restype = QCam_Err
_dll.QCam_GetParamSparseTableS32.argtypes = [ctypes.POINTER(QCam_Settings),
                                             QCam_ParamS32,
                                             ctypes.POINTER(ctypes.c_long),
                                             ctypes.POINTER(ctypes.c_int)]

_dll.QCam_GetParamSparseTable64.restype = QCam_Err
_dll.QCam_GetParamSparseTable64.argtypes = [ctypes.POINTER(QCam_Settings),
                                            QCam_Param64,
                                            ctypes.POINTER(UNSIGNED64),
                                            ctypes.POINTER(ctypes.c_int)]

_dll.QCam_IsSparseTable.restype = QCam_Err
_dll.QCam_IsSparseTable.argtypes = [ctypes.POINTER(QCam_Settings),
                                    QCam_Param]

_dll.QCam_IsSparseTableS32.restype = QCam_Err
_dll.QCam_IsSparseTableS32.argtypes = [ctypes.POINTER(QCam_Settings),
                                       QCam_ParamS32]

_dll.QCam_IsSparseTable64.restype = QCam_Err
_dll.QCam_IsSparseTable64.argtypes = [ctypes.POINTER(QCam_Settings),
                                      QCam_Param64]

_dll.QCam_IsRangeTable.restype = QCam_Err
_dll.QCam_IsRangeTable.argtypes = [ctypes.POINTER(QCam_Settings),
                                    QCam_Param]

_dll.QCam_IsRangeTableS32.restype = QCam_Err
_dll.QCam_IsRangeTableS32.argtypes = [ctypes.POINTER(QCam_Settings),
                                       QCam_ParamS32]

_dll.QCam_IsRangeTable64.restype = QCam_Err
_dll.QCam_IsRangeTable64.argtypes = [ctypes.POINTER(QCam_Settings),
                                      QCam_Param64]

_dll.QCam_IsParamSupported.restype = QCam_Err
_dll.QCam_IsParamSupported.argtypes = [QCam_Handle,
                                       QCam_Param]

_dll.QCam_IsParamS32Supported.restype = QCam_Err
_dll.QCam_IsParamS32Supported.argtypes = [QCam_Handle,
                                          QCam_ParamS32]

_dll.QCam_IsParam64Supported.restype = QCam_Err
_dll.QCam_IsParam64Supported.argtypes = [QCam_Handle,
                                         QCam_Param64]

_dll.QCam_SetStreaming.restype = QCam_Err
_dll.QCam_SetStreaming.argtypes = [QCam_Handle,
                                   ctypes.c_ulong]

_dll.QCam_Trigger.restype = QCam_Err
_dll.QCam_Trigger.argtypes = [QCam_Handle]

_dll.QCam_Abort.restype = QCam_Err
_dll.QCam_Abort.argtypes = [QCam_Handle]

_dll.QCam_GrabFrame.restype = QCam_Err
_dll.QCam_GrabFrame.argtypes = [QCam_Handle,
                                ctypes.POINTER(QCam_Frame)]
                                
_dll.QCam_QueueFrame.restype = QCam_Err
_dll.QCam_QueueFrame.argtypes = [QCam_Handle,
                                 ctypes.POINTER(QCam_Frame),
                                 QCam_AsyncCallback,
                                 ctypes.c_ulong,
                                 ctypes.c_void_p,
                                 ctypes.c_ulong]

_dll.QCam_QueueSettings.restype = QCam_Err
_dll.QCam_QueueSettings.argtypes = [QCam_Handle,
                                    ctypes.POINTER(QCam_Settings),
                                    QCam_AsyncCallback,
                                    ctypes.c_ulong,
                                    ctypes.c_void_p,
                                    ctypes.c_ulong]


import ctypes

# data types
CamListItem = QCam_CamListItem
Frame = QCam_Frame
AsyncCallback =QCam_AsyncCallback
#
# CONSTANTS
#

MAX_SERIAL_STRING_LENGTH = 80

# values of QCam_Err
qerrSuccess = 0
qerrNotSupported = 1
qerrInvalidValue = 2
qerrBadSettings = 3
qerrNoUserDriver = 4
qerrNoFirewireDriver = 5
qerrDriverConnection = 6
qerrDriverAlreadyLoaded = 7
qerrDriverNotLoaded = 8
qerrInvalidHandle = 9
qerrUnknownCamera = 10
qerrInvalidCameraId = 11
qerrNoMoreConnections = 12
qerrHardwareFault = 13
qerrFirewireFault = 14
qerrCameraFault = 15
qerrDriverFault = 16
qerrInvalidFrameIndex = 17
qerrBufferTooSmall = 18
qerrOutOfMemory = 19
qerrOutOfSharedMemory = 20
qerrBusy = 21
qerrQueueFull = 22
qerrCancelled = 23
qerrNotStreaming = 24
qerrLostSync = 25
qerrBlackFill = 26
qerrFirewireOverflow = 27
qerrUnplugged = 28
qerrAccessDenied = 29
qerrStreamFault = 30
qerrQCamUpdateNeeded = 31
qerrRoiTooSmall = 32

# values of QCam_Info
qinfCameraType = 0
qinfSerialNumber = 1 # Only for model-A (not # MicroPublishers);
                     # otherwise returns 0
qinfHardwareVersion = 2
qinfFirmwareVersion = 3
qinfCcd = 4
qinfBitDepth = 5 # Maximum number of bits
qinfCooled = 6 # 1 if camera has cooler
qinfReserved1 = 7 # Factory test values
qinfImageWidth = 8 # Width of ROI, in pixels
qinfImageHeight = 9 # Height of ROI, in pixels
qinfImageSize = 10 # Size of image, in bytes
qinfCcdType = 11 # Monochrome, bayer, etc.
qinfCcdWidth = 12 # Maximum width
qinfCcdHeight = 13 # Maximum height
qinfFirmwareBuild = 14
qinfUniqueId = 15 # Same as uniqueId in QCam_CamListItem
qinfIsModelB = 16 # 1 for model-B functionality, 0 otherwise
qinfIntensifierModel = 17 # Intensifier tube model, see
                          # QCam_qcIntensifierModel
qinfExposureRes = 18 # Exposure Time resolution (in nanoseconds)
qinfTriggerDelayRes = 19 # Trigger Delay Resolution (in nanoseconds)
qinfStreamVersion = 20 # Streaming Version
qinfNormGainSigFigs = 21 # Normalized Gain Significant Figures
                         # resolution
qinfNormGaindBRes = 22 # Normalized Gain dB resolution (micro units)
qinfNormITGainSigFigs = 23 # Normalized Intensifier Gain Significant
                           # Figures
qinfNormITGaindBRes = 24 # Normalized Intensifier Gain dB resolution
                         # (micro units)
qinfRegulatedCooling = 25 # 1 if camera has regulated cooling
qinfRegulatedCoolingLock= 26 # 1 if camera is at regulated temp, 0
                             # otherwise
qinfFanControl = 29 # 1 if camera can control fan speed
qinfHighSensitivityMode = 30 # 1 if camera has enhanced red mode
                             # available
qinfBlackoutMode = 31 # 1 if camera has blackout mode available
qinfPostProcessImageSize= 32 # returns the size (in bytes) of the
                             # post-processed image
qinfAsymetricalBinning = 33 # TRUE if asymetrical binning is
                            # available, 0 otherwise
qinfEMGain = 34 # TRUE if camera supports EM Gain
qinfOpenDelay = 35 # TRUE if open delay controls are available, 0
                   # otherwise
qinfCloseDelay = 36 # TRUE if close delay controls are available, 0
                    # otherwise
qinfEasyEmModeSupported = 42 # 20160620: True if easyEmMode is supported

# values of QCam_qcCameraType
qcCameraUnknown	= 0
qcCameraMi2 = 1
qcCameraPmi = 2
qcCameraRet1350 = 3
qcCameraQICam = 4
qcCameraRet1300B = 5
qcCameraRet1350B = 6
qcCameraQICamB = 7
qcCameraMicroPub = 8
qcCameraRetIT = 9
qcCameraQICamIR = 10
qcCameraRochester = 11
qcCameraRet4000R = 12
qcCameraRet2000R = 13
qcCameraRoleraXR = 14
qcCameraRetigaSRV = 15
qcCameraOem3 = 16
qcCameraRoleraMGi = 17
qcCameraRet4000RV = 18
qcCameraRet2000RV = 19
qcCameraOem4 = 20
qcCameraX = 1000
qcCameraOem1 = 1001
qcCameraOem2 = 1002

# descriptive names of qcCameraType
_camera_names = {
qcCameraUnknown : 'QImaging Camera (Unknown)',
qcCameraMi2 : 'QImaging MicroImager II / Retiga 3000',
qcCameraPmi : 'QImaging PMI',
qcCameraRet1350 : 'QImaging Retiga 1350',
qcCameraQICam : 'QImaging QICAM',
qcCameraRet1300B : 'QImaging Retiga 1300B',
qcCameraRet1350B : 'QImaging Retiga 1350B',
qcCameraQICamB : 'QImaging QICAM B',
qcCameraMicroPub : 'QImaging MicroPublisher',
qcCameraRetIT : 'QImaging Intensified Retiga',
qcCameraQICamIR : 'QImaging QICAM IR',
qcCameraRochester : 'QImaging Rochester',
qcCameraRet4000R : 'QImaging Retiga 4000R',
qcCameraRet2000R : 'QImaging Retiga 2000R',
qcCameraRoleraXR : 'QImaging Rolera-XR',
qcCameraRetigaSRV : 'QImaging Retiga SRV',
qcCameraOem3 : 'QImaging OEM 3',
qcCameraRoleraMGi : 'QImaging Rolera MGi',
qcCameraRet4000RV : 'QImaging Retiga 4000RV',
qcCameraRet2000RV : 'QImaging Retiga 2000RV',
qcCameraOem4 : 'QImaging OEM 4',
qcCameraX : 'QImaging Camera X (Engineering/OEM)',
qcCameraOem1 : 'QImaging OEM 1',
qcCameraOem2 : 'QImaging OEM 2',
}

def camera_type_to_string(camera_type):
    try:
        return _camera_names[camera_type]
    except KeyError:
        return 'QImaging Camera (Unknown %d)' % camera_type

# values of QCam_qcCcd (CCD types)
qcCcdKAF1400 = 0
qcCcdKAF1600 = 1
qcCcdKAF1600L = 2
qcCcdKAF4200 = 3
qcCcdICX085AL = 4
qcCcdICX085AK = 5
qcCcdICX285AL = 6
qcCcdICX285AK = 7
qcCcdICX205AL = 8
qcCcdICX205AK = 9
qcCcdICX252AQ = 10
qcCcdS70311006 = 11
qcCcdICX282AQ = 12
qcCcdICX407AL = 13
qcCcdS70310908 = 14
qcCcdVQE3618L = 15
qcCcdKAI2001gQ = 16
qcCcdKAI2001gN = 17
qcCcdKAI2001MgAR = 18
qcCcdKAI2001CMgAR = 19
qcCcdKAI4020gN = 20
qcCcdKAI4020MgAR = 21
qcCcdKAI4020MgN = 22
qcCcdKAI4020CMgAR = 23
qcCcdKAI1020gN = 24
qcCcdKAI1020MgAR = 25
qcCcdKAI1020MgC = 26
qcCcdKAI1020CMgAR = 27
qcCcdKAI2001MgC = 28
qcCcdKAI2001gAR = 29
qcCcdKAI2001gC = 30
qcCcdKAI2001MgN = 31
qcCcdKAI2001CMgC = 32
qcCcdKAI2001CMgN = 33
qcCcdKAI4020MgC = 34
qcCcdKAI4020gAR = 35
qcCcdKAI4020gQ = 36
qcCcdKAI4020gC = 37
qcCcdKAI4020CMgC = 38
qcCcdKAI4020CMgN = 39
qcCcdKAI1020gAR = 40
qcCcdKAI1020gQ = 41
qcCcdKAI1020gC = 42
qcCcdKAI1020MgN = 43
qcCcdKAI1020CMgC = 44
qcCcdKAI1020CMgN = 45
qcCcdKAI2020MgAR = 46
qcCcdKAI2020MgC = 47
qcCcdKAI2020gAR = 48
qcCcdKAI2020gQ = 49
qcCcdKAI2020gC = 50
qcCcdKAI2020MgN = 51
qcCcdKAI2020gN = 52
qcCcdKAI2020CMgAR = 53
qcCcdKAI2020CMgC = 54
qcCcdKAI2020CMgN = 55
qcCcdKAI2021MgC = 56
qcCcdKAI2021CMgC = 57
qcCcdKAI2021MgAR = 58
qcCcdKAI2021CMgAR = 59
qcCcdKAI2021gAR = 60
qcCcdKAI2021gQ = 61
qcCcdKAI2021gC = 62
qcCcdKAI2021gN = 63
qcCcdKAI2021MgN = 64
qcCcdKAI2021CMgN = 65
qcCcdKAI4021MgC = 66
qcCcdKAI4021CMgC = 67
qcCcdKAI4021MgAR = 68
qcCcdKAI4021CMgAR = 69
qcCcdKAI4021gAR = 70
qcCcdKAI4021gQ = 71
qcCcdKAI4021gC = 72
qcCcdKAI4021gN = 73
qcCcdKAI4021MgN = 74
qcCcdKAI4021CMgN = 75
qcCcdKAF3200M = 76
qcCcdKAF3200ME = 77
qcCcdE2v97B = 78

# CCD info (C = color, M = microlens,
# gAR = antireflective glass
# gC = clear glass
# gQ = quartz glass
# gN = unsealed CCD (no glass)
_ccd_info = {
    qcCcdKAF1400 : ('KAF1400', 6.8, 6.8),
    qcCcdKAF1600 : ('KAF1600', 9.0, 9.0),
    qcCcdKAF1600L : ('KAF1600L', 9.0, 9.0),
    qcCcdKAF4200 : ('KAF4200', 9.0, 9.0),
    qcCcdICX085AL : ('ICX085AL', 6.7, 6.7), # L = B&W
    qcCcdICX085AK : ('ICX085AK', 6.7, 6.7), # K = Color
    qcCcdICX285AL : ('ICX285AL', 6.45, 6.45),
    qcCcdICX285AK : ('ICX285AK', 6.45, 6.45),
    qcCcdICX205AL : ('ICX205AL', 4.65, 4.65),
    qcCcdICX205AK : ('ICX205AK', 4.65, 4.65),
    qcCcdICX252AQ : ('ICX252AQ', 3.45, 3.45),
    qcCcdS70311006 : ('S70311006', 0.0, 0.0),
    qcCcdICX282AQ : ('ICX282AQ', 3.4, 3.4),
    qcCcdICX407AL : ('ICX407AL', 4.65, 4.65),
    qcCcdS70310908 : ('S70310908', 0.0, 0.0),
    qcCcdVQE3618L : ('VQE3618L', 12.7, 12.7), # QICAM IR
    qcCcdKAI2001gQ : ('KAI2001gQ', 7.4, 7.4),
    qcCcdKAI2001gN : ('KAI2001gN', 7.4, 7.4),
    qcCcdKAI2001MgAR : ('KAI2001MgAR', 7.4, 7.4),
    qcCcdKAI2001CMgAR : ('KAI2001CMgAR', 7.4, 7.4),
    qcCcdKAI4020gN : ('KAI4020gN', 7.4, 7.4),
    qcCcdKAI4020MgAR : ('KAI4020MgAR', 7.4, 7.4),
    qcCcdKAI4020MgN : ('KAI4020MgN', 7.4, 7.4),
    qcCcdKAI4020CMgAR : ('KAI4020CMgAR', 7.4, 7.4),
    qcCcdKAI1020gN : ('KAI1020gN', 7.4, 7.4),
    qcCcdKAI1020MgAR : ('KAI1020MgAR', 7.4, 7.4),
    qcCcdKAI1020MgC : ('KAI1020MgC', 7.4, 7.4),
    qcCcdKAI1020CMgAR : ('KAI1020CMgAR', 7.4, 7.4),
    qcCcdKAI2001MgC : ('KAI2001MgC', 7.4, 7.4),
    qcCcdKAI2001gAR : ('KAI2001gAR', 7.4, 7.4),
    qcCcdKAI2001gC : ('KAI2001gC', 7.4, 7.4),
    qcCcdKAI2001MgN : ('KAI2001MgN', 7.4, 7.4),
    qcCcdKAI2001CMgC : ('KAI2001CMgC', 7.4, 7.4),
    qcCcdKAI2001CMgN : ('KAI2001CMgN', 7.4, 7.4),
    qcCcdKAI4020MgC : ('KAI4020MgC', 7.4, 7.4),
    qcCcdKAI4020gAR : ('KAI4020gAR', 7.4, 7.4),
    qcCcdKAI4020gQ : ('KAI4020gQ', 7.4, 7.4),
    qcCcdKAI4020gC : ('KAI4020gC', 7.4, 7.4),
    qcCcdKAI4020CMgC : ('KAI4020CMgC', 7.4, 7.4),
    qcCcdKAI4020CMgN : ('KAI4020CMgN', 7.4, 7.4),
    qcCcdKAI1020gAR : ('KAI1020gAR', 7.4, 7.4),
    qcCcdKAI1020gQ : ('KAI1020gQ', 7.4, 7.4),
    qcCcdKAI1020gC : ('KAI1020gC', 7.4, 7.4),
    qcCcdKAI1020MgN : ('KAI1020MgN', 7.4, 7.4),
    qcCcdKAI1020CMgC : ('KAI1020CMgC', 7.4, 7.4),
    qcCcdKAI1020CMgN : ('KAI1020CMgN', 7.4, 7.4),
    qcCcdKAI2020MgAR : ('KAI2020MgAR', 7.4, 7.4),
    qcCcdKAI2020MgC : ('KAI2020MgC', 7.4, 7.4),
    qcCcdKAI2020gAR : ('KAI2020gAR', 7.4, 7.4),
    qcCcdKAI2020gQ : ('KAI2020gQ', 7.4, 7.4),
    qcCcdKAI2020gC : ('KAI2020gC', 7.4, 7.4),
    qcCcdKAI2020MgN : ('KAI2020MgN', 7.4, 7.4),
    qcCcdKAI2020gN : ('KAI2020gN', 7.4, 7.4),
    qcCcdKAI2020CMgAR : ('KAI2020CMgAR', 7.4, 7.4),
    qcCcdKAI2020CMgC : ('KAI2020CMgC', 7.4, 7.4),
    qcCcdKAI2020CMgN : ('KAI2020CMgN', 7.4, 7.4),
    qcCcdKAI2021MgC : ('KAI2021MgC', 7.4, 7.4),
    qcCcdKAI2021CMgC : ('KAI2021CMgC', 7.4, 7.4),
    qcCcdKAI2021MgAR : ('KAI2021MgAR', 7.4, 7.4),
    qcCcdKAI2021CMgAR : ('KAI2021CMgAR', 7.4, 7.4),
    qcCcdKAI2021gAR : ('KAI2021gAR', 7.4, 7.4),
    qcCcdKAI2021gQ : ('KAI2021gQ', 7.4, 7.4),
    qcCcdKAI2021gC : ('KAI2021gC', 7.4, 7.4),
    qcCcdKAI2021gN : ('KAI2021gN', 7.4, 7.4),
    qcCcdKAI2021MgN : ('KAI2021MgN', 7.4, 7.4),
    qcCcdKAI2021CMgN : ('KAI2021CMgN', 7.4, 7.4),
    qcCcdKAI4021MgC : ('KAI4021MgC', 7.4, 7.4),
    qcCcdKAI4021CMgC : ('KAI4021CMgC', 7.4, 7.4),
    qcCcdKAI4021MgAR : ('KAI4021MgAR', 7.4, 7.4),
    qcCcdKAI4021CMgAR : ('KAI4021CMgAR', 7.4, 7.4),
    qcCcdKAI4021gAR : ('KAI4021gAR', 7.4, 7.4),
    qcCcdKAI4021gQ : ('KAI4021gQ', 7.4, 7.4),
    qcCcdKAI4021gC : ('KAI4021gC', 7.4, 7.4),
    qcCcdKAI4021gN : ('KAI4021gN', 7.4, 7.4),
    qcCcdKAI4021MgN : ('KAI4021MgN', 7.4, 7.4),
    qcCcdKAI4021CMgN : ('KAI4021CMgN', 7.4, 7.4),
    qcCcdKAF3200M : ('KAF3200M', 6.8, 6.8),
    qcCcdKAF3200ME : ('KAF3200ME', 6.8, 6.8),
    qcCcdE2v97B : ('E2v97B', 0.0, 0.0),
}

def ccd_to_info(ccd):
    try:
        return _ccd_info[ccd]
    except KeyError:
        return ('Unknown', 0.0, 0.0)

# value of ccdType
qcCcdMonochrome	= 0
qcCcdColorBayer	= 1

# Parameter names
qprmGain = 0 # Camera gain (gain on CCD output)
qprmOffset = 1 # Camera offset (offset in CCD ADC)
qprmExposure = 2 # Exposure in microseconds
qprmBinning = 3 # Binning, for cameras with square binning
qprmHorizontalBinning = 4 # Binning, if camera has separate horiz value
qprmVerticalBinning = 5 # Binning, if camera has separate vert value
qprmReadoutSpeed = 6 # See readout speed constants
qprmTriggerType = 7 # See trigger constants 0:freerun, 1: edgeHi
qprmColorWheel = 8 # Manual control of wheel color
qprmCoolerActive = 9 # 1 turns on cooler, 0 turns off
qprmExposureRed = 10 # For LCD filter mode: exposure (ms) of red shot
qprmExposureBlue = 11 # For LCD filter mode: exposure (ms) of green shot
qprmImageFormat = 12 # See QCam_ImageFormat
qprmRoiX = 13 # Upper left X of ROI
qprmRoiY = 14 # Upper left Y of ROI
qprmRoiWidth = 15 # Width of ROI, in pixels
qprmRoiHeight = 16 # Height of ROI, in pixels
qprmReserved1 = 17
qprmShutterState = 18 # Shutter position
qprmReserved2 = 19
qprmSyncb = 20 # SyncB output on some model-B cameras
qprmReserved3 = 21
qprmIntensifierGain = 22 # Gain value for the intensifier (Intensified cameras only)
qprmTriggerDelay = 23 # Trigger delay in nanoseconds.
qprmCameraMode = 24 # Camera mode
qprmNormalizedGain = 25 # Normalized camera gain (micro units)
qprmNormIntensGaindB = 26 # Normalized intensifier gain dB (micro units)
qprmDoPostProcessing = 27 # Turns post processing on and off, 1 = On 0 = Off
qprmPostProcessGainRed = 28 # parameter to set bayer gain
qprmPostProcessGainGreen = 29 # parameter to set bayer gain
qprmPostProcessGainBlue = 30 # parameter to set bayer gain
qprmPostProcessBayerAlgorithm = 31 # specify the bayer interpolation. QCam_qcBayerInterp enum with the possible algorithms is located in QCamImgfnc.h  	
qprmPostProcessImageFormat = 32 # image format for post processed images	
qprmFan = 33 # use QCam_qcFanSpeed to modify speed
qprmBlackoutMode = 34 # 1 turns all lights off, 0 turns them back on
qprmHighSensitivityMode = 35 # 1 turns high sensitivity mode on, 0 turn it off
qprmReadoutPort = 36 # Set the normal or EM readout port 
qprmEMGain = 37 # Set the EM gain
qprmOpenDelay = 38 # each bit is 10us rangeis 0-655.35ms (must be entered as us) cannot be longer then (Texp - 10us) where Texp = exposure time
qprmCloseDelay = 39 # each bit is 10us rangeis 0-655.35ms (must be entered as us) cannot be longer then (Texp - 10us) where Texp = exposure time
qprmCCDClearingMode = 40 # can be set to qcPreFrameClearing or qcNonClearing
qprmEasyEmMode = 47 # 20160620: added because we needed to control this

qprmS32NormalizedGaindB = 0 # Normalized camera gain in dB (micro units)
qprmS32AbsoluteOffset = 1 # Absolute camera offset (offset in CCD ADC)
qprmS32RegulatedCoolingTemp = 2

qprm64Exposure = 0 # Exposure in nanoseconds
qprm64ExposureRed = 1 # For LCD filter mode: exposure (ns) of red shot
qprm64ExposureBlue = 2 # For LCD filter mode: exposure (ns) of green shot
qprm64NormIntensGain = 3 # Normalized intensifier gain (micro units)

# Image formats
qfmtRaw8 = 0 #  Raw CCD output
qfmtRaw16 = 1 #  Raw CCD output
qfmtMono8 = 2 #  Data is bytes
qfmtMono16 = 3 #  Data is shorts, LSB aligned
qfmtBayer8 = 4 #  Bayer mosaic; data is bytes
qfmtBayer16 = 5 #  Bayer mosaic; data is shorts, LSB aligned
qfmtRgbPlane8 = 6 #  Separate color planes
qfmtRgbPlane16 = 7 #  Separate color planes
qfmtBgr24 = 8 #  Common Windows format
qfmtXrgb32 = 9 #  Format of Mac pixelmap
qfmtRgb48 = 10
qfmtBgrx32 = 11 #  Common Windows format
qfmtRgb24 = 12 #  RGB with no alpha

# callback flags
qcCallbackDone = 1 # Callback when QueueFrame (or QueueSettings) is done
qcCallbackExposeDone = 2 # Callback when exposure done (readout starts)
                         # model-B and all MicroPublishers only;
                         # callback is not guaranteed to occur

# ERROR HANDLING

_error_codes = {
    qerrSuccess: 'Success',
    qerrNotSupported: 'Function is not supported for this device',
    qerrInvalidValue: 'Invalid parameter value',
    qerrBadSettings: 'Bad QCam.Settings struct',
    qerrNoUserDriver: 'No user driver installed',
    qerrNoFirewireDriver: 'No firewire device driver installed',
    qerrDriverConnection: 'Error connecting to driver',
    qerrDriverAlreadyLoaded: 'Too many calls to QCam.LoadDriver()',
    qerrDriverNotLoaded: 'Did not call QCam.LoadDriver()',
    qerrInvalidHandle: 'Invalid QCam handle',
    qerrUnknownCamera: 'Camera type is unknown to this version of QCam',
    qerrInvalidCameraId: 'Invalid camera id used in QCam.OpenCamera()',
    qerrNoMoreConnections: 'Obsolete (no more connections)',
    qerrHardwareFault: 'Hardware fault',
    qerrFirewireFault: 'Firewire fault',
    qerrCameraFault: 'Camera fault',
    qerrDriverFault: 'Driver fault',
    qerrInvalidFrameIndex: 'Invalid frame index',
    qerrBufferTooSmall: 'Frame buffer is too small for image',
    qerrOutOfMemory: 'Out of memory',
    qerrOutOfSharedMemory: 'Out of shared memory',
    qerrBusy: 'Busy',
    qerrQueueFull: 'Cannot queue more items, queue is full',
    qerrCancelled: 'Cancelled',
    qerrNotStreaming: 'Streaming must be on before calling this command',
    qerrLostSync: 'This frame is trash, frame sync was lost',
    qerrBlackFill: 'This frame is damaged, some data is missing',
    qerrFirewireOverflow: 'Firewire overflow - restart streaming',
    qerrUnplugged: 'Camera has been unplugged or turned off',
    qerrAccessDenied: 'The camera is already open',
    qerrStreamFault: 'Stream Allocation Failed.  Is there enough Bandwidth',
    qerrQCamUpdateNeeded: 'QCam driver software is not recent enough for the camera',
    qerrRoiTooSmall: 'Region of interest is too small'
}

class Error(Exception):
    '''
    A QCam specific error
    '''
    def __init__(self, value):
        self.code = value
        if value in _error_codes:
            Exception.__init__(self,_error_codes[value])
        else:
            Exception.__init__(self,'Error: '+str(value))

def _check_error(errcode):
    if errcode != qerrSuccess:
        raise Error(errcode)

# Image format handling

_image_fmt_to_string_table = {
    qfmtRaw8:'raw8',
    qfmtRaw16:'raw16',
    qfmtMono8:'mono8',
    qfmtMono16:'mono16',
    qfmtBayer8:'bayer8',
    qfmtBayer16:'bayer16',
    qfmtRgbPlane8:'rgbPlane8',
    qfmtRgbPlane16:'rgbPlane16',
    qfmtBgr24:'bgr24',
    qfmtXrgb32:'xrgb32',
    qfmtRgb48:'rgb48',
    qfmtBgrx32:'bgrx32',
    qfmtRgb24:'rgb24'
    }

def image_fmt_to_string(qfmt):
    try:
        return _image_fmt_to_string_table[qfmt]
    except KeyError:
        return 'unknown'

_string_to_image_fmt_table = {
    'raw8':qfmtRaw8,
    'raw16':qfmtRaw16,
    'mono8':qfmtMono8,
    'mono16':qfmtMono16,
    'bayer8':qfmtBayer8,
    'bayer16':qfmtBayer16,
    'rgbPlane8':qfmtRgbPlane8,
    'rgbPlane16':qfmtRgbPlane16,
    'bgr24':qfmtBgr24,
    'xrgb32':qfmtXrgb32,
    'rgb48':qfmtRgb48,
    'bgrx32':qfmtBgrx32,
    'rgb24':qfmtRgb24
    }

def string_to_image_fmt(s):
    try:
        return _string_to_image_fmt_table[s]
    except KeyError:
        raise Error('Unknown image format: '+str(s))

# Settings class

# each tuple is (qprmValue, paramType, convFrom, convTo)
_settings_lookup = {
    'gain':(qprmGain,'u32',int,int),
    'offset':(qprmOffset,'u32',int,int),
    'exposure':(qprmExposure,'u32',int,int),
    'binning':(qprmBinning,'u32',int,int),
    'horizontalBinning':(qprmHorizontalBinning,'u32',int,int),
    'verticalBinning':(qprmVerticalBinning,'u32',int,int),
    'readoutSpeed':(qprmReadoutSpeed,'u32',int,int),
    'triggerType':(qprmTriggerType,'u32',int,int),
    'colorWheel':(qprmColorWheel,'u32',int,int),
    'coolerActive':(qprmCoolerActive,'u32',bool,int),
    'exposureRed':(qprmExposureRed,'u32',int,int),
    'exposureBlue':(qprmExposureBlue,'u32',int,int),
    'imageFormat':(qprmImageFormat,'u32',image_fmt_to_string,string_to_image_fmt),
    'roiX':(qprmRoiX,'u32',int,int),
    'roiY':(qprmRoiY,'u32',int,int),
    'roiWidth':(qprmRoiWidth,'u32',int,int),
    'roiHeight':(qprmRoiHeight,'u32',int,int),
    'reserved1':(qprmReserved1,'u32',int,int),
    'shutterState':(qprmShutterState,'u32',int,int),
    'reserved2':(qprmReserved1,'u32',int,int),
    'syncb':(qprmSyncb,'u32',int,int),
    'reserved3':(qprmReserved1,'u32',int,int),
    'intensifierGain':(qprmIntensifierGain,'u32',int,int),
    'triggerDelay':(qprmTriggerDelay,'u32',int,int),
    'cameraMode':(qprmCameraMode,'u32',int,int),
    'normalizedGain':(qprmNormalizedGain,'u32',int,int),
    'normIntensGaindB':(qprmNormIntensGaindB,'u32',int,int),
    'doPostProcessing':(qprmDoPostProcessing,'u32',bool,int),
    'postProcessGainRed':(qprmPostProcessGainRed,'u32',int,int),
    'postProcessGainGreen':(qprmPostProcessGainGreen,'u32',int,int),
    'postProcessGainBlue':(qprmPostProcessGainBlue,'u32',int,int),
    'postProcessBayerAlgorithm':(qprmPostProcessBayerAlgorithm,'u32',int,int),
    'postProcessImageFormat':(qprmPostProcessImageFormat,'u32',image_fmt_to_string,string_to_image_fmt),
    'fan':(qprmFan,'u32',int,int),
    'blackoutMode':(qprmBlackoutMode,'u32',bool,int),
    'highSensitivityMode':(qprmHighSensitivityMode,'u32',bool,int),
    'readoutPort':(qprmReadoutPort,'u32',int,int),
    'emGain':(qprmEMGain,'u32',int,int),
    'easyEmMode':(qprmEasyEmMode,'u32',bool,int), # 20160620: added because we needed to try this
    'openDelay':(qprmOpenDelay,'u32',int,int),
    'closeDelay':(qprmCloseDelay,'u32',int,int),
    'ccdClearingMode':(qprmCCDClearingMode,'u32',int,int),
    'normalizedGaindB':(qprmS32NormalizedGaindB,'s32',int,int), 
    'absoluteOffset':(qprmS32AbsoluteOffset,'s32',int,int), 
    'regulatedCoolingTemp':(qprmS32RegulatedCoolingTemp,'s32',int,int),
    'exposureNs':(qprm64Exposure,'u64',int,int), 
    'exposureRedNs':(qprm64ExposureRed,'u64',int,int), 
    'exposureBlueNs':(qprm64ExposureBlue,'u64',int,int), 
    'normIntensGain':(qprm64NormIntensGain,'u64',int,int), 
}

class Settings:
    def __init__(self, camera, settings):
        """
        Create a wrapper for camera settings

        camera - an instance of the QCam class
        settings - an opaque settings structure
        """
        import threading
        self._camera = camera
        self._settings = settings
        self.max = self.Maxes(self)
        self.min = self.Mins(self)
        self.valid = self.Valids(self)
        self._callback = AsyncCallback(self._settings_updated)
        # for keeping settings in flight
        self._settings_lock = threading.RLock()
        self._settings_queue = {}
        self._settings_num = 0

    def GetParam(self, paramKey):
        ulong = ctypes.c_ulong(0)
        _check_error(_dll.QCam_GetParam(ctypes.pointer(self._settings),
                                              paramKey,
                                              ctypes.pointer(ulong)))
        return ulong.value

    def GetParamS32(self, paramKey):
        slong = ctypes.c_long(0)
        _check_error(_dll.QCam_GetParamS32(ctypes.pointer(self._settings),
                                                 paramKey,
                                                 ctypes.pointer(slong)))
        return slong.value

    def GetParam64(self, paramKey):
        u64 = UNSIGNED64(0)
        _check_error(_dll.QCam_GetParam64(ctypes.pointer(self._settings),
                                                paramKey,
                                                ctypes.pointer(u64)))
        return u64.value

    def SetParam(self, paramKey, value):
        ulong = ctypes.c_ulong(value)
        _check_error(_dll.QCam_SetParam(ctypes.pointer(self._settings),
                                              paramKey,
                                              ulong))

    def SetParamS32(self, paramKey, value):
        slong = ctypes.c_long(value)
        _check_error(_dll.QCam_SetParamS32(ctypes.pointer(self._settings),
                                                 paramKey,
                                                 slong))

    def SetParam64(self, paramKey, value):
        u64 = ctypes.c_ulonglong(value)
        _check_error(_dll.QCam_SetParam64(ctypes.pointer(self._settings),
                                                paramKey,
                                                u64))

    def GetParamMin(self, paramKey):
        ulong = ctypes.c_ulong(0)
        _check_error(_dll.QCam_GetParamMin(ctypes.pointer(self._settings),
                                                 paramKey,
                                                 ctypes.pointer(ulong)))
        return ulong.value

    def GetParamS32Min(self, paramKey):
        slong = ctypes.c_long(0)
        _check_error(_dll.QCam_GetParamS32Min(ctypes.pointer(self._settings),
                                                    paramKey,
                                                    ctypes.pointer(slong)))
        return slong.value

    def GetParam64Min(self, paramKey):
        u64 = UNSIGNED64(0)
        _check_error(_dll.QCam_GetParam64Min(ctypes.pointer(self._settings),
                                                   paramKey,
                                                   ctypes.pointer(u64)))
        return u64.value
        
    def GetParamMax(self, paramKey):
        ulong = ctypes.c_ulong(0)
        _check_error(_dll.QCam_GetParamMax(ctypes.pointer(self._settings),
                                                 paramKey,
                                                 ctypes.pointer(ulong)))
        return ulong.value

    def GetParamS32Max(self, paramKey):
        slong = ctypes.c_long(0)
        _check_error(_dll.QCam_GetParamS32Max(ctypes.pointer(self._settings),
                                                    paramKey,
                                                    ctypes.pointer(slong)))
        return slong.value

    def GetParam64Max(self, paramKey):
        u64 = UNSIGNED64(0)
        _check_error(_dll.QCam_GetParam64Max(ctypes.pointer(self._settings),
                                                   paramKey,
                                                   ctypes.pointer(u64)))
        return u64.value

    def IsSparseTable(self, paramKey):
        return (_dll.QCam_IsSparseTable(ctypes.pointer(self._settings),
                                              paramKey) == qerrSuccess)

    def IsSparseTable64(self, paramKey):
        return (_dll.QCam_IsSparseTable64(ctypes.pointer(self._settings),
                                                paramKey) == qerrSuccess)
    
    def IsSparseTableS32(self, paramKey):
        return (_dll.QCam_IsSparseTableS32(ctypes.pointer(self._settings),
                                                 paramKey) == qerrSuccess)

    def GetParamSparseTable(self, paramKey, maxEntries):
        pSparseTable = (ctypes.c_ulong*maxEntries)(0)
        uSize = ctypes.c_int(maxEntries)
        _check_error(_dll.QCam_GetParamSparseTable(ctypes.pointer(self._settings),
                                                    paramKey,
                                                    pSparseTable,
                                                    ctypes.pointer(uSize)))
        return list(pSparseTable[0:uSize.value])

    def GetParamSparseTable64(self, paramKey, maxEntries):
        pSparseTable = (UNSIGNED64*maxEntries)(0)
        uSize = ctypes.c_int(maxEntries)
        _check_error(_dll.QCam_GetParamSparseTable64(ctypes.pointer(self._settings),
                                                      paramKey,
                                                      pSparseTable,
                                                      ctypes.pointer(uSize)))
        return list(pSparseTable[0:uSize.value])

    def GetParamSparseTableS32(self, paramKey, maxEntries):
        pSparseTable = (ctypes.c_long*maxEntries)(0)
        uSize = ctypes.c_int(maxEntries)
        _check_error(_dll.QCam_GetParamSparseTableS32(ctypes.pointer(self._settings),
                                                       paramKey,
                                                       pSparseTable,
                                                       ctypes.pointer(uSize)))
        return list(pSparseTable[0:uSize.value])

    def GetDefault(self):
        """
        Get the default settings
        """
        self._settings = self._camera.ReadDefaultSettings()

    def GetCamera(self):
        """
        Get the settings from the camera
        """
        self._settings = self._camera.ReadSettingsFromCam()

    def Flush(self):
        """
        Write the settings out to the camera
        """
        settings_copy = QCam_Settings()
        ctypes.memmove(ctypes.pointer(settings_copy),
                       ctypes.pointer(self._settings),
                       ctypes.sizeof(settings_copy))
        try:
            self._camera.SendSettingsToCam(settings_copy)
        except Error, e:
            if e.code == qerrBusy:
                self._settings_lock.acquire()
                self._settings_queue[self._settings_num] = settings_copy
                num = self._settings_num
                self._settings_num += 1
                self._settings_lock.release()
                self._camera.QueueSettings(self._callback,settings_copy,num)

    def _settings_updated(self, pointer, data, error, flags):
        """
        A callback to indicate settings updated
        """
        self._settings_lock.acquire()
        try:
            del self._setings_queue[data]
        except KeyError:
            pass
        self._settings_lock.release()

    class Maxes:
        def __init__(self, settings):
            self._settings = settings
        def __getattr__(self, name):
            if name in _settings_lookup:
                paramKey, paramType, convFrom, convTo = _settings_lookup[name]
                if paramType == 'u32':
                    return convFrom(self._settings.GetParamMax(paramKey))
                elif paramType == 's32':
                    return convFrom(self._settings.GetParamS32Max(paramKey))
                elif paramType == 'u64':
                    return convFrom(self._settings.GetParam64Max(paramKey))
                else:
                    raise Error('Unknown parameter type: '+str(paramType))
            else:
                raise AttributeError(name)
            
    class Mins:
        def __init__(self, settings):
            self._settings = settings
        def __getattr__(self, name):
            if name in _settings_lookup:
                paramKey, paramType, convFrom, convTo = _settings_lookup[name]
                if paramType == 'u32':
                    return convFrom(self._settings.GetParamMin(paramKey))
                elif paramType == 's32':
                    return convFrom(self._settings.GetParamS32Min(paramKey))
                elif paramType == 'u64':
                    return convFrom(self._settings.GetParam64Min(paramKey))
                else:
                    raise Error('Unknown parameter type: '+str(paramType))
            else:
                raise AttributeError(name)

    class Valids:
        def __init__(self, settings):
            self._settings = settings
        def __getattr__(self, name):
            if name in _settings_lookup:
                paramKey, paramType, convFrom, convTo = _settings_lookup[name]
                if paramType == 'u32':
                    rangeLow = self._settings.GetParamMin(paramKey)
                    rangeHigh = self._settings.GetParamMax(paramKey)
                    if not self._settings.IsSparseTable(paramKey):
                        return range(rangeLow,rangeHigh+1)
                    return [convFrom(x) for x in
                            self._settings.GetParamSparseTable(paramKey, rangeHigh-rangeLow+1)]
                elif paramType == 's32':
                    rangeLow = self._settings.GetParamMinS32(paramKey)
                    rangeHigh = self._settings.GetParamMaxS32(paramKey)
                    if not self._settings.IsSparseTable(paramKey):
                        return range(rangeLow,rangeHigh+1)
                    return [convFrom(x) for x in
                            self._settings.GetParamSparseTableS32(paramKey, rangeHigh-rangeLow+1)]
                elif paramType == 'u64':
                    rangeLow = self._settings.GetParamMin64(paramKey)
                    rangeHigh = self._settings.GetParamMax64(paramKey)
                    if not self._settings.IsSparseTable(paramKey):
                        return range(rangeLow,rangeHigh+1)
                    return [convFrom(x) for x in
                            self._settings.GetParamSparseTable64(paramKey, rangeHigh-rangeLow+1)]

    def __getattr__(self, name):
        if name in _settings_lookup:
            paramKey, paramType, convFrom, convTo = _settings_lookup[name]
            if paramType == 'u32':
                return convFrom(self.GetParam(paramKey))
            elif paramType == 's32':
                return convFrom(self.GetParamS32(paramKey))
            elif paramType == 'u64':
                return convFrom(self.GetParam64(paramKey))
            else:
                raise Error('Unknown parameter type: '+str(paramType))
        else:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in _settings_lookup:
            paramKey, paramType, convFrom, convTo = _settings_lookup[name]
            if paramType == 'u32':
                self.SetParam(paramKey,convTo(value))
            elif paramType == 's32':
                self.SetParamS32(paramKey,convTo(value))
            elif paramType == 'u64':
                self.SetParam64(paramKey,convTo(value))
            else:
                raise Error('Unknown parameter type: '+str(paramType))
        else:
            self.__dict__[name] = value
        
#
# INFO LOOKUP HANDLING
#

_info_lookup = {
    'cameraType':(qinfCameraType,camera_type_to_string),
    'serialNumber':(qinfSerialNumber,int),
    'hardwareVersion':(qinfHardwareVersion,int),
    'firmwareVersion':(qinfFirmwareVersion,int),
    'ccd':(qinfCcd,ccd_to_info),
    'bitDepth':(qinfBitDepth,int),
    'cooled':(qinfCooled,bool),
    'reserved1':(qinfReserved1,int),
    'imageWidth':(qinfImageWidth,int),
    'imageHeight':(qinfImageHeight,int),
    'imageSize':(qinfImageSize,int),
    'ccdType':(qinfCcdType,int),
    'ccdWidth':(qinfCcdWidth,int),
    'ccdHeight':(qinfCcdHeight,int),
    'firmwareBuild':(qinfFirmwareBuild,int),
    'uniqueId':(qinfUniqueId,int),
    'isModelB':(qinfIsModelB,bool),
    'intensifierModel':(qinfIntensifierModel,int),
    'exposureRes':(qinfExposureRes,int),
    'triggerDelayRes':(qinfTriggerDelayRes,int),
    'streamVersion':(qinfStreamVersion,int),
    'normGainSigFigs':(qinfNormGainSigFigs,int),
    'normGaindBRes':(qinfNormGaindBRes,int),
    'normITGainSigFigs':(qinfNormITGainSigFigs,int),
    'normITGaindBRes':(qinfNormITGaindBRes,int),
    'regulatedCooling':(qinfRegulatedCooling,bool),
    'regulatedCoolingLock':(qinfRegulatedCoolingLock,bool),
    'fanControl':(qinfFanControl,bool),
    'highSensitivityMode':(qinfHighSensitivityMode,bool),
    'blackoutMode':(qinfBlackoutMode,bool),
    'postProcessImageSize':(qinfPostProcessImageSize,int),
    'asymetricalBinning':(qinfAsymetricalBinning,bool),
    'asymmetricalBinning':(qinfAsymetricalBinning,bool),
    'emGain':(qinfEMGain,bool),
    'easyEmModeSupported':(qinfEasyEmModeSupported,bool),    
    'openDelay':(qinfOpenDelay,bool),
    'closeDelay':(qinfCloseDelay,bool),
}

class _InfoLookup:
    """
    A class that handles lazy information lookup from the camera
    """
    def __init__(self, camera):
        self._camera = camera

    def __getattr__(self, name):
        try:
            entry = _info_lookup[name]
        except KeyError:
            raise AttributeError(name)
        property, propertyType = entry[0:2]
        return propertyType(self._camera.GetInfo(property))

#
# THE FUNCTIONS
#

def LoadDriver():
    """
    Load the QCam driver.  Call before using any QCam Api functions.

    Raise an exception if the driver has already been loaded.
    """
    _check_error(_dll.QCam_LoadDriver())

def ReleaseDriver():
    """
    Release the QCam driver.
    """
    _dll.QCam_ReleaseDriver()

def LibVersion():
    """
    Get the version of this module (the QCam Driver).

    Returns a tuple of (major,minor,build)
    """
    verMajor = ctypes.c_ushort(0)
    verMinor = ctypes.c_ushort(0)
    verBuild = ctypes.c_ushort(0)
    verMajorPtr = ctypes.pointer(verMajor)
    verMinorPtr = ctypes.pointer(verMinor)
    verBuildPtr = ctypes.pointer(verBuild)
    _check_error(_dll.QCam_LibVersion(verMajorPtr,
                                            verMinorPtr,
                                            verBuildPtr))
    return (verMajor.value,
            verMinor.value,
            verBuild.value)

def ListCameras():
    """
    List the connected cameras

    Returns a list of QCam.CamListItem
    """
    # find out how many cameras are connected
    camList = CamListItem()
    pList = ctypes.pointer(camList)
    numberInList = ctypes.c_ulong(1)
    pNumberInList = ctypes.pointer(numberInList)
    # call the function
    _check_error(_dll.QCam_ListCameras(pList,
                                             pNumberInList))
    # create a camera list with the actual number of cameras
    arrayLength = numberInList.value
    pList = (CamListItem * arrayLength)()
    # call the function
    _check_error(_dll.QCam_ListCameras(pList,
                                             pNumberInList))
    # return a list of cameras
    num_cameras = min(numberInList.value,arrayLength)
    return list(pList[0:num_cameras])

def OpenCamera(camera):
    """
    Open a camera

    You can pass in either the camera id or a QCam.CamListItem
    """
    try:
        if 'cameraId' in dir(camera):
            # it's a CamListItem
            cameraId = int(camera.cameraId)
        else:
            cameraId = int(camera)
    except Exception, e:
        raise Error('Could not extract the cameraId out of the input argument: '+str(e))
    handle = QCam_Handle()
    pHandle = ctypes.pointer(handle)
    _check_error(_dll.QCam_OpenCamera(cameraId,
                                            pHandle))
    # return a new camera wrapper
    return QCam(handle)
            
#
# THE MAIN CLASS
#

class QCam:
    def __init__(self, handle):
        """
        Build a new QCam wrapper object.
        Do not call this directly, but use QCam.OpenCamera instead
        """
        self.handle = handle
        self.open = True
        # an info lookup object for easy looking up of read-only information about the camera
        self.info = _InfoLookup(self)
        # a basic settings object for easy settings
        self.settings = Settings(self, self.ReadDefaultSettings())
        #self.settings = Settings(self, self.ReadSettingsFromCam())
        

    def __del__(self):
        """
        Automagically call the CloseCamera method
        """
        self.Abort()
        self.CloseCamera()

    def CloseCamera(self):
        """
        Close the camera

        Will have no effect once the camera is closed
        """
        if self.open:
            _check_error(_dll.QCam_CloseCamera(self.handle))
            self.open = False
        
    def GetSerialString(self):
        """
        Get the serial string of the camera

        This function is not supported by cameras purchased before
        September 2002
        """
        string = ctypes.create_string_buffer(MAX_SERIAL_STRING_LENGTH)
        size = MAX_SERIAL_STRING_LENGTH
        _check_error(_dll.QCam_GetSerialString(self.handle,
                                                     string,
                                                     size))
        return string.value

    def GetInfo(self, parameter):
        """
        Get information from the camera based on the parameter based in.

        parameter is one of the QCam_Info enums

        For a higher level approach, use properties of the QCam.info property
        """
        value=ctypes.c_ulong(0)
        pValue=ctypes.pointer(value)
        _check_error(_dll.QCam_GetInfo(self.handle,
                                             parameter,
                                             pValue))
        return value.value

    def ReadDefaultSettings(self, settings=None):
        """
        Get the camera's default settings.
        Returns a low level opaque settings object

        Pass in a previously allocated settings object to overwrite it.
        """
        if not settings:
            settings = QCam_Settings()
        pSettings = ctypes.pointer(settings)
        _check_error(_dll.QCam_ReadDefaultSettings(self.handle,
                                                         pSettings))
        return settings

    def ReadSettingsFromCam(self, settings=None):
        """
        Read the camera settings.
        Returns a low level opaque settings object

        Pass in a previously allocated settings object to overwrite it.
        """
        if not settings:
            settings = QCam_Settings()
        pSettings = ctypes.pointer(settings)
        _check_error(_dll.QCam_ReadSettingsFromCam(self.handle,
                                                         pSettings))
        return settings        

    def SendSettingsToCam(self, settings):
        """
        Set the camera.  Your settings struct reflects any tweaking required
        (specifically, roi parameters).
        """
        pSettings = ctypes.pointer(settings)
        _check_error(_dll.QCam_SendSettingsToCam(self.handle,
                                                       pSettings))
        
    # TODO: Other settings functions

    def IsParamSupported(self, paramKey):
        """
        Returns True/False dependent on whether the parameter is supported
        """
        result = _dll.QCam_IsParamSupported(self.handle,
                                                  paramKey)
        if result == qerrSuccess:
            return True
        elif result == qerrNotSupported:
            return False
        else:
            _check_error(result)
    
    def IsParamS32Supported(self, paramKey):
        """
        Returns True/False dependent on whether the parameter is supported
        """
        result = _dll.QCam_IsParamS32Supported(self.handle,
                                                  paramKey)
        if result == qerrSuccess:
            return True
        elif result == qerrNotSupported:
            return False
        else:
            _check_error(result)

    def IsParam64Supported(self, paramKey):
        """
        Returns True/False dependent on whether the parameter is supported
        """
        result = _dll.QCam_IsParam64Supported(self.handle,
                                                    paramKey)
        if result == qerrSuccess:
            return True
        elif result == qerrNotSupported:
            return False
        else:
            _check_error(result)

    def SetStreaming(self, enable):
        """
        Start/stop firewire streaming.  The camera's firewire port
        must be streaming continuously to transmit an image.  If you
        call a Grab() function without firewire streaming on, the QCam
        driver will start streaming, capture the image, then stop
        streaming.  For higher frame rates, such as preview mode, it
        is an advantage to turn on firewire streaming manually.  (The
        disadvantage of firewire streaming when you are not capturing
        images: the OS must process empty firewire packets.)

        enable -- non-zero to enable streaming, zero to disable streaming
        """
        _check_error(_dll.QCam_SetStreaming(self.handle,
                                                  enable))

    def StartStreaming(self):
        """
        Start firewire streaming on the camera
        """
        self.SetStreaming(True)

    def StopStreaming(self):
        """
        Stop firewire streaming on the camera
        """
        self.SetStreaming(False)

    def Trigger(self):
        """
        Trigger an exposure to start (software trigger).  The trigger
        mode must be set to a hardware or software-only mode.  Firewire
        streaming must be started (see QCam_SetStreaming).

        You can guarantee that the frame resulting from QCam_Trigger
        was exposed after this function call was entered.

        WARNING: Software triggering is unreliable in model-A cameras!
        See SDK documentation.  If you need QCam_Trigger(), you should
        consider restricting your support to model-B cameras.
        (Model-A MicroPublishers also do not have reliable software
        triggering.)
        """
        _check_error(_dll.QCam_Trigger(self.handle))

    def Abort(self):
        """
        Stop all pending frame-grabs, and clear the queue.  You will
        not receive any more QueueFrame() and QueueSettings()
        callbacks after this function has returned.
        """
        _check_error(_dll.QCam_Abort(self.handle))
        
    def GrabFrame(self, frame=None):
        """
        Grab a frame from the camera and return a QCam.Frame structure

        frame -- A previously returned frame with allocated buffer
        """
        # allocate a new frame structure
        if not frame:
            frame = Frame()
            # find out how much space we need
            bufferSize = self.GetInfo(qinfImageSize)
            # allocate the buffer we need
            pBuffer = ctypes.create_string_buffer(bufferSize)
            # fill in the frame fields
            frame.bufferSize = bufferSize
            frame.pBuffer = ctypes.cast(pBuffer,ctypes.c_void_p)
            frame.stringBuffer = pBuffer
        # grab the frame
        _check_error(_dll.QCam_GrabFrame(self.handle,
                                               ctypes.pointer(frame)))
        return frame

    def QueueFrame(self, callback, frame=None, data=0, flags=qcCallbackDone):
        """
        Queue a frame buffer.  Returns the queued frame immediately.
        Callback occurs when the frame has been captured.

        The callback function is something like:

        def callback(pointer, data, error, flags):
            frame = ctypes.cast(pointer, ctypes.POINTER(Frame)).contents
            # do something with frame
        
        """
        # allocate a new frame structure
        if not frame:
            frame = Frame()
            # find out how much space we need
            bufferSize = self.GetInfo(qinfImageSize)
            # allocate the buffer we need
            pBuffer = ctypes.create_string_buffer(bufferSize)
            # fill in the frame fields
            frame.bufferSize = bufferSize
            frame.pBuffer = ctypes.cast(pBuffer,ctypes.c_void_p)
        # queue up a frame
        _check_error(_dll.QCam_QueueFrame(self.handle,
                                                ctypes.pointer(frame),
                                                ctypes.cast(callback,QCam_AsyncCallback),
                                                flags,
                                                ctypes.pointer(frame),
                                                data))
        return frame

    def QueueSettings(self, callback, settings, data=0, flags=qcCallbackDone):
        """
        Queue a change in camera settings.  Returns immediately.
        Callback occurs when the settings are changed.  Your settings
        structure must persist until the settings have been changed.
        """
        _check_error(_dll.QCam_QueueSettings(self.handle,
                                                   ctypes.pointer(settings),
                                                   ctypes.cast(callback,QCam_AsyncCallback),
                                                   flags,
                                                   ctypes.pointer(settings),
                                                   data))

class CameraQueue:
    """
    A frame queue for keeping track of frames in flight from the camera
    """

    Empty = Queue.Empty

    def __init__(self, camera):
        """
        Create a new FrameQueue object
        camera - An opened QCam camera
        size - The maximum number of frames in flight
        """
        self._queue = Queue.Queue(0)
        self.camera = camera
        self.lock = threading.RLock()
        self.frames = {} # frames indexed by pBuffer
        self.streaming = False
        self.paused = False
        self.callback = AsyncCallback(self._frame_arrived)

    def start(self, size=5):
        """Start streaming from the camera"""
        # clear the queue
        self.camera.Abort()
        # prepare the camera for stream capture by turning on streaming
        self.camera.StartStreaming()
        self.lock.acquire()
        self.streaming = True
        self.lock.release()
        # start the frames in flight
        if size < 2:
            raise Error('Must have at least two frames in flight')
        for i in range(size):
            self.put()

    def stop(self):
        """Stop streaming from the camera"""
        self.camera.Abort()
        self.camera.StopStreaming()
        self.lock.acquire()
        self.streaming = False
        self.frames = {} # remove pointers to the frames
        self.lock.release()
        # garbage collect the frame pointers
        gc.collect()

    def active(self):
        "Return whether streaming is currently active"
        self.lock.acquire()
        streaming = self.streaming
        self.lock.release()
        return streaming

    def pause(self):
        "Abort all the current frames in progress"
        self.lock.acquire()
        paused = self.paused
        self.lock.release()
        if paused:
            return # already paused
        self.camera.Abort()
        self.camera.StopStreaming()
        self.lock.acquire()
        self.paused = True
        self.lock.release()

    def unpause(self):
        "Recover from a pause"
        self.lock.acquire()
        paused = self.paused
        self.lock.release()
        if not paused:
            return # not paused
        # start streaming again
        self.camera.StartStreaming()
        self.lock.acquire()
        # queue up the previously queued frames
        frames = self.frames.values()
        self.lock.release()
        for frame in frames:
            self.put(frame)
        self.lock.acquire()
        self.paused = False
        self.lock.release()

    def paused(self):
        self.lock.acquire()
        paused = self.paused
        self.lock.release()
        return paused

    def __del__(self):
        # shut down camera streaming
        self.stop()

    def put(self, frame=None):
        """Add a frame, ready for capture, into the queue for the camera"""
        self.lock.acquire()
        streaming = self.streaming
        self.lock.release()
        if not streaming:
            return # discard the frame if not streaming
        # the gain-exposure product will determine relative intensity
        gainExposureFloat = 0.000001 * self.camera.settings.exposure * 0.000001 * self.camera.settings.normalizedGain
        gainExposure, = struct.unpack('L',struct.pack('f',gainExposureFloat))
        frame = self.camera.QueueFrame(self.callback, frame, gainExposure)
        # keep a reference to this frame so that it doesn't get deleted
        self.lock.acquire()
        if frame.pBuffer not in self.frames:
            self.frames[frame.pBuffer] = frame
        self.lock.release()

    def get(self, block=True, timeout=None):
        """Get a captured frame from the queue"""
        return self._queue.get(block,timeout)

    def frame_done(self):
        """Called to indicate that a frame is ready"""
        pass

    def _frame_arrived(self, pointer, data, error, flags):
        """Process a freshly arrived frame"""
        frame = ctypes.cast(pointer, ctypes.POINTER(Frame)).contents
        if error != qerrSuccess:
            raise Error(error)
        # recover the string buffer
        BufferType = ctypes.c_char * frame.bufferSize
        frame.stringBuffer = BufferType.from_address(frame.pBuffer)
        frame.formatString = image_fmt_to_string(frame.format)
        
        gainExposureFloat, = struct.unpack('f',struct.pack('L',data))
        frame.intensity = gainExposureFloat # normalized intensity of the frame
        
        # stick it into the output queue
        self._queue.put(frame)
        # frame ready
        self.frame_done()
