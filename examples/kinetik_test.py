import time
import numpy as np

from pyvcam import pvc
from pyvcam.camera import Camera
from pyvcam import constants
import signal

def main():
    pvc.init_pvcam()
    cam = next(Camera.detect_camera())
    cam.open()
    cam.meta_data_enabled = True
    cam.start_live(exp_time=10, buffer_frame_count = 100)
    nframes = 0
    nframes_camera = 0
    isrunning = [True]
    def stop_handler(signum,frame):
        print('Stopping.')
        isrunning[0] = False
    print('press ctr+c to stop')
    signal.signal(signal.SIGINT, stop_handler)
    while isrunning[0]:
        frame, fps, frame_count = cam.poll_frame(oldestFrame = True)
        nframes += 1
        frame_num = frame['meta_data']['frame_header']['frameNr']
        if nframes_camera+1 !=  frame_num:
            print('Skipped frame: expected {0}, got {1}'.format(
                nframes_camera, frame_num))
        nframes_camera = frame_num
        
    cam.finish()
    cam.close()
    pvc.uninit_pvcam()

    print('Total frames seen: {}'.format(nframes))
    print('Total frames count by the camera: {}\n'.format(nframes_camera))
    print('Lost {0} frames?'.format(nframes_camera - nframes))


if __name__ == "__main__":
    main()
