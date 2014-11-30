####
#
# program to read heart rate data from a COM port ((from pulse sensor via Arduino, see http://pulsesensor.myshopify.com/)
#
# the x-axis is just taken from the current computer time.
# this can be improved when ones takes the time from arduino (either by sending time date from the arduino, or just using the IBI values (they provide time deltas between data points))
#
# these are the things sent by Arduino:
#   sensor: the raw sensor data
#   IBI: inter beat interval in ms
#   beats: heart rate (average of last 10 beats)
#
#
# todo:
#   - real time axis (plot/input of data is now tied to current local time, should be tied to microprocessor time)
#
# A. Riss, 2014
#
####


# config

CFG_comport = 'COM3'
CFG_baudrate = 115200
CFG_serial_timeout = 1


CFG_maxpoints        = {'sensor': 50000, 'beats': 10000, 'IBI': 10000} # max data points for sensor data, heart beats, inter-beat distances
CFG_default_y        = {'sensor': 500.007007, 'beats': 0.007007, 'IBI': 500.007007}   # i use some special values so that I know afterwards that these are the default values (a bit of a dirty hack)
CFG_default_y        = {'sensor': None, 'beats': None, 'IBI': None}   # i use some special values so that I know afterwards that these are the default values (a bit of a dirty hack)

CFG_max_runtime = 120  # stops after so many seconds

CFG_graph_span_min   = 0.15   # x axis span of the graph in minutes

CFG_figsize = (14,8)

CFG_default_fontsize = 14

CFG_text_fontsize = {'HR': 16, 'HR_mean_all': 16, 'HR_mean_10': 16, 'HR_description':9, 'HR_description_big':12, 'beats': 16, 'IBI': 16,  'time': 14, 'HRV_descriptors': 12, 'HRV_descriptors_norm': 9}
CFG_text_color    = {'HR': '#E53935', 'HR_mean_all': '#E53935', 'HR_mean_10': '#E53935', 'beats': '#3F51B5', 'IBI': '#00695C',  'time': '#A0A0A0', 'HRV_descriptors': '#FFFFFF', 'HRV_descriptors_norm': '#A0A0A0'}

CFG_plot_color    = {'HR': '#A53935', 'IBI': '#00695C', 'HRV_descriptors': '#3F51B5'}

CFG_title_fontsize = 16
CFG_title_color = '#000000'

CFG_no_arduino = True   # do not connect to arduino, read data from file (for testing)
CFG_save_dump = False     # save arduino data to file (for later offline testing)
CFG_temp_file = 'temp.txt'  # store temp data here (if we do not want to re-record from arduino)

CFG_hrv_descriptors = ['HRMean', 'HRSTD', 'rMSSD', 'pNN50', 'VLF', 'LF', 'HF', 'LFHF', 'Power']  # gives the order
CFG_hrv_descriptors_labels = {'HRMean': 'HR Mean', 'HRSTD': 'HR STD', 'rMSSD': 'rMSSD', 'pNN50': 'pNN50', 'VLF': 'VLF', 'LF': 'LF', 'HF': 'HF', 'LFHF': 'LFHF', 'Power': 'Power'}
CFG_hrv_descriptors_units = {'HRMean': 'Hz', 'HRSTD': 'Hz', 'rMSSD': 'ms', 'pNN50': '%', 'VLF': 'ms2', 'LF': 'ms2', 'HF': 'ms2', 'LFHF': '', 'Power': 'ms2'}
CFG_hrv_descriptors_format = {'HRMean': '%0.1f', 'HRSTD': '%0.1f', 'rMSSD': '%0.1f', 'pNN50': '%0.1f', 'VLF': '%0.1f', 'LF': '%0.1f', 'HF': '%0.1f', 'LFHF': '%0.2f', 'Power': '%0.1f'}
CFG_hrv_descriptors_standard = {'HRMean': 75, 'HRSTD': 4, 'rMSSD': 51.7, 'pNN50': 12.3, 'VLF': 2437.2, 'LF': 2234.3, 'HF': 1442.6, 'LFHF': 1.75, 'Power': 6120.2}  # standard values for hrv descriptors (from http://www.hrv24.de/HRV-Interpretation.htm), HRSTD is made up

