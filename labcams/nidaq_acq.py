# NIDAQ "CAMERA" for logging syncronization triggers using NIDAQ X series hardware
import threading
import nidaqmx
from nidaqmx.stream_readers import AnalogMultiChannelReader,AnalogUnscaledReader
from nidaqmx.stream_readers import DigitalMultiChannelReader
from .cams import *

def unpackbits(x,num_bits = 32):
    '''
    unpacks numbers in bits from the port.
    '''
    xshape = list(x.shape)
    x = x.reshape([-1,1])
    to_and = 2**np.arange(num_bits).reshape([1,num_bits])
    return (x & to_and).astype(bool).astype(int).reshape(xshape + [num_bits]).squeeze().transpose()

# this only reads data for now.
class NIDAQ(object): 
    def __init__(self, device = "dev2",
                 srate = 25000,
                 digital = {"P0.0":"P0.0"},
                 analog = {},
                 ai_range = [-5,5],
                 dtype = 'int16',
                 start_trigger = None,
                 stop_trigger = None,
                 save_trigger = None,
                 triggered = Event(),
                 recorderpar = None,
                 **kwargs):
        '''
        Recorder parameters must be a dict(filename,pathformat,dataname,datafolder)
        '''
        # Events to interface with cameras
        self.camera_ready = Event()
        self.close_event = Event()
        self.eventsQ = Queue() # not used now.
        self.recorder = None # not used now.
        self.device = device
        self.task_ai = None
        self.task_di = None
        self.start_trigger = start_trigger
        self.stop_trigger = stop_trigger
        self.save_trigger = save_trigger

        if self.start_trigger is None:
            self.start_trigger = Event()
        if self.stop_trigger is None:
            self.stop_trigger = Event()
        if self.save_trigger is None:
            self.save_trigger = Event()
        self.ai_range = ai_range
        self.digital_channels = digital
        self.analog_channels = analog
        self.ai_num_channels = len(analog)
        self.di_num_channels = len(digital)
        self.di_port_channels = []
        self.triggered = triggered
        self.recorderpar = recorderpar
        self.srate = srate
        self.samps_per_chan = int(self.srate/5)
        self.was_saving = False
        
        self.task_clock = nidaqmx.Task()
        self.task_clock.co_channels.add_co_pulse_chan_freq(
            self.device + '/ctr0',freq = self.srate)
        self.samp_clk_terminal = '/{0}/Ctr0InternalOutput'.format(self.device)
        self.task_clock.timing.cfg_implicit_timing(
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=self.samps_per_chan)
        self.recorderpar = dict(recorderpar,**kwargs)
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
            for io,diport in enumerate(diports):
                chanstr = '{0}/{1}'.format(self.device,diport.replace("P","port"))
                self.task_di.di_channels.add_di_chan(
                    chanstr,
                    line_grouping = nidaqmx.constants.LineGrouping.CHAN_FOR_ALL_LINES)
                for o in self.digital_channels.keys():
                    if o.startswith(diport):
                        self.di_port_channels.append(io*8 + int(o.split('.')[-1]))
            
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
        self.data_buffer = np.zeros((self.ai_num_channels+len(self.di_port_channels),
                                     self.srate),
                                    dtype='int16')
    def _start_recorder(self):
        if not self.recorderpar is None:
            from .io import BinaryDAQWriter
            self.recorder = BinaryDAQWriter(self,
                                            incrementruns = True,
                                            **self.recorderpar)
            
    def _waitsoftwaretrigger(self):
        '''wait for software trigger'''
        display('[{0}] waiting for software trigger.'.format('nidaq'))
        while (not self.start_trigger.is_set()):
            # limits resolution to 1 ms 
            time.sleep(0.001)
            self._parse_command_queue()
            if self.was_saving:
                display("Closing nidaq file.")
                self.recorder.close_run()
                self.was_saving = False
            if self.close_event.is_set() or self.stop_trigger.is_set():
                display('[{0}] stop_trigger set.'.format('nidaq'))
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

    def _parse_command_queue(self):
        if not self.eventsQ.empty():
            cmd = self.eventsQ.get()
            if '=' in cmd:
                cmd = cmd.split('=')
                if hasattr(self,'ctrevents'):
                    self._call_event(cmd[0],cmd[1])
                if cmd[0] == 'filename':
                    if not self.recorder is None:
                        if hasattr(self,'recorder'):
                            self.recorder.set_filename(cmd[1])
                    self.recorderpar['filename'] = cmd[1]

    def start(self):
        def run_thread():
            self._start_recorder()
            while not self.close_event.is_set():
                self.camera_ready.set()
                self._waitsoftwaretrigger()
                self._daq_init()
                ai_buffer = np.zeros((self.ai_num_channels,self.samps_per_chan),
                                     dtype = np.int16)
                di_buffer = np.zeros((self.di_num_channels,self.samps_per_chan),
                                     dtype = np.uint32)

                self.ibuff = int(0)
                self._parse_command_queue()
                while not self.stop_trigger.is_set():
                    self._parse_command_queue()
                    di_nsamples = 0
                    ai_nsamples = 0
                    if not self.task_ai is None:
                        ai_nsamples = self.ai_reader.read_int16(
                            ai_buffer,
                            number_of_samples_per_channel = self.samps_per_chan,
                            timeout = 1)
                        #ai_nsamples = self.ai_reader.read_many_sample(
                        #    ai_buffer,
                        #    number_of_samples_per_channel = self.samps_per_chan,
                        #    timeout = 2)
                        self.n_ai_samples += ai_nsamples
                    if not self.task_di is None:
                        di_nsamples = self.di_reader.read_many_sample_port_uint32(
                            di_buffer,
                            number_of_samples_per_channel = self.samps_per_chan,
                            timeout = 1)
                        self.n_di_samples += di_nsamples

                    databuffer = np.hstack([ai_buffer.T,di_buffer.astype('int16').T])
                    if self.save_trigger.is_set():
                        self.was_saving = True
                        if not self.recorder is None:
                            self.recorder.save(np.ascontiguousarray(databuffer))
                    elif self.was_saving:
                        display("Closing file")
                        self.recorder.close_run()
                        self.was_saving = False
                    databuffer = databuffer.T
                    nsampl = databuffer.shape[1]
                    if not self.task_di is None:
                        # send it to the plot-buffer...
                        tmp = unpackbits(
                            di_buffer,
                            32)
                        databuffer = np.vstack([ai_buffer,tmp[self.di_port_channels].astype('int16')])

                    self.data_buffer[:] = np.roll(self.data_buffer, -nsampl,
                                                  axis = 1)[:]
                    self.data_buffer[:,-nsampl:] = databuffer[:]

                    if not self.start_trigger.is_set() and not self.stop_trigger.is_set():
                        self._cam_stopacquisition()
                if not self.task_clock is None:
                    self.task_clock.stop()
                if not self.task_ai is None:
                    #self.task_ai.wait_until_done()
                    self.task_ai.stop()
                if not self.task_di is None:
                    #self.task_di.wait_until_done()
                    self.task_di.stop()
                self.start_trigger.clear()
                self.stop_trigger.clear()
                self.camera_ready.clear()
                if self.close_event.is_set():
                    break
            if not self.task_di is None:
                self.task_di.close()
            if not self.task_ai is None:
                self.task_ai.close()
            if not self.task_clock is None:
                self.task_clock.close()                
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
        self.save_trigger.clear()
