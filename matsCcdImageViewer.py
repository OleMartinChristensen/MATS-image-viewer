 ################################################################################
# Python application for viewing MATS payload images
#
#   Version:        $Rev: 5608 $
#   Last Edit       $Date: 2019-05-06 13:30:31 +0200 (Mon, 06 May 2019) $
#   Last Edit by:   $Author: nln $
#
################################################################################

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
from PIL import Image
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable
#from PIL import Image
import os
import sys
import math

sys.setrecursionlimit(5000)

NANOS_PER_SECOND = 1e9

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
                sniffer.wait_for_incoming_data(all_sniffers, 0.05)  # timeout given to be able to exit with Ctrl-C
       
                tc_packet = tc_sniffer.read(scid_filter=self.scid, apid_filter=self.apid, type_filter=self.type, subtype_filter=self.subType, invert_filter=None)
                if tc_packet is not None:
                    self.queue.put(tc_packet)
                    
       
                tm_packet = tm_sniffer.read(scid_filter=self.scid, apid_filter=self.apid, type_filter=self.type, subtype_filter=self.subType, invert_filter=False)
                if tm_packet is not None:
                    self.queue.put(tm_packet)    

class matsViewer(tkinter.Tk):
    def __init__(self,parent):   
        tkinter.Tk.__init__(self,parent)
        self.parent = parent
        
        self.TmStream=17
        
        self.initialize(parent)
        self.ccdDataDefinition()
        self.imageData=bytes()
        self.outputDir = "PayloadImages\\"
        
    def initialize(self,parent):

        self.ccdSelect = 0
        self.exposureStart = 0
        self.exposureFraction = 0
        self.wdwMode = 0
        self.windowOverflow = 0
        self.jpegQuality = 99
        self.frame = 0
        self.nRows = 0
        self.nRowBin = 0
        self.nRowSkip = 0
        self.nCols = 0
        self.nColBin = 0
        self.nColSkip = 0
        self.nflush = 0
        self.exposureTime = 0.0
        self.gain = 0
        self.temp = 0
        self.fbinov = 0
        self.lblnk = 0
        self.tblnk = 0
        self.zero= 0
        self.timing1 = 0
        self.timing2 = 0
        self.version = 0
        self.timing3 = 0
        self.nBadCols = 0
        self.id = ''
    
        ########### --Layout frames-- ##########    
        self.myContainer1 = Frame(parent)
        self.myContainer1.pack()
        
        self.leftFrame = Frame(self.myContainer1, 
            background="white",
            borderwidth=5,
            relief=RIDGE,
            height=850,
            width=200)
        self.leftFrame.pack(
            side = LEFT,
            fill = BOTH,
            expand = YES
            )
           
        self.rightFrame = Frame(self.myContainer1,
            borderwidth=5,  
            relief=RIDGE,
            height=850,
            width=350)
        self.rightFrame.pack(
            side = LEFT,
            fill = BOTH,
            expand = YES
            )
            
        self.ccdImageInfoFrame = Frame(self.leftFrame,
            background = "gray",
            borderwidth=5,
            relief=RIDGE,
            height=350,
            width=200
            )
        self.ccdImageInfoFrame.pack(
            side = TOP,
            fill = BOTH,
            expand = YES
            )
            
        self.buttonFrame = Frame(self.leftFrame,
            background = "gray",
            borderwidth=5,
            relief=RIDGE,
            height=150,
            width=200
            )
        self.buttonFrame.pack(
            side = BOTTOM,
            fill = BOTH,
            expand = YES
            )
        
        self.contrastFrame = Frame(self.leftFrame,
            background = "gray",
            borderwidth=5,
            relief=RIDGE,
            height=150,
            width=200
            )
        self.contrastFrame.pack(
            side = BOTTOM,
            fill = BOTH,
            expand = YES
            )
        
        ########### --Action buttons-- ##########
        button_width=15
        button_padx=10
        button_pady=10
        
        small_button_width = 5
        small_button_width = 5
        small_button_width = 5
        #Start button
        self.startButton = Button(self.buttonFrame, command=self.startButtonClick)
        self.startButton.configure(text="Start")
        self.startButton.focus_force()
        self.startButton.configure(
            width=button_width,  
            padx=button_padx,    
            pady=button_pady,
            state = NORMAL
            )

        self.startButton.pack(
            fill = BOTH,
            expand = NO,
            side=TOP
            )
        self.startButton.bind("<Return>", self.startButtonClick_a)
        
        #Stop capture button
        self.stopButton = Button(self.buttonFrame, command=self.stopButtonClick)
        self.stopButton.configure(text="Stop")
        self.stopButton.focus_force()
        self.stopButton.configure(
            width=button_width,  
            padx=button_padx,    
            pady=button_pady,
            state = DISABLED
            )

        self.stopButton.pack(
            fill = BOTH,
            expand = NO,
            side=TOP
            )
        self.stopButton.bind("<Return>", self.stopButtonClick_a)
        
        #Quit button
        self.quitButton = Button(self.buttonFrame, command=self.quitButtonClick)
        self.quitButton.configure(text="Quit")
        self.quitButton.configure(
            width=button_width,
            padx=button_padx,  
            pady=button_pady   
            )

        self.quitButton.pack(
            fill = BOTH,
            expand = NO,
            side=TOP
            )
        self.quitButton.bind("<Return>", self.quitButtonClick_a)

        #min value of colormap
        self.minEntryLabel = Label(self.contrastFrame, text="MinVal")
        self.minEntryLabel.grid(row=0, column=0)
        self.minVal = IntVar()
        self.minVal.set(0)
        self.minEntry = Entry(self.contrastFrame,textvariable=self.minVal)
        self.minEntry.bind("<Return>", self.ManButtonClick_a) 
        self.minEntry.grid(row=0, column=1,columnspan=3)        
        
        #max value of colormap
        self.maxEntryLabel = Label(self.contrastFrame, text="MaxVal")
        self.maxEntryLabel.grid(row=1, column=0)
        self.maxVal = IntVar()
        self.maxVal.set(0)
        self.maxEntry = Entry(self.contrastFrame,textvariable=self.maxVal)
        self.maxEntry.bind("<Return>", self.ManButtonClick_a) 
        self.maxEntry.grid(row=1, column=1,columnspan=3)     
        
        #Use autoadjust colormap by default
        self.AutoVal = BooleanVar()
        self.AutoVal.set(True)


        #Set contrast buttons
        self.bit12Button = Button(self.contrastFrame, command=self.bit12ButtonClick)
        self.bit12Button.configure(text="12bit")
        self.bit12Button.focus_force()
        self.bit12Button.configure(
            width=small_button_width
            )
        self.bit12Button.grid(row=2, column=1)
        self.bit12Button.bind("<Return>", self.bit12ButtonClick_a) 

        self.bit16Button = Button(self.contrastFrame, command=self.bit16ButtonClick)
        self.bit16Button.configure(text="16bit")
        self.bit16Button.focus_force()
        self.bit16Button.configure(
            width=small_button_width 
            )
        self.bit16Button.grid(row=2, column=2)
        self.bit16Button.bind("<Return>", self.bit16ButtonClick_a) 
        
        self.AutoButton = Button(self.contrastFrame, command=self.AutoButtonClick,relief= SUNKEN)
        self.AutoButton.configure(text="Auto")
        self.AutoButton.focus_force()
        self.AutoButton.configure(
            width=small_button_width
            )
        self.AutoButton.grid(row=2, column=3)
        self.AutoButton.bind("<Return>", self.AutoButtonClick_a) 

       
        ########### --Labels-- ##########
        self.ccdSelectLabel=Label(self.ccdImageInfoFrame,text="ID: ")
        self.ccdSelectLabel.grid(row=0, column=0)

        self.ccdSelectLabel=Label(self.ccdImageInfoFrame,text="CCD#: ")
        self.ccdSelectLabel.grid(row=1, column=0)
        
        self.imageScetLabel=Label(self.ccdImageInfoFrame,text="Exposure Sec: ", justify="left")
        self.imageScetLabel.grid(row=2, column=0)

        self.exposureFractionLabel=Label(self.ccdImageInfoFrame,text="Exposure Subsec: ", justify="left")
        self.exposureFractionLabel.grid(row=3, column=0)
        
        self.WindowLabel=Label(self.ccdImageInfoFrame,text="Window Mode: ", justify="left")
        self.WindowLabel.grid(row=4, column=0)

        self.OverflowLabel=Label(self.ccdImageInfoFrame,text="Overflow Counter (OBC): ", justify="left")
        self.OverflowLabel.grid(row=5, column=0)
     
        self.jpegQualityLabel=Label(self.ccdImageInfoFrame,text="JPEG Quality: ", justify="left")
        self.jpegQualityLabel.grid(row=6, column=0)
        
        self.exposureTimeLabel=Label(self.ccdImageInfoFrame,text="Exposure time (ms): ", justify="left")
        self.exposureTimeLabel.grid(row=7, column=0)
        
        self.LeadBlanksLabel=Label(self.ccdImageInfoFrame,text="Leading blanks: ", justify="left")
        self.LeadBlanksLabel.grid(row=8, column=0)
        
        self.TrailBlanksLabel=Label(self.ccdImageInfoFrame,text="Trailing Blanks: ", justify="left")
        self.TrailBlanksLabel.grid(row=9, column=0)
        
        self.GainLabel=Label(self.ccdImageInfoFrame,text="Gain: ", justify="left")
        self.GainLabel.grid(row=10, column=0)
        
        self.GainOvLabel=Label(self.ccdImageInfoFrame,text="Number of overflows (CCD): ", justify="left")
        self.GainOvLabel.grid(row=11, column=0)
        
        self.NFlushLabel=Label(self.ccdImageInfoFrame,text="Number of flushes: ", justify="left")
        self.NFlushLabel.grid(row=12, column=0)
        
        self.NRSkipLabel=Label(self.ccdImageInfoFrame,text="Number of rows to skip: ", justify="left")
        self.NRSkipLabel.grid(row=13, column=0)
        
        self.NRBinLabel=Label(self.ccdImageInfoFrame,text="Number of rows to bin: ", justify="left")
        self.NRBinLabel.grid(row=14, column=0)
        
        self.NRowLabel=Label(self.ccdImageInfoFrame,text="Number of rows: ", justify="left")
        self.NRowLabel.grid(row=15, column=0)
        
        self.NCSkipLabel=Label(self.ccdImageInfoFrame,text="Number of columns to skip: ", justify="left")
        self.NCSkipLabel.grid(row=16, column=0)
        
        self.NCBinLabel=Label(self.ccdImageInfoFrame,text="Number of columns to bin: ", justify="left")
        self.NCBinLabel.grid(row=17, column=0)
        
        self.NColLabel=Label(self.ccdImageInfoFrame,text="Number of columns: ", justify="left")
        self.NColLabel.grid(row=18, column=0)
        
        self.NBCLabel=Label(self.ccdImageInfoFrame,text="Number of bad columns: ", justify="left")
        self.NBCLabel.grid(row=19, column=0)
        
        self.totalPayloadPackets=Label(self.ccdImageInfoFrame,text="Total Packets: ")
        self.totalPayloadPackets.grid(row=20, column=0)
            
        ######## --Image output -- #########
        self.image=np.zeros([1,1],dtype='uint16')
        self.figure = plt.Figure()        
        self.subplot = self.figure.add_subplot(111)
        self.cbaraxis = make_axes_locatable(self.subplot).append_axes("right", size="5%", pad="2%")
        
        self.imshowobject = self.subplot.imshow(self.image)
        
        self.colorbar = self.figure.colorbar(self.imshowobject, cax=self.cbaraxis)
        
        self.imageOut=FigureCanvasTkAgg(self.figure, master=self.rightFrame)
        self.imageOut.get_tk_widget().pack(side="top", fill="both", expand=True)
        self.minVal.set(np.min(self.image))
        self.maxVal.set(np.max(self.image))
        
        
    #Button callbacks
    def startButtonClick(self):
        #Disable button
        self.startButton.config(state=DISABLED)
        self.stopButton.config(state=NORMAL)
        self.subplot.imshow(self.image)
        #Create queue and start capture thread
        self.queue = queue.Queue(maxsize=0)
        self.snifferStopEvent = threading.Event()
        self.snifferThread = ThreadedTask(self.snifferStopEvent,self.queue, self.TmStream, 558, 100, 128, 25)
        self.snifferThread.daemon = True
        self.snifferThread.start()
        self.after(100, self.process_queue)
        
        #self.image=self.read12bit_jpeg('output717.jpg')
        
        self.refresh_image()
        

        
    def stopButtonClick(self):
        self.startButton.config(state=NORMAL)
        self.stopButton.config(state=DISABLED)
        
        #self.after(0, self.process_queue)
        self.snifferStopEvent.set()

    def bit12ButtonClick(self):
        self.minVal.set(0)
        self.maxVal.set(4095)
        self.AutoVal.set(False)
        self.AutoButton.config(relief=RAISED)
        self.refresh_image()

    def bit16ButtonClick(self):
        self.minVal.set(0)
        self.maxVal.set(65535)
        self.AutoVal.set(False)
        self.AutoButton.config(relief=RAISED)
        self.refresh_image()       
    
    def ManButtonClick(self):
        #Handle that minval grater than maxval
        if self.minVal.get()>self.maxVal.get():
            tmp = self.minVal.get()
            self.minVal.set(self.maxVal.get())
            self.maxVal.set(tmp)
        self.AutoVal.set(False)
        self.AutoButton.config(relief=RAISED)
        self.refresh_image()

    def AutoButtonClick(self):
        self.AutoVal.set(True)
        self.AutoButton.config(relief=SUNKEN)
        self.refresh_image()
        
    # Wrapper callbacks for buttons
    def quitButtonClick(self):
        self.destroy()

    def startButtonClick_a(self, event):
        self.startButtonClick()
        
    def stopButtonClick_a(self, event):
        self.stopButtonClick()
        
    def clearButtonClick_a(self, event):
        self.clearButtonClick()

    def quitButtonClick_a(self, event):
        self.quitButtonClick()
    
    def bit12ButtonClick_a(self, event):
        self.bit12ButtonClick()

    def bit16ButtonClick_a(self, event):
        self.bit16ButtonClick()

    def ManButtonClick_a(self, event):
        self.ManButtonClick()
        
    def AutoButtonClick_a(self, event):
        self.AutoButtonClick()

        
    def ccdDataDefinition(self):
        self.ccdDataByteOffset = {
            'CCDSEL': 0,
            'EXPTS': 1,
            'EXPTSS': 5,
            'WDW':7,
            'WDWOV': 8,
            'JPEGQ': 10,
            'FRAME': 11,
            'NROW': 13,
            'NRBIN': 15,
            'NRSKIP': 17,
            'NCOL': 19,
            'NCBIN': 21,
            'NCSKIP': 23,
            'NFLUSH': 25,
            'TEXPMS': 27,
            'GAIN': 31,
            'TEMP': 33,
            'FBINOV': 35,
            'LBLNK': 37,
            'TBLNK': 39,
            'ZERO': 41,
            'TIMING1': 43,
            'TIMING2': 45,
            'VERSION': 47,
            'TIMING3': 49,
            'NBC': 51,
            'BC': 53
            }
        
        self.ccdDataLengths = {
            'CCDSEL': 1,
            'EXPTS': 4,
            'EXPTSS': 2,
            'WDW':1,
            'WDWOV': 2,
            'JPEGQ': 1,
            'FRAME': 2,
            'NROW': 2,
            'NRBIN': 2,
            'NRSKIP': 2,
            'NCOL': 2,
            'NCBIN': 2,
            'NCSKIP': 2,
            'NFLUSH': 2,
            'TEXPMS': 4,
            'GAIN': 2,
            'TEMP': 2,
            'FBINOV': 2,
            'LBLNK': 2,
            'TBLNK': 2,
            'ZERO': 2,
            'TIMING1': 2,
            'TIMING2': 2,
            'VERSION': 2,
            'TIMING3': 2,
            'NBC': 2,
            'BC': 0 #will be set later after NBC is decoded
            }
        
        
        self.ccdPacketRid= 21
        self.totalCCDs = 7
        self.totalCcdPackets = 0
        
        
    def process_queue(self):
        if not self.snifferStopEvent.is_set():
            try:                
                packet = self.queue.get(0)
                if packet['packet_type'] == 1:
                    packet_type = 'TC'
                else:
                    packet_type = 'TM'                    
                
                ridLength = 2     
                headerSize = 53                
                
                rid=struct.unpack('>H',packet['payload'][:ridLength])[0]
                
                #Only process CCD image data packets
                if rid >= self.ccdPacketRid and rid <= self.ccdPacketRid + (self.totalCCDs-1) and packet_type == 'TM':
                    groupFlag = packet['sequence_control']>>14
                    sequenceCounter = packet['sequence_control']&0x3fff     
                    #print(packet['payload'])
                    print(sequenceCounter)
                    #Handle data stretched over several packets, such as image data, strip header/context data from first packet
                    if groupFlag == 1 or groupFlag == 3:
                        print("Start packet found")
                        
                        #Extract & display header information
                        self.ccdSelect = struct.unpack('B',packet['payload'][ridLength+self.ccdDataByteOffset['CCDSEL']:ridLength+self.ccdDataByteOffset['CCDSEL']+self.ccdDataLengths['CCDSEL']])[0]                        
                        self.ccdSelectLabel.configure(text=("CCD#: " + str(self.ccdSelect)))
                        
                        self.exposureStart = struct.unpack('I',packet['payload'][ridLength+self.ccdDataByteOffset['EXPTS']:ridLength+self.ccdDataByteOffset['EXPTS']+self.ccdDataLengths['EXPTS']])[0]                        
                        self.imageScetLabel.configure(text=("Exposure Start#: " + str(self.exposureStart)))
                        
                        self.exposureFraction = struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['EXPTSS']:ridLength+self.ccdDataByteOffset['EXPTSS']+self.ccdDataLengths['EXPTSS']])[0]                        
                        self.exposureFractionLabel.configure(text=("Exposure Subsec: " + str(self.exposureFraction)))
                        #self.exposureStart= float(exposureStart) + float(exposureFraction)/65535.0
                        
                        
                        self.wdwMode =  struct.unpack('B',packet['payload'][ridLength+self.ccdDataByteOffset['WDW']:ridLength+self.ccdDataByteOffset['WDW']+self.ccdDataLengths['WDW']])[0]                        
                        self.WindowLabel.configure(text=("Window Mode: " + str(self.wdwMode)))

                        self.windowOverflow =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['WDWOV']:ridLength+self.ccdDataByteOffset['WDWOV']+self.ccdDataLengths['WDWOV']])[0]                        
                        self.OverflowLabel.configure(text=("Overflow Counter (OBC): " + str(self.windowOverflow)))
                        
                        self.jpegQuality =  struct.unpack('B',packet['payload'][ridLength+self.ccdDataByteOffset['JPEGQ']:ridLength+self.ccdDataByteOffset['JPEGQ']+self.ccdDataLengths['JPEGQ']])[0]                        
                        self.jpegQualityLabel.configure(text=("JPEG Quality: " + str(self.jpegQuality)))
                        
                        #self.exposureTime  = struct.unpack('I',packet['payload'][ridLength+self.ccdDataByteOffset['TEXPMS']+2:ridLength+self.ccdDataByteOffset['TEXPMS']+self.ccdDataLengths['TEXPMS']] 
                        #+ packet['payload'][ridLength+self.ccdDataByteOffset['TEXPMS']:ridLength+self.ccdDataByteOffset['TEXPMS']+2])[0]
                        
                        self.frame =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['FRAME']:ridLength+self.ccdDataByteOffset['FRAME']+self.ccdDataLengths['FRAME']])[0]                        

                        self.nRows =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NROW']:ridLength+self.ccdDataByteOffset['NROW']+self.ccdDataLengths['NROW']])[0]                        
                        self.NRowLabel.configure(text=("Number of rows: " + str(self.nRows)))  

                        self.nRowBin =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NRBIN']:ridLength+self.ccdDataByteOffset['NRBIN']+self.ccdDataLengths['NRBIN']])[0]                        
                        self.NRBinLabel.configure(text=("Number of rows to bin: " + str(self.nRowBin)))  

                        self.nRowSkip =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NRSKIP']:ridLength+self.ccdDataByteOffset['NRSKIP']+self.ccdDataLengths['NRSKIP']])[0]                        
                        self.NRSkipLabel.configure(text=("Number of rows to skip: " + str(self.nRowSkip)))   

                        self.nCols =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NCOL']:ridLength+self.ccdDataByteOffset['NCOL']+self.ccdDataLengths['NCOL']])[0]                        
                        self.NColLabel.configure(text=("Number of columns: " + str(self.nCols)))  

                        self.nColBin =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NCBIN']:ridLength+self.ccdDataByteOffset['NCBIN']+self.ccdDataLengths['NCBIN']])[0]                        
                        self.NCBinLabel.configure(text=("Number of columns to bin: " + str(self.nColBin)))  

                        self.nColSkip =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NCSKIP']:ridLength+self.ccdDataByteOffset['NCSKIP']+self.ccdDataLengths['NCSKIP']])[0]                        
                        self.NCSkipLabel.configure(text=("Number of columns to skip: " + str(self.nColSkip)))   

                        self.nflush =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NFLUSH']:ridLength+self.ccdDataByteOffset['NFLUSH']+self.ccdDataLengths['NFLUSH']])[0]                        
                        self.NFlushLabel.configure(text=("Number of Flushes: " + str(self.nflush)))                          
                        
                        self.exposureTime =  struct.unpack('I',packet['payload'][ridLength+self.ccdDataByteOffset['TEXPMS']:ridLength+self.ccdDataByteOffset['TEXPMS']+self.ccdDataLengths['TEXPMS']])[0]
                        self.exposureTimeLabel.configure(text=("Exposure time (ms): " + str(self.exposureTime)))

                        self.gain =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['GAIN']:ridLength+self.ccdDataByteOffset['GAIN']+self.ccdDataLengths['GAIN']])[0]                        
                        self.GainLabel.configure(text=("Gain: " + str(self.gain)))    

                        self.temp =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['TEMP']:ridLength+self.ccdDataByteOffset['TEMP']+self.ccdDataLengths['TEMP']])[0]                        

                        self.fbinov =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['FBINOV']:ridLength+self.ccdDataByteOffset['FBINOV']+self.ccdDataLengths['FBINOV']])[0]                        
                        self.GainOvLabel.configure(text=("Number of overflows (FPGA): " + str(self.fbinov))) 
                        
                        
                        self.lblnk =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['LBLNK']:ridLength+self.ccdDataByteOffset['LBLNK']+self.ccdDataLengths['LBLNK']])[0]                        
                        self.LeadBlanksLabel.configure(text=("Trailing blanks: " + str(self.lblnk)))

                        self.tblnk =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['TBLNK']:ridLength+self.ccdDataByteOffset['TBLNK']+self.ccdDataLengths['TBLNK']])[0]                        
                        self.TrailBlanksLabel.configure(text=("Leading blanks: " + str(self.tblnk)))
                    
                        self.zero =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['ZERO']:ridLength+self.ccdDataByteOffset['ZERO']+self.ccdDataLengths['ZERO']])[0]                                               
                        self.timing1 =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['TIMING1']:ridLength+self.ccdDataByteOffset['TIMING1']+self.ccdDataLengths['TIMING1']])[0]                                               
                        self.timing2 =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['TIMING2']:ridLength+self.ccdDataByteOffset['TIMING2']+self.ccdDataLengths['TIMING2']])[0]                                               
                        self.version =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['VERSION']:ridLength+self.ccdDataByteOffset['VERSION']+self.ccdDataLengths['VERSION']])[0]                                               
                        self.timing3 =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['TIMING3']:ridLength+self.ccdDataByteOffset['TIMING3']+self.ccdDataLengths['TIMING3']])[0]                                               
 
                        self.nBadCols =  struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NBC']:ridLength+self.ccdDataByteOffset['NBC']+self.ccdDataLengths['NBC']])[0]                        
                        self.NBCLabel.configure(text=("Number of bad columns: " + str(self.nBadCols)))
                        
                        self.BadCols = np.array([1,self.nBadCols])
                        
                        self.id = str(UnsegmentedTimeNanoseconds(self.exposureStart,self.exposureFraction)) + '_' + str(self.ccdSelect)
                        #print(self.BadCols.shape)
                        for n in range(self.nBadCols):
                            self.BadCols[n] = struct.unpack('H',packet['payload'][ridLength+self.ccdDataByteOffset['NBC']+self.ccdDataLengths['NBC']+2*n:ridLength+self.ccdDataByteOffset['NBC']+self.ccdDataLengths['NBC']+2*(n+1)])[0]                        
						
                        self.imageData=packet['payload'][ridLength+headerSize+2*self.nBadCols:]
                        
                    elif groupFlag == 0 or groupFlag == 2:
                        #print("Mid packet")
                        self.imageData+=packet['payload'][ridLength:]
                    
                    if groupFlag == 2 or groupFlag == 3:
                        print("Stand-alone or end packet ")                        
                        if self.jpegQuality <= 100:
                            self.saveToJpeg()
                        else:
                            self.saveToPnm()
                        self.imageData=bytes()
                        self.saveToTxt()
                    
                    self.totalCcdPackets+=1
                    self.totalPayloadPackets.configure(text=("Total Packets: " + str(self.totalCcdPackets)))
                
                #self.process_queue()
                self.after(10,self.process_queue)
            except queue.Empty:
                self.after(10,self.process_queue)

    def saveToTxt(self):
        fileName = self.outputDir + self.id + "_output" + ".txt"
        text_file = open(fileName, "w")
        text_file.write("id= %s \n" % self.id)
        text_file.write("CCDSEL= %s \n" % self.ccdSelect)
        text_file.write("EXPTS= %s \n" % self.exposureStart)
        text_file.write("EXPTSS= %s \n" % self.exposureFraction)
        text_file.write("WDW= %s \n" % self.wdwMode)
        text_file.write("WDWOV= %s \n" % self.windowOverflow)
        text_file.write("JPEGQ= %s \n" % self.jpegQuality)
        text_file.write("FRAME= %s \n" % self.nRows )
        text_file.write("NROW= %s \n" % self.nRows)
        text_file.write("NRBIN= %s \n" % self.nRowBin)
        text_file.write("NRSKIP= %s \n" % self.nRowSkip)
        text_file.write("NCOL= %s \n" % self.nCols)
        text_file.write("NCBIN= %s \n" % self.nColBin)
        text_file.write("NCSKIP= %s \n" % self.nColSkip)
        text_file.write("NFLUSH= %s \n" % self.nflush)
        text_file.write("TEXPMS= %s \n" % self.exposureTime)
        text_file.write("GAIN= %s \n" % self.gain)
        text_file.write("TEMP= %s \n" % self.temp)
        text_file.write("FBINOV= %s \n" % self.fbinov)
        text_file.write("LBLNK= %s \n" % self.lblnk)
        text_file.write("TBLNK= %s \n" % self.tblnk)
        text_file.write("ZERO= %s \n" % self.zero)
        text_file.write("TIMING1= %s \n" % self.timing1)
        text_file.write("TIMING2= %s \n" % self.timing2)
        text_file.write("VERSION= %s \n" % self.version)
        text_file.write("TIMING3= %s \n" % self.timing3)
        text_file.write("NBC= %s \n" % self.nBadCols)
        for n in range(self.nBadCols):
            text_file.write("BC= %s \n" % self.BadCols[n])
        
        text_file.close()  
    
    #Save jpeg image to file
    def saveToJpeg(self):
        writeFormat = 'wb'

        fileName = self.outputDir + self.id + ".jpg"
        f=open(fileName,writeFormat)
        f.write(self.imageData)
        f.close()
        self.imageData=bytes()
        self.convertAndDisplayImage(fileName)

    #Save raw image to pnm file
    def saveToPnm(self):
        fileName = self.outputDir + self.id + ".pnm"
        f=open(fileName,"wb")
        #TODO get the size of the image
        imsize = (self.nRows, self.nCols + 1 )
        pnm_header = "P5\n"+str(imsize[1])+" "+str(imsize[0])+"\n65535\n"
        f.write(bytearray(pnm_header, "utf8"))
        
        # Make the image a proper pnm file
        data = np.frombuffer(self.imageData, dtype=np.uint16)

        # And save it
        f.write(data.byteswap().tobytes())
        f.close()
        self.imageData=bytes()
        # TODO display image as well

        self.image = data.reshape(imsize) #reshape image
        self.refresh_image()
       
    #Convert 12-bit jpeg to pgm & display image
    def convertAndDisplayImage(self,jpegFile):           
        #outputFile= jpegFile[:-4] + ".pgm"   
        try:
            if self.jpegQuality <= 100:
                self.image = self.read12bit_jpeg(jpegFile) #read image       
            else:
                self.image = self.read16bit_jpeg(jpegFile) #read image    
            
            self.refresh_image()           
            
        except:
            print("JPEG conversion failed for " + jpegFile)        
    
    #Show image in viewer
    def refresh_image(self):
       
        if self.AutoVal.get():
            self.imshowobject = self.subplot.imshow(self.image)
            self.minVal.set(np.min(self.image))
            self.maxVal.set(np.max(self.image))
        else:
            self.imshowobject = self.subplot.imshow(self.image,vmin=self.minVal.get(),vmax=self.maxVal.get())
        
        self.colorbar = self.figure.colorbar(self.imshowobject, cax=self.cbaraxis)
        
        self.imageOut.show()
    
    #Call external application for conversion
    def read12bit_jpeg(self,fileName):
        djpegLocation = 'djpeg.exe'
        outputFile = fileName[:-4] + ".pnm"
    
        batcmd = djpegLocation + ' -pnm -outfile ' +outputFile + ' ' + fileName #call jpeg decompression executable            
        imagedata = subprocess.check_output(batcmd,shell=True) #load imagedata including header

        with open(outputFile,'rb') as f:
            imagedata=f.read()
                
        newLine=b'\n'
        imagedata=imagedata.split(newLine,3)    #split into magicnumber, shape, maxval and data

        imsize = imagedata[1].split() #size of image in height/width
        imsize = [int(i) for i in imsize]
        imsize.reverse() #flip size to get width/heigth
        maxval = int(imagedata[2])
        
        im = np.frombuffer(imagedata[3], dtype=np.uint16) #read image data
        
        im = im.reshape(imsize) #reshape image
        return im
    
    def read16bit_jpegfile(filename):
        im_object = Image.open(filename)
        im = np.asarray(im_object)
        return im
        
def UnsegmentedTimeNanoseconds(coarseTime, fineTime):
    nanos  = coarseTime * NANOS_PER_SECOND
    fine = math.ldexp(fineTime,-16)

    return int(nanos + round(fine*NANOS_PER_SECOND))   
        
#----------------- Main function ----------------

if __name__ == "__main__":
    app = matsViewer(None)
    app.title("MATS CCD Viewer")
    
    app.mainloop()
    

