"""
Serial communication with the printer for printing is done from a separate process,
this to ensure that the PIL does not block the serial printing.

This file is the 2nd process that is started to handle communication with the printer.
And handles all communication with the initial process.
"""

__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"
import sys
import time
import os
import json

from Cura.util import machineCom

class serialComm(object):
	"""
	The serialComm class is the interface class which handles the communication between stdin/stdout and the machineCom class.
	This interface class is used to run the (USB) serial communication in a different process then the GUI.
	"""
	def __init__(self, portName, baudrate, com):
		self._comm = None
		self._gcodeList = []

		try:
			baudrate = int(baudrate)
		except ValueError:
			baudrate = 0
		self._comm = com(portName, baudrate, callbackObject=self)

	def mcLog(self, message):
		sys.stdout.write('log:%s\n' % (message))

	def mcTempUpdate(self, temp, bedTemp, targetTemp, bedTargetTemp):
		sys.stdout.write('temp:%s:%s:%f:%f\n' % (json.dumps(temp), json.dumps(targetTemp), bedTemp, bedTargetTemp))

	def mcStateChange(self, state):
		if self._comm is None:
			return
		sys.stdout.write('state:%d:%s\n' % (state, self._comm.getStateString()))

	def mcMessage(self, message):
		sys.stdout.write('message:%s\n' % (message))

	def mcProgress(self, lineNr):
		sys.stdout.write('progress:%d\n' % (lineNr))

	def mcZChange(self, newZ):
		sys.stdout.write('changeZ:%d\n' % (newZ))

	def monitorStdin(self):
		while not self._comm.isClosed():
			line = sys.stdin.readline()
			if not line:
				sys.stderr.write("\nClient closed connection to printer\n")
				return
			line = line.strip()
			line = line.split(':', 1)
			if line[0] == 'STOP':
				self._comm.cancelPrint()
				self._gcodeList = ['M110']
			elif line[0] == 'G':
				self._gcodeList.append(line[1])
			elif line[0] == 'C':
				self._comm.sendCommand(line[1])
			elif line[0] == 'START':
				self._comm.printGCode(self._gcodeList)
			else:
				sys.stderr.write(str(line))

def startMonitor(portName, baudrate, printer='printer'):
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
	com = machineCom.PrinterCom
	if printer == 'color':
		com = machineCom.ColorCom
	comm = serialComm(portName, baudrate, com)
	comm.monitorStdin()

def main():
	if len(sys.argv) != 4:
		return
	portName, baudrate, printer = sys.argv[1], sys.argv[2], sys.argv[3]
	startMonitor(portName, baudrate, printer)

if __name__ == '__main__':
	main()
