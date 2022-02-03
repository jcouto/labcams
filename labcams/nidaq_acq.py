# NIDAQ "CAMERA" for logging syncronization triggers using NIDAQ X series hardware
import threading
import nidaqmx
from nidaqmx.stream_readers import AnalogMultiChannelReader,AnalogUnscaledReader
from nidaqmx.stream_readers import DigitalMultiChannelReader
from .cams import *

# this only reads data for now.
class NIDAQ(object): 
    def __init__(self, device = "dev2",
                 srate = 25000,
                 digital = {"P0.0":"P0.0"},
                 analog = {"ai0":"ai0"},
                 ai_range = [-5,5],
                 dtype = 'int16',
                 triggered = Event(),
                 recorderpar = None,
                 **kwargs):
        '''
        Recorder parameters must be a dict(filename,pathformat,dataname,datafolder)
        '''
        # Events to interface with cameras
        self.camera_ready = Event()
        self.close_event = Event()
        self.start_trigger = Event()
        self.stop_trigger = Event()
        self.saving = Event()
        self.eventsQ = Queue() # not used now.
        
        self.device = device
        self.task_ai = None
        self.task_di = None
        self.ai_range = ai_range
        self.digital_channels = digital
        self.analog_channels = analog
        self.ai_num_channels = len(analog)
        self.di_num_channels = len(digital)
        
        self.triggered = triggered
        self.recorderpar = recorderpar
        self.srate = srate
        self.samps_per_chan = 1000

        self.task_clock = nidaqmx.Task()
        self.task_clock.co_channels.add_co_pulse_chan_freq(
            self.device + '/ctr0',freq = self.srate)
        self.samp_clk_terminal = '/{0}/Ctr0InternalOutput'.format(self.device)
        self.task_clock.timing.cfg_implicit_timing(
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=self.samps_per_chan)
        self.recorderpar = recorderpar
        self.dataname = None
        for aich in self.analog_channels.keys():
            chanstr = '{0}/{1}'.format(self.device,aich)
            if self.task_ai is None:
                self.task_ai = nidaqmx.Task()
            self.task_ai.ai_channels.add_ai_voltage_chan(
                chanstr,
                min_val = ai_range[0],
                max_val = ai_range[1])
        if self.di_num_channels:      # then there are channels (need to find out the ports)
            if self.task_di is None:
                self.task_di = nidaqmx.Task()
            dinames = [n[:2] for n in self.digital_channels.keys()]
            # one channel per port
            diports = np.unique(dinames)
            for diport in diports:
                chanstr = '{0}/{1}'.format(self.device,diport.replace("P","port"))
                self.task_di.di_channels.add_di_chan(
                    chanstr,
                    line_grouping = nidaqmx.constants.LineGrouping.CHAN_FOR_ALL_LINES)
            self.di_num_channels = len(diports)

        if not self.task_ai is None:
            self.task_ai.timing.cfg_samp_clk_timing(
                self.srate,
                source=self.samp_clk_terminal,
                active_edge=nidaqmx.constants.Edge.FALLING,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                samps_per_chan=self.samps_per_chan)
            self.ai_reader = AnalogUnscaledReader(self.task_ai.in_stream)
            #AnalogMultiChannelReader(self.task_ai.in_stream)

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
        self.data_buffer = np.zeros((self.ai_num_channels+self.di_num_channels,
                                     self.srate),
                                    dtype='int16')
    def _waitsoftwaretrigger(self):
        '''wait for software trigger'''
        display('[{0}] waiting for software trigger.'.format('nidaq'))
        while not self.start_trigger.is_set() or self.stop_trigger.is_set():
            # limits resolution to 1 ms 
            time.sleep(0.001)
            if self.close_event.is_set() or self.stop_trigger.is_set():
                break
        if self.close_event.is_set() or self.stop_trigger.is_set():
            return
        self.camera_ready.clear()
    def _daq_init(self):
        if not self.task_ai is None:
            self.task_ai.start()
        if not self.task_di is None:
            self.task_di.start()
        if not self.task_clock is None:
            display("NIDAQ acquisition starting.")
            self.task_clock.start()
        self.n_ai_samples = 0
        self.n_di_samples = 0
        
        self.ai_reader.read_all_avail_samp = True
        self.di_reader.read_all_avail_samp = True

    def start(self):
        def run_thread():
            while not self.close_event.is_set():
                self.camera_ready.set()
                self._waitsoftwaretrigger()
                self._daq_init()
                ai_buffer = np.zeros((self.ai_num_channels,self.samps_per_chan),
                                     dtype = np.int16)
                di_buffer = np.zeros((self.di_num_channels,self.samps_per_chan),
                                     dtype = np.uint32)

                self.ibuff = int(0)
                while not self.stop_trigger.is_set():
                    di_nsamples = 0
                    ai_nsamples = 0
                    if not self.task_ai is None:
                        ai_nsamples = self.ai_reader.read_int16(
                            ai_buffer,
                            number_of_samples_per_channel = self.samps_per_chan,
                            timeout = 2)
                        #ai_nsamples = self.ai_reader.read_many_sample(
                        #    ai_buffer,
                        #    number_of_samples_per_channel = self.samps_per_chan,
                        #    timeout = 2)
                        self.n_ai_samples += ai_nsamples
                    if not self.task_di is None:
                        di_nsamples = self.di_reader.read_many_sample_port_uint32(
                            di_buffer,
                            number_of_samples_per_channel = self.samps_per_chan,
                            timeout = 2)
                        self.n_di_samples += di_nsamples

                    databuffer = np.vstack([ai_buffer,di_buffer.astype('int16')])
                    nsampl = databuffer.shape[1]
                    self.data_buffer[:] = np.roll(self.data_buffer, -nsampl,
                                                  axis = 1)[:]
                    self.data_buffer[:,-nsampl:] = databuffer[:]
                
                    if not self.start_trigger.is_set():
                        self.stop_acquisition()

                if not self.task_clock is None:
                    self.task_clock.stop()
                if not self.task_ai is None:
                    #self.task_ai.wait_until_done()
                    self.task_ai.stop()
                if not self.task_di is None:
                    #self.task_di.wait_until_done()
                    self.task_di.stop()
                self.stop_trigger.clear()
                self.camera_ready.clear()
                if self.close_event.is_set():
                    break

            display('Closed DAQ')
        self.thread_task = threading.Thread(target = run_thread)
        self.thread_task.start()
        return

    def stop_acquisition(self):
        self.stop_trigger.set()

    def close(self):
        self.close_event.set()
        self.stop_acquisition()

    def join(self):
        pass

    def stop_saving(self):
        pass
