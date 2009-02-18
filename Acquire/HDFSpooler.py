import os
#import logparser
import datetime
import tables
from PYME.Acquire import MetaDataHandler
from PYME import cSMI

import time

from PYME.Acquire import eventLog

class SpoolEvent(tables.IsDescription):
   EventName = tables.StringCol(32)
   Time = tables.Time64Col()
   EventDescr = tables.StringCol(256)

class EventLogger:
   def __init__(self, scope, hdf5File):
      self.scope = scope
      self.hdf5File = hdf5File

      self.evts = self.hdf5File.createTable(hdf5File.root, 'Events', SpoolEvent)

   def logEvent(self, eventName, eventDescr = ''):
      ev = self.evts.row

      ev['EventName'] = eventName
      ev['EventDescr'] = eventDescr
      ev['Time'] = time.time()

      ev.append()
      self.evts.flush()

class Spooler:
   def __init__(self, scope, filename, acquisator, parent=None, complevel=6, complib='zlib'):
       self.scope = scope
       self.filename=filename
       self.acq = acquisator
       self.parent = parent 
       
       #self.dirname =filename[:-4]
       #os.mkdir(self.dirname)
       
       #self.filestub = self.dirname.split(os.sep)[-1]
       
       self.h5File = tables.openFile(filename, 'w')
       
       filt = tables.Filters(complevel, complib, shuffle=True)

       self.imageData = self.h5File.createEArray(self.h5File.root, 'ImageData', tables.UInt16Atom(), (0,scope.cam.GetPicWidth(),scope.cam.GetPicHeight()), filters=filt)

       self.imNum=0
       self.log = {}

       self.md = MetaDataHandler.HDFMDHandler(self.h5File)

       self.doStartLog()

       self.evtLogger = EventLogger(scope, self.h5File)
       eventLog.WantEventNotification.append(self.evtLogger)
       
       self.acq.WantFrameNotification.append(self.Tick)
       
       self.spoolOn = True

       
       
   def StopSpool(self):
       self.acq.WantFrameNotification.remove(self.Tick)
       eventLog.WantEventNotification.remove(self.evtLogger)
       self.doStopLog()
       #self.writeLog()
       self.h5File.flush()
       self.h5File.close()
       self.spoolOn = False
   
   def Tick(self, caller):
      #fn = self.dirname + os.sep + self.filestub +'%05d.kdf' % self.imNum
      #caller.ds.SaveToFile(fn.encode())
      
      self.imageData.append(cSMI.CDataStack_AsArray(caller.ds, 0).reshape(1,self.scope.cam.GetPicWidth(),self.scope.cam.GetPicHeight()))
      self.h5File.flush()

      self.imNum += 1
      if not self.parent == None:
         self.parent.Tick()

   def doStartLog(self):
      #md = self.h5File.createGroup(self.h5File.root, 'MetaData')

      dt = datetime.datetime.now()
        
      self.dtStart = dt

      #self.log['GENERAL']['Date'] = '%d/%d/%d' % (dt.day, dt.month, dt.year)
      #self.log['GENERAL']['StartTime'] = '%d:%d:%d' % (dt.hour, dt.minute, dt.second)
      #md._v_attrs.StartTime = time.time()
      self.md.setEntry('StartTime', time.time())
      
      #self.h5File.createGroup(self.h5File.root.MetaData, 'Camera')
      #self.scope.cam.GetStatus()

      #if 'tKin' in dir(self.scope.cam): #check for Andor cam
      #   md.Camera._v_attrs.IntegrationTime = self.scope.cam.tExp
      #   md.Camera._v_attrs.CycleTime = self.scope.cam.tKin
      #   md.Camera._v_attrs.EMGain = self.scope.cam.GetEMGain()

      #md.Camera._v_attrs.ROIPosX = self.scope.cam.GetROIX1()
      #md.Camera._v_attrs.ROIPosY = self.scope.cam.GetROIY1()
      #md.Camera._v_attrs.StartCCDTemp = self.scope.cam.GetCCDTemp()

      #loop over all providers of metadata
      for mdgen in MetaDataHandler.provideStartMetadata:
         mdgen(self.md)
      
   
  

   def doStopLog(self):
        #self.log['GENERAL']['Depth'] = self.ds.getDepth()
        #self.log['PIEZOS']['EndPos'] = self.GetEndPos()
        #self.scope.cam.GetStatus()
        #self.log['CAMERA']['EndCCDTemp'] = self.scope.cam.GetCCDTemp()
        #self.log['CAMERA']['EndElectrTemp'] = self.scope.cam.GetElectrTemp()
        
        dt = datetime.datetime.now()
        #self.log['GENERAL']['EndTime'] = '%d:%d:%d' % (dt.hour, dt.minute, dt.second)
        self.md.setEntry('EndTime', time.time())
        #self.log['GENERAL']['NumImages'] = '%d' % self.imNum

        #loop over all providers of metadata
        for mdgen in MetaDataHandler.provideStopMetadata:
           mdgen(self.md)
        
   def writeLog_(self):
        lw = logparser.logwriter()
        s = lw.write(self.log)
        log_f = file(self.filename, 'w')
        log_f.write(s)
        log_f.close()
        
   def __del__(self):
        if self.spoolOn:
            self.StopSpool()
