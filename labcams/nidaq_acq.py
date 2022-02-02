# NIDAQ "CAMERA" for logging syncronization triggers using NIDAQ X series hardware
import threading
import nidaqmx
from nidaqmx.stream_readers import AnalogMultiChannelReader
from nidaqmx.stream_readers import DigitalMultiChannelReader
from .cams import *

# this only reads data for now.
class NIDAQ(object): 
    def __init__(self, device = "dev2",
                 srate = 25000,
                 channels = ['ai0','ai1','port0'],
                 ai_range = [-5,5],
                 triggered = Event(),
                 recorderpar = None,
                 **kwargs):
        '''
        Recorder parameters must be a dict(filename,pathformat,dataname,datafolder)
        '''
        self.device = device
        self.task_ai = None
        self.task_di = None
        self.channels = channels
        self.ai_range = ai_range
        self.ai_num_channels = 0
        self.di_num_channels = 0
                    
        self.triggered = triggered
        self.recorder = recorder
        self.srate = srate
        self.samps_per_chan = 10000

        self.task_clock = nidaqmx.Task()
        self.task_clock.co_channels.add_co_pulse_chan_freq(
            self.device + '/ctr0',freq = self.srate)
        self.samp_clk_terminal = '/{0}/Ctr0InternalOutput'.format(self.device)
        self.task_clock.timing.cfg_implicit_timing(
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=self.samps_per_chan)
        self.recorderpar = recorderpar
        self.dataname = None
        
        for ch in self.channels:
            chanstr = '{0}/{1}'.format(self.device,ch)
            if 'ai' in ch:
                if self.task_ai is None:
                    self.task_ai = nidaqmx.Task()
                self.task_ai.ai_channels.add_ai_voltage_chan(
                    chanstr,
                    min_val = ai_range[0],
                    max_val = ai_range[1])
                self.ai_num_channels += 1
            if 'port' in ch:
                if self.task_di is None:
                    self.task_di = nidaqmx.Task()
                self.task_di.di_channels.add_di_chan(
                    chanstr,
                    line_grouping = nidaqmx.constants.LineGrouping.CHAN_FOR_ALL_LINES)
                self.di_num_channels += 1

        if not self.task_ai is None:
            self.task_ai.timing.cfg_samp_clk_timing(
                self.srate,
                source=self.samp_clk_terminal,
                active_edge=nidaqmx.constants.Edge.FALLING,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                samps_per_chan=self.samps_per_chan)
            self.ai_reader = AnalogMultiChannelReader(self.task_ai.in_stream)

        if not self.task_di is None:
            self.task_di.timing.cfg_samp_clk_timing(
                rate = self.srate,
                source = self.samp_clk_terminal,
                active_edge=nidaqmx.constants.Edge.FALLING,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                samps_per_chan = self.samps_per_chan)
            self.di_reader = DigitalMultiChannelReader(self.task_di.in_stream)
        self.data =  np.zeros((self.ai_num_channels+self.di_num_channels,self.srate),
                              dtype = np.float64)
        self.daq_acquiring = False

    def start(self):
        if not self.task_ai is None:
            self.task_ai.start()
        if not self.task_di is None:
            self.task_di.start()
        if not self.task_clock is None:
            print("Clock starting")
            self.task_clock.start()
        self.n_ai_samples = 0
        self.n_di_samples = 0

        def run_thread():
            self.ai_reader.read_all_avail_samp = True
            self.di_reader.read_all_avail_samp = True
            print('Starting thread')
            ai_buffer = np.zeros((self.ai_num_channels,self.samps_per_chan),
                              dtype = np.float64)
            di_buffer = np.zeros((self.di_num_channels,self.samps_per_chan),
                                 dtype = np.uint32)

            self.daq_acquiring = True

            while self.daq_acquiring:
                if not self.task_ai is None:
                    ai_nsamples = self.ai_reader.read_many_sample(
                        ai_buffer,
                        number_of_samples_per_channel = self.samps_per_chan,
                        timeout = 1)
                    self.n_ai_samples += ai_nsamples

                if not self.task_di is None:
                    di_nsamples = self.di_reader.read_many_sample_port_uint32(
                        di_buffer,
                        number_of_samples_per_channel = self.samps_per_chan,
                        timeout = 1)
                    print(di_buffer,flush=True)
                    print(di_nsamples,flush=True)
                    self.n_di_samples += di_nsamples
                    
            if not self.task_clock is None:
                self.task_clock.stop()
            if not self.task_ai is None:
                #self.task_ai.wait_until_done()
                self.task_ai.stop()
            if not self.task_di is None:
                #self.task_di.wait_until_done()
                self.task_di.stop()
        self.thread_task = threading.Thread(target = run_thread)
        self.thread_task.start()
        return

    def stop(self):
        self.daq_acquiring = False
