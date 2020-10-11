#  NanoVNASaver
#
#  A python program to view and export Touchstone data from a NanoVNA
#  Copyright (C) 2019, 2020  Rune B. Broberg
#  Copyright (C) 2020 NanoVNA-Saver Authors
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import argparse
import logging
import sys
import threading
import time
from datetime import datetime
from collections import OrderedDict
from time import sleep, strftime, localtime
from typing import List


from .Hardware.Hardware import Interface, get_interfaces, get_VNA
from .Hardware.VNA import VNA
from .RFTools import Datapoint, corr_att_data
from .Calibration import Calibration
from .SweepWorker import SweepWorker
from .Settings import BandsModel, Sweep
from .Touchstone import Touchstone
from .About import VERSION
from .Controls import SweepControl

logger = logging.getLogger(__name__)



class NanoVNASaver():
    version = VERSION
    scaleFactor = 1
    # logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    #module_logger = logging.getLogger('spam_application.auxiliary')



    def __init__(self):
        self.s21att = 0.0
        
        parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-o", "--output", type=str,
                        help="output location (folder)")
        parser.add_argument("-f", "--start", type=int,
                        help="start frequency in Hz")
        parser.add_argument("-t", "--stop", type=int,
                        help="stop frequency in Hz")
        parser.add_argument("-i", "--infinite", action="store_true",
                        help="infinite saving 2port touchstone files, otherwise once")

        args = parser.parse_args()
        self.output_path = args.output
        self.frequency_start = args.start 
        self.frequency_stop = args.stop 
        if args.infinite:
            self.infinite = True
        else:
            self.infinite = False


        #print(f"Settings: {self.settings.fileName()}")
        self.sweep = Sweep()
        self.worker = SweepWorker(self)

        self.sweep.start = self.frequency_start
        self.sweep.end = self.frequency_stop
        if not self.infinite:
            self.sweep.properties.mode = 0 #single

        self.interface = Interface("serial", "None")
        self.vna = VNA(self.interface)

        self.dataLock = threading.Lock()
        # TODO: use Touchstone class as data container
        self.data11: List[Datapoint] = []
        self.data21: List[Datapoint] = []
        self.referenceS11data: List[Datapoint] = []
        self.referenceS21data: List[Datapoint] = []

        self.sweepSource = ""
        self.referenceSource = ""

        self.calibration = Calibration()


        self.rescanSerialPort()
        sleep(0.5)
        self.connect_device()
        self.thread_control = threading.Thread(target=self.controlThread)#, args=(2, "Thread-2", 2) )
        self.thread_runner = threading.Thread(target=self.sweep_start)#, args=(1, "Thread-1", 1) )
        self.thread_control.start()
        self.thread_runner.start()
        #self.controlThread()


    def controlThread(self):
        logger.info("         starting main loop")
        while 1:
            #if updated call 
            if self.worker.updated:
                now = datetime.now()
                self.worker.updated = 0
                print("updated")
                self.dataUpdated()
                path = self.output_path + now.strftime("%Y%m%d_%H%M%S") + ".s2p"
                self.exportFile(4,path)

            #if thread_runner not running, exit
            if hasattr(self.worker, 'finished'):
                if self.worker.finished :
                    print("not running")
                    return
                    #self.thread_runner.kill()

                #return
            sleep(0.1)

    def rescanSerialPort(self):
        get_interfaces()

    def exportFile(self, nr_params, filename):
        ts = Touchstone(filename)
        ts.sdata[0] = self.data11
        if nr_params > 1:
            ts.sdata[1] = self.data21
            for dp in self.data11:
                ts.sdata[2].append(Datapoint(dp.freq, 0, 0))
                ts.sdata[3].append(Datapoint(dp.freq, 0, 0))
        try:
            ts.save(nr_params)
        except IOError as e:
            logger.exception("Error during file export: %s", e)
            return

    def connect_device(self):
        if not self.interface:

            return
        with self.interface.lock:
        #    self.interface = self.serialPortInput.currentData()
            interfaces = get_interfaces() 
            self.interface = interfaces[0]
            logger.info("Connection %s", self.interface)
            try:
                self.interface.open()
                self.interface.timeout = 0.05
            except (IOError, AttributeError) as exc:
                logger.error("Tried to open %s and failed: %s",
                             self.interface, exc)
                return
            if not self.interface.isOpen():
                logger.error("Unable to open port %s", self.interface)
                return
        sleep(0.1)
        try:
            self.vna = get_VNA(self.interface)
        except IOError as exc:
            logger.error("Unable to connect to VNA: %s", exc)


#frequencies from parameter
        frequencies = self.vna.readFrequencies()
        if not frequencies:
            logger.warning("No frequencies read")
            return
        logger.info("Read starting frequency %s and end frequency %s",
                    frequencies[0], frequencies[-1])

        logger.debug("Starting initial sweep")
#        self.sweep_start()
        #self.thread_runner.start()

    def disconnect_device(self):
        with self.interface.lock:
            logger.info("Closing connection to %s", self.interface)
            self.interface.close()

    def sweep_start(self):
        print("start worker")
        # Run the device data update
        if not self.vna.connected():
            print("not connected")
            return
        self.worker.stopped = False
        logger.debug("Starting worker thread")
        self.worker.run()

        logger.debug("Starting worker thread old")
 #       self.threadpool.start(self.worker)

    def sweep_stop(self):
        self.worker.stopped = True

    def saveData(self, data, data21, source=None):
        with self.dataLock:
            self.data11 = data
            self.data21 = data21
            if self.s21att > 0:
                self.data21 = corr_att_data(self.data21, self.s21att)
        if source is not None:
            self.sweepSource = source
        else:
            self.sweepSource = (
                f"{self.sweep.properties.name}"
                f" {strftime('%Y-%m-%d %H:%M:%S', localtime())}"
            ).lstrip()

    def dataUpdated(self):
        with self.dataLock:
            s11data = self.data11[:]
            s21data = self.data21[:]

        if s11data:
            min_vswr = min(s11data, key=lambda data: data.vswr)
            
        if s21data:
            min_gain = min(s21data, key=lambda data: data.gain)
            max_gain = min(s21data, key=lambda data: data.gain)
#                    self.updateTitle()
#        self.dataAvailable.emit()
#write file

    def setReference(self, s11data=None, s21data=None, source=None):
        if not s11data:
            with self.dataLock:
                s11data = self.data11[:]
                s21data = self.data21[:]

        self.referenceS11data = s11data
        for c in self.s11charts:
            c.setReference(s11data)

        self.referenceS21data = s21data
        for c in self.s21charts:
            c.setReference(s21data)

        for c in self.combinedCharts:
            c.setCombinedReference(s11data, s21data)

        if source is not None:
            # Save the reference source info
            self.referenceSource = source
        else:
            self.referenceSource = self.sweepSource
        self.updateTitle()

    def resetReference(self):
        self.referenceS11data = []
        self.referenceS21data = []
        self.referenceSource = ""
        self.updateTitle()
        for c in self.subscribing_charts:
            c.resetReference()

    def loadReferenceFile(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            filter="Touchstone Files (*.s1p *.s2p);;All files (*.*)")
        if filename != "":
            self.resetReference()
            t = Touchstone(filename)
            t.load()
            self.setReference(t.s11data, t.s21data, filename)

    def showFatalSweepError(self):
        self.showError(self.worker.error_message)
        self.stopSerial()

    def showSweepError(self):
        self.showError(self.worker.error_message)
        try:
            self.vna.flushSerialBuffers()  # Remove any left-over data
            self.vna.reconnect()  # try reconnection
        except IOError:
            pass

