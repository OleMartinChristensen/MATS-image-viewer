import serial
from tkinter import *
from ramses import sniffer
import queue
import threading
import binascii
import tkinter.filedialog
import binascii
import numpy as np
import matplotlib.pyplot as plt
import struct
import subprocess
import time

def recvFromArduino(ser):
  startMarker = 60
  endMarker = 62
  
  ck = ""
  x = "z" # any value that is not an end- or startMarker
  byteCount = -1 # to allow for the fact that the last increment will be one too many
  
  # wait for the start character
  while  ord(x) != startMarker: 
    x = ser.read()
  
  # save data until the end marker is found
  while ord(x) != endMarker:
    if ord(x) != startMarker:
      ck = ck + x 
      byteCount += 1
    x = ser.read()
  
  return(ck)

def waitForArduino(ser):

   # wait until the Arduino sends 'Arduino Ready' - allows time for Arduino reset
   # it also ensures that any bytes left over from a previous message are discarded
   
    msg = ""
    while msg.find("READY") == -1:

      while ser.inWaiting() == 0:
        pass
        
      msg = recvFromArduino(ser)
      

      print(msg)

def send_shuttercommand(ser,exposure_time=20):
    #exposure_time is in seconds
	print('running script')
	# ser.isOpen() # AH
	# ser.isOpen() # AH

	print('sending command')
	msg = ser.write(bytes(b'1\n\r'))
	# print(str(msg)+ 'sd')
	print(msg)
	print(exposure_time)
	time.sleep(exposure_time)
	msg = ser.write(bytes(b'1\n\r'))
	print(msg)

	#ser.close()

class ThreadedTask(threading.Thread):
    def __init__(self, stopEvent, queue, stream, scid, apid, type, subtype):
        threading.Thread.__init__(self)
        self.queue = queue
        self.stream = stream
        self.scid = scid
        self.apid = apid
        self.type = type
        self.subType = subtype
        self.stopEvent = stopEvent
        
    def run(self):
        with sniffer.RamsesTmSniffer(self.stream) as tm_sniffer, sniffer.RamsesTcSniffer(self.stream) as tc_sniffer:
            all_sniffers = (tm_sniffer, tc_sniffer)
            while (not self.stopEvent.is_set()):
                sniffer.wait_for_incoming_data(all_sniffers, 0.25)  # timeout given to be able to exit with Ctrl-C
       
                tc_packet = tc_sniffer.read(scid_filter=self.scid, apid_filter=self.apid, type_filter=self.type, subtype_filter=self.subType, invert_filter=None)
                if tc_packet is not None:
                    self.queue.put(tc_packet)
                    
       
                tm_packet = tm_sniffer.read(scid_filter=self.scid, apid_filter=self.apid, type_filter=self.type, subtype_filter=self.subType, invert_filter=False)
                if tm_packet is not None:
                    self.queue.put(tm_packet)    

class shutter_commander(tkinter.Tk):
    def __init__(self,parent):   
        tkinter.Tk.__init__(self,parent)
        self.parent = parent		
        self.TmStream=17
		
        #Create queue and start capture thread
        self.queue = queue.Queue()
        self.snifferStopEvent = threading.Event()
        self.snifferThread = ThreadedTask(self.snifferStopEvent,self.queue, self.TmStream, 558, 100, 8, 1) #what should type be?
        self.snifferThread.daemon = True
        self.snifferThread.start()
        self.after(10, self.process_queue)
		
        self.ser = serial.Serial(
            port='COM4',
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
	    )
		
		
        time.sleep(5)
        self.ser.write(bytes(b'1\n\r'))
        time.sleep(5)
        self.ser.write(bytes(b'1\n\r'))


		
    def process_queue(self):
        if not self.snifferStopEvent.is_set():
            try:                
                packet = self.queue.get(0)
                print('packet detected')
                if packet['packet_type'] == 1:
                    packet_type = 'TC'
                    print('TC packet detected')
                else:
                    packet_type = 'TM'                    
                    print('TM packet detected')
                
                ridLength = 2     
                headerSize = 37                
                
                rid=struct.unpack('>H',packet['payload'][:ridLength])[0]
                
                #Only process TC commands with snapshot?
				
                if rid ==24:
                    print('Snapshot detected')
                    groupFlag = packet['sequence_control']>>14
                    sequenceCounter = packet['sequence_control']&0x3fff     
                    #print(packet['payload'])
                    
                    #Handle data stretched over several packets, such as image data, strip header/context data from first packet
                    if groupFlag == 1 or groupFlag == 3:
                        print("Start packet found")
						
                        #Extract & display header information
                        ccdSelect = struct.unpack('B',packet['payload'][ridLength:ridLength+1])[0] 
                        print('Shooting with CCD# ' + str(ccdSelect))
                        send_shuttercommand(self.ser,exposure_time=3.0)
               
                #self.process_queue()
                self.after(10,self.process_queue)
                
            except queue.Empty:
                self.after(10,self.process_queue)

		
if __name__ == "__main__":
    app = shutter_commander(None)
    app.title("Shutter Commander")
    
    app.mainloop()