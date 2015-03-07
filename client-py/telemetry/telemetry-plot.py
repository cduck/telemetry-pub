from matplotlib import pyplot as plt
import matplotlib.animation as animation
import numpy as np
import serial

from telemetry.parser import *

plot_registry = {}

class NumericPlot():
  # TODO REFACTOR ME REALLY
  def __init__(self, indep_name, dep_def, indep_span, subplot, hide_indep_axis=False):
    self.indep_span = indep_span
    self.indep_name = indep_name
    self.dep_name = dep_def.internal_name
    self.subplot = subplot
    self.subplot.set_title("%s: %s (%s)"           
                           % (dep_def.internal_name, dep_def.display_name, dep_def.units))
    self.line, = subplot.plot([0])
    
    plt.setp(subplot.get_xticklabels(), visible=not hide_indep_axis)
    
    self.indep_data = deque()
    self.dep_data = deque()
  
  def update_from_packet(self, packet):
    assert isinstance(packet, DataPacket)
    data_names = packet.get_data_names()
    
    if self.indep_name in data_names and self.dep_name in data_names:
      latest_indep = packet.get_data(self.indep_name)
      self.indep_data.append(latest_indep)
      self.dep_data.append(packet.get_data(self.dep_name))
      
      indep_cutoff = latest_indep - self.indep_span
      
      while self.indep_data[0] < indep_cutoff:
        self.indep_data.popleft()
        self.dep_data.popleft()
        
      self.line.set_xdata(self.indep_data)
      self.line.set_ydata(self.dep_data)

  def set_indep_range(self, indep_range):
    self.subplot.set_xlim(indep_range)

  def autoset_dep_range(self):
    if not self.dep_data:
      return
    minlim = min(self.dep_data)
    maxlim = max(self.dep_data)
    if minlim < 0 and maxlim < 0:
      maxlim = 0
    elif minlim > 0 and maxlim > 0:
      minlim = 0
    rangelim = maxlim - minlim
    minlim -= rangelim / 20 # TODO make variable padding
    maxlim += rangelim / 20
    self.subplot.set_ylim(minlim, maxlim)

plot_registry[NumericData] = NumericPlot

class WaterfallPlot():
  # TODO REFACTOR ME REALLY
  def __init__(self, indep_name, dep_def, indep_span, subplot, hide_indep_axis=False):
    self.indep_span = indep_span
    self.indep_name = indep_name
    self.dep_name = dep_def.internal_name
    self.count = dep_def.count
    
    self.subplot = subplot
    self.subplot.set_title("%s: %s (%s)"           
                           % (dep_def.internal_name, dep_def.display_name, dep_def.units))
    
    self.x_mesh = [0] * (self.count + 1)
    self.x_mesh = np.array([self.x_mesh, self.x_mesh])
    
    self.y_array = range(0, self.count + 1)
    self.y_array = list(map(lambda x: x - 0.5, self.y_array))
    self.y_mesh = np.array([self.y_array, self.y_array])
    
    self.data_array = np.array([[0] * self.count])
    
    self.quad = self.subplot.pcolormesh(self.x_mesh, self.y_mesh, self.data_array)

    plt.setp(subplot.get_xticklabels(), visible=not hide_indep_axis)
    
    self.indep_data = deque()
    self.dep_data = deque()
  
  def update_from_packet(self, packet):
    assert isinstance(packet, DataPacket)
    data_names = packet.get_data_names()

    if self.indep_name in data_names and self.dep_name in data_names:
      latest_indep = packet.get_data(self.indep_name)
      self.x_mesh = np.vstack([self.x_mesh, np.array([[latest_indep] * (self.count + 1)])])
      self.y_mesh = np.vstack([self.y_mesh, np.array(self.y_array)])
      self.data_array = np.vstack([self.data_array, packet.get_data(self.dep_name)])

      indep_cutoff = latest_indep - self.indep_span
      
      while self.x_mesh[0][0] < indep_cutoff:
        self.x_mesh = np.delete(self.x_mesh, (0), axis=0)
        self.y_mesh = np.delete(self.y_mesh, (0), axis=0)
        self.data_array = np.delete(self.data_array, (0), axis=0)
      
      self.subplot.cla()
      self.quad = self.subplot.pcolorfast(self.x_mesh, self.y_mesh, self.data_array, cmap='gray', vmin=0, vmax=65535, interpolation='None')

  def set_indep_range(self, indep_range):
    self.subplot.set_xlim(indep_range)

  def autoset_dep_range(self):
    pass

plot_registry[NumericArray] = WaterfallPlot

if __name__ == "__main__":
  timespan = 10000
  independent_axis_name = 'time'
  
  telemetry = TelemetrySerial(serial.Serial("COM61", baudrate=1000000))
  all_plotdata = []
  fig = plt.figure()
  latest_indep = [0]
  
  def update(data):
    telemetry.process_rx()
    plot_updated = False
    
    while True:
      packet = telemetry.next_rx_packet()
      if not packet:
        break
      
      if isinstance(packet, HeaderPacket):
        all_plotdata.clear()
        fig.clf()
        
        data_defs = []
        for _, data_def in reversed(sorted(packet.get_data_defs().items())):
          if data_def.internal_name != independent_axis_name:
            data_defs.append(data_def)

        for plot_idx, data_def in enumerate(data_defs):
          if data_def.internal_name == independent_axis_name:
            continue

          ax = fig.add_subplot(len(data_defs), 1, len(data_defs)-plot_idx)
          plotdata = plot_registry[data_def.__class__](independent_axis_name, data_def,
                                 timespan, ax)
          all_plotdata.append(plotdata)
          
          print("Found dependent data %s" % data_def.internal_name)

      elif isinstance(packet, DataPacket):
        indep_value = packet.get_data(independent_axis_name)
        if indep_value is not None:
          latest_indep[0] = indep_value
          
        for plotdata in all_plotdata:
          plotdata.update_from_packet(packet)
          
        plot_updated = True
      else:
        raise Exception("Unknown received packet %s" % repr(next_packet))
      
    while True:
      next_byte = telemetry.next_rx_byte()
      if next_byte is None:
        break
      try:
        print(chr(next_byte), end='')
      except UnicodeEncodeError:
        pass

    if plot_updated:
      max_indep = 0
      for plotdata in all_plotdata:
        plotdata.autoset_dep_range()
           
      for plotdata in all_plotdata:    
        plotdata.set_indep_range([latest_indep[0] - timespan, latest_indep[0]])  

  ani = animation.FuncAnimation(fig, update, interval=30)
  plt.show()