CFG_hrv_descriptors_log_base = 4  # for dynamic adjustment of bar plot  for hrv descriptors


import serial
import numpy as np
import matplotlib.pyplot as plt 
import matplotlib.animation as animation
import matplotlib.dates
import datetime
import pickle
import math

import hrv_analysis

matplotlib.rcParams.update({'font.size': CFG_default_fontsize})
    
# plot class
class HRVplot:

    def __init__(self, comport, baudrate, timeout):
    
        # setup data
        
        self.x = {}
        self.y = {}
        self.date_start = datetime.datetime.now()
        self.date_start_num = matplotlib.dates.date2num(self.date_start)
        
        self.hrv_descriptors = []  # list of all past dictionaries
        self.hrv_descriptors_plot_norm2 = {}  # normalize bar width (for plotting), defined in powers of CFG_hrv_descriptors_log_base
        
        self.num_points = {'sensor': 0, 'beats': 0, 'IBI': 0}

        for sym in ['sensor', 'beats', 'IBI']:
            self.y[sym] = np.empty(CFG_maxpoints[sym])
            self.y[sym].fill(CFG_default_y[sym])
            self.x[sym] = np.empty(CFG_maxpoints[sym])
            self.x[sym].fill(self.date_start_num)
        
        # setup figure/plots
        
        self.fig = plt.figure(num=None, figsize=CFG_figsize, facecolor='w', edgecolor='k')
        gs = matplotlib.gridspec.GridSpec(2, 2, width_ratios=[3,1.5], height_ratios=[1,1])

        self.ax = {}
        self.ax['sensor'] = self.fig.add_subplot(gs[0,0], xlim=(self.date_start_num, self.date_start_num+1.0/24/60/60), ylim=(0, 1023))    # 1 second span in for the x-axis
        self.ax['sensor'].xaxis_date()
        #self.ax['beats'] = plt.axes(xlim=(0, CFG_maxpoints_beats), ylim=(0, 220))
        self.ax['IBI']    = self.fig.add_subplot(gs[1,0], sharex=self.ax['sensor'], ylim=(0, 1000))
        
        self.ax['HRV_descriptors'] = self.fig.add_subplot(gs[:,1])
        
        self.plots = {}
        self.plots['sensor'], = self.ax['sensor'].plot(self.x['sensor'], self.y['sensor'], color=CFG_plot_color['HR'], linewidth=2)
        #self.plots['beats'],  = self.ax['beats'].plot(self.x['beats'], self.y['beats'])
        self.plots['IBI'],    = self.ax['IBI'].plot(self.x['IBI'], self.y['IBI'], color=CFG_plot_color['IBI'], linewidth=2)
        
        dummy_plot, = self.ax['sensor'].plot(self.date_start_num, 500)  # some dummy plot to prevent scaling errors before any real data exists
        dummy_plot2, = self.ax['IBI'].plot(self.date_start_num, 500)  # some dummy plot to prevent scaling errors before any real data exists

        # setup captions
        
        self.text_val = {}
        for sym in ['sensor', 'IBI']:
            self.ax[sym].autoscale(enable=True, axis='y', tight=False)
            self.ax[sym].set_ymargin(0.5)
            self.ax[sym].set_autoscaley_on(True)

        self.text_IBI = self.ax['IBI'].text(1.0, 1.0, ' ', horizontalalignment='right', verticalalignment='top', transform=self.ax['IBI'].transAxes, fontsize=CFG_text_fontsize['IBI'], color=CFG_text_color['IBI'], fontweight='bold')
        
        self.text_HR = self.ax['sensor'].text(1.0, 1.0, ' ', horizontalalignment='right', verticalalignment='top', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['HR'], color=CFG_text_color['HR'], fontweight='bold')
        self.text_HR_mean_10 = self.ax['sensor'].text(0.92, 1.0, ' ', horizontalalignment='right', verticalalignment='top', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['HR_mean_10'], color=CFG_text_color['HR'], fontweight='bold', alpha=0.6)
        self.text_HR_mean_all = self.ax['sensor'].text(0.84, 1.0, ' ', horizontalalignment='right', verticalalignment='top', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['HR_mean_all'], color=CFG_text_color['HR'], fontweight='bold', alpha=0.3)
        
        self.ax['sensor'].text(1.0, 0.92, '$\heartsuit$', horizontalalignment='right', verticalalignment='top', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['HR_description_big'], color=CFG_text_color['HR'])
        self.ax['sensor'].text(0.92, 0.92, 'last 10', horizontalalignment='right', verticalalignment='top', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['HR_description'], color=CFG_text_color['HR'], alpha=0.6)
        self.ax['sensor'].text(0.84, 0.92, 'all', horizontalalignment='right', verticalalignment='top', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['HR_description'], color=CFG_text_color['HR'], alpha=0.3)

        pos = range(len(CFG_hrv_descriptors))
        vals = [1] * len(CFG_hrv_descriptors)
        labels = []
        self.hrv_text = {}
        self.hrv_text_norm = {}
        i=0
        for k in CFG_hrv_descriptors:
            labels.append(CFG_hrv_descriptors_labels[k])
            self.hrv_text[k] = plt.annotate("", xy=(vals[-1] + 0.1, pos[len(vals)-1]), va='center', ha='right', color=CFG_text_color['HRV_descriptors'], fontsize=CFG_text_fontsize['HRV_descriptors'])
            self.hrv_text_norm[k] = plt.annotate("", xy=(0.02, pos[i]-0.132), va='bottom', color=CFG_text_color['HRV_descriptors_norm'], fontsize=CFG_text_fontsize['HRV_descriptors_norm'])
            i+=1
    
        self.plots['HRV_descriptors'] = self.ax['HRV_descriptors'].barh(pos, vals, align='center', color=CFG_plot_color['HRV_descriptors'], height=0.75, edgecolor = "none")
        self.ax['HRV_descriptors'].set_yticks(pos)
        self.ax['HRV_descriptors'].set_yticklabels(labels)
        self.ax['HRV_descriptors'].set_ylim([len(CFG_hrv_descriptors)-1+0.385, -0.385])
        self.ax['HRV_descriptors'].set_xlim([0, CFG_hrv_descriptors_log_base+0.05])
        for t in self.ax['HRV_descriptors'].yaxis.get_ticklines(): t.set_visible(False) 
        
        #self.text_time = self.ax['sensor'].text(1, 1.06, ' ', horizontalalignment='right', verticalalignment='bottom', transform=self.ax['sensor'].transAxes, fontsize=CFG_text_fontsize['time'], color=CFG_text_color['time'], fontweight='bold')
        #self.text_time = self.ax['HRV_descriptors'].text(1, 0.20, ' ', horizontalalignment='right', verticalalignment='bottom', transform=self.ax['HRV_descriptors'].transAxes, fontsize=CFG_text_fontsize['time'], color=CFG_text_color['time'], fontweight='normal')
        self.text_time = self.fig.text(0.99, 0.985, ' ', horizontalalignment='right', verticalalignment='top', fontsize=CFG_text_fontsize['time'], color=CFG_text_color['time'], fontweight='normal')
        self.text_title = self.fig.text(0.01, 0.985, 'Heart rate measurement', horizontalalignment='left', verticalalignment='top', fontsize=CFG_title_fontsize, color=CFG_title_color, fontweight='bold')

        self.ax['IBI'].xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Mm %Ss'))
        self.ax['IBI'].xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(interval_multiples=True, minticks=2, maxticks=4))
        
        self.ax['sensor'].set_ylabel("sensor [a.u.]")
        self.ax['IBI'].set_ylabel("IBI [ms]")
        
        self.ax['IBI'].set_xlabel("time")
        self.ax['sensor'].get_xaxis().set_visible(False)
        #self.ax['sensor'].xaxis.set_ticklabels([])
        
        self.ax['sensor'].spines['right'].set_visible(False)
        self.ax['sensor'].spines['top'].set_visible(False)
        self.ax['sensor'].spines['bottom'].set_visible(False)
        self.ax['sensor'].yaxis.set_ticks_position('left')
        self.ax['sensor'].xaxis.set_ticks_position('bottom')
        self.ax['IBI'].spines['right'].set_visible(False)
        self.ax['IBI'].spines['top'].set_visible(False)
        self.ax['IBI'].yaxis.set_ticks_position('left')
        self.ax['IBI'].xaxis.set_ticks_position('bottom')
        self.ax['HRV_descriptors'].spines['right'].set_visible(False)
        self.ax['HRV_descriptors'].spines['top'].set_visible(False)
        self.ax['HRV_descriptors'].spines['bottom'].set_visible(False)
        self.ax['HRV_descriptors'].get_xaxis().set_visible(False)
        #self.ax['HRV_descriptors'].yaxis.set_ticks([])
        self.ax['HRV_descriptors'].yaxis.set_ticks_position('right')
        
        gs.tight_layout(self.fig, rect=[0, 0, 1, 0.96], w_pad=3.2)
        
        # setup input and output

        if not CFG_no_arduino:
            print('reading from serial port %s...' % CFG_comport)
            self.ser = serial.Serial(comport, baudrate, timeout=CFG_serial_timeout)    # open serial port

        if CFG_save_dump: self.lines = []
        
        if CFG_no_arduino:
            self.no_arduino =  pickle.load(open(CFG_temp_file, "rb" ))
            self.lines_sim_iter = iter(self.no_arduino['lines'])
        
   
    def _on_xlim_changed(self, ax, min_y=None, max_y=None):
        """autoscale y-axis according to current x-axis limits, taken from stackoverflow"""
        xlim = ax.get_xlim()
        for a in ax.figure.axes:
            # shortcuts: last avoids n**2 behavior when each axis fires event
            if a is ax or len(a.lines) == 0 or getattr(a, 'xlim', None) == xlim:
                continue

            ylim = np.inf, -np.inf
            for l in a.lines:
                x, y = l.get_data()
                # faster, but assumes that x is sorted
                start, stop = np.searchsorted(x, xlim)
                yc = y[max(start-1,0):(stop+1)]
                ylim = min(ylim[0], np.nanmin(yc)), max(ylim[1], np.nanmax(yc))

            # x axis: emit=False avoids infinite loop
            a.set_xlim(xlim, emit=False)

            # y axis: set dataLim, make sure that autoscale in 'y' is on 
            if max_y!=None:
                if ylim[1]>max_y: ylim[1]=max_y
            if min_y!=None:
                if ylim[0]>min_y: ylim[0]=min_y
            corners = (xlim[0], ylim[0]), (xlim[1], ylim[1])
            a.dataLim.update_from_data_xy(corners, ignore=True, updatex=False)
            a.autoscale(enable=True, axis='y', tight=True)
            # cache xlim to mark 'a' as treated
            a.xlim = xlim
            

    def update_descriptors(self):
        """calculates and updates HRV descriptors"""
        
        hrv = hrv_analysis.HRVdescriptors()
        r = hrv.calculate(self.y['IBI'][:self.num_points['IBI']])
        self.hrv_descriptors.append(r)  # this list is not used right now
        
        pos = range(len(CFG_hrv_descriptors))
        vals = []
        for k in CFG_hrv_descriptors:
            val = r[k] / CFG_hrv_descriptors_standard[k]
            if val>0:
                self.hrv_descriptors_plot_norm2[k] = np.sign(math.log(val, CFG_hrv_descriptors_log_base)) * np.floor(np.abs(math.log(val, CFG_hrv_descriptors_log_base)))
            else:
                self.hrv_descriptors_plot_norm2[k] = 1
            vals.append(val / CFG_hrv_descriptors_log_base**(self.hrv_descriptors_plot_norm2[k]))
            self.hrv_text[k].set_text(CFG_hrv_descriptors_format[k] % r[k])
            self.hrv_text[k].set_position((vals[-1] - 0.05, pos[len(vals)-1]))
            self.hrv_text_norm[k].set_text("**%d" % self.hrv_descriptors_plot_norm2[k])
    
        for rect, val in zip(self.plots['HRV_descriptors'], vals):
            rect.set_width(val)

        

    def update(self, frameNum):
        """reads date from serial connection and updates the plot""" 
        
        update_artists = [self.ax['sensor'], self.ax['IBI'], self.ax['HRV_descriptors']]  # will be return to the animation task, for update, we need a few more if we want to use blit

        symbols = {"S":"sensor", "B":"beats", "Q":"IBI"}   # these are the symbols that come form the arduino program
        try:
            #line = self.ser.readline()
            if not CFG_no_arduino: serialRead = self.ser.read(self.ser.inWaiting())
            now = datetime.datetime.now()
            now_num = matplotlib.dates.date2num(now)

            if CFG_no_arduino:
                try:
                    arduino_input = next(self.lines_sim_iter)
                except StopIteration:
                    self.close()
                    return update_artists
            else:
                arduino_input = serialRead.strip().decode('ascii')
            if CFG_save_dump: self.lines.append(arduino_input)
            
        except ValueError:
            return update_artists
        except UnicodeDecodeError:
            return update_artists
            
        for line in arduino_input.split("\r\n"):
            if len(line)<2: return update_artists
            
            sym = line[0]
            if sym in symbols:
                val = int(line[1:])
                if sym=="S":
                    if val==0 and self.num_points['sensor']==0: return update_artists   # for some reason the first value is always 0, just want to ignore this one

                self.num_points[symbols[sym]] += 1
                self.y[symbols[sym]][self.num_points[symbols[sym]]-1] = val
                self.x[symbols[sym]][self.num_points[symbols[sym]]-1] = now_num
                if not sym in ["S", "Q", "B"]:
                    print("unexpected data: %s, %s "% (sym, val))
                else:               
                    if sym in ["S", "Q"]:
                        x_data = self.x[symbols[sym]][:self.num_points[symbols[sym]]]
                        y_data = self.y[symbols[sym]][:self.num_points[symbols[sym]]]
                        self.plots[symbols[sym]].set_data(x_data, y_data)
                   
                    if sym=='Q':  # always a B and a Q together, so let's update only once
                        self.text_IBI.set_text(self.y['IBI'][self.num_points['IBI']-1])
                        self.text_HR.set_text(int(60000.0/self.y['IBI'][self.num_points['IBI']-1]))
                        self.text_HR_mean_10.set_text(int(self.y['beats'][self.num_points['beats']-1]))
                        self.text_HR_mean_all.set_text(int(np.mean(60000.0/self.y['IBI'][:self.num_points['IBI']])))
                        
                        if self.num_points['IBI']>1: self.update_descriptors()  # calculates and updates HRV descriptors
                   
                    elapsed = (now-self.date_start).seconds
                    if elapsed < 3600:
                        elapsed_str = '{:02}:{:02}'.format(elapsed % 3600 // 60, elapsed % 60)
                    else:
                        elapsed_str = '{:02}:{:02}:{:02}'.format(elapsed // 3600, elapsed % 3600 // 60, elapsed % 60)
                    self.text_time.set_text("Elapsed time: %s" % elapsed_str)
                    
                    maxpoints_exceeded=False
                    for s in symbols.values():
                        if self.num_points[s] >= CFG_maxpoints[s]:
                            maxpoints_exceeded=True
                    if  (elapsed > CFG_max_runtime or maxpoints_exceeded):
                        if CFG_save_dump: pickle.dump({'IBI': self.y['IBI'][:self.num_points[symbols[sym]]], 'lines': self.lines}, open(CFG_temp_file, "wb" ))
                        self.close()
                    
        # update graph limits/scale
        if self.num_points['sensor'] == 0: return update_artists
        x_lim_start = now_num - CFG_graph_span_min/24/60
        #if x_lim_start < self.x['sensor'][0]: x_lim_start = self.x['sensor'][0]
        self.ax['sensor'].set_xlim([x_lim_start, now_num])
        self._on_xlim_changed(self.ax['sensor'])
        self._on_xlim_changed(self.ax['IBI'])
        
        return update_artists
        
        
    def showplot(self):
        plt.show()
   
    # clean up
    def close(self):
        if not CFG_no_arduino:
            # close serial
            self.ser.flush()
            self.ser.close()    
 

# main() function
def main():
    hrvplot = HRVplot(CFG_comport, CFG_baudrate, CFG_serial_timeout)
 
    hrvplot.update(0)
    anim = animation.FuncAnimation(hrvplot.fig, hrvplot.update, interval=100, blit=False)
    plt.show()

    hrvplot.close()
 
 
# call main
if __name__ == '__main__':
    main()