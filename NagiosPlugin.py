#!/usr/bin/python

""" Module to create Nagios plugins """
__version__ = "1.0"
__author__ = "Omni Flux"

import os
import sys
from optparse import OptionParser, OptionValueError, OptionGroup

class NagiosPlugin (object):
	returnValues = { 'OK' : 0, 'WARNING' : 1, 'CRITICAL' : 2, 'UNKNOWN' : 3 }

	@staticmethod
	def _isNumeric (string):
		try:
			float (string)
			return True
		except ValueError:
			return False

	class _DefaultThresholdHandler (object):
		def __init__ (self, start = None, end = None, exclusive = True):
			self.start = start
			self.end = end
			self.exclusive = exclusive

		def __str__ (self):
			start = str (self.start) if (self.start is not None) else "~"
			end = str (self.end) if (self.end is not None) else ""
			exclusive = "" if (self.exclusive) else "@"
			return exclusive + start + ":" + end

		def checkValue (self, value):
			if (not NagiosPlugin._isNumeric (value)):
				return None

			if (self.start is not None and float (value) < float (self.start)):
				return True if (self.exclusive) else False
			elif (self.end is not None and float (value) > float (self.end)):
				return True if (self.exclusive) else False
			return False if (self.exclusive) else True

		@staticmethod
		def parseThreshold (option, opt, value, parser):
			thresholds = []
			values = value.split (",")
			for value in values:
				# Check if threshold specified
				if (not len (value)):
					thresholds.append (None)
					continue

				# Check if threshold is exclusive
				if (value[0] == "@"):
					exclusive = False
					value = value[1:]
				else:
					exclusive = True

				threshold = None
				thresholdValue = value.partition (":")

				# Match 10, 10: and 10:~
				if (thresholdValue[2] in ("", "~")):
					# Match 10
					if (thresholdValue[1] == "" and NagiosPlugin._isNumeric (thresholdValue[0])):
						if (float (thresholdValue[0]) < 0):
							threshold = NagiosPlugin._DefaultThresholdHandler (thresholdValue[0], 0, exclusive)
						else:
							threshold = NagiosPlugin._DefaultThresholdHandler (0, thresholdValue[0], exclusive)
					# Match 10: and 10:~
					elif (thresholdValue[1] == ":" and NagiosPlugin._isNumeric (thresholdValue[0])):
						threshold = NagiosPlugin._DefaultThresholdHandler (thresholdValue[0], None, exclusive)
				# Match :10, ~:10 and 10:20
				elif (thresholdValue[1] == ":" and NagiosPlugin._isNumeric (thresholdValue[2])):
					# Match :10 and ~:10
					if (thresholdValue[0] in ("", "~")):
						threshold = NagiosPlugin._DefaultThresholdHandler (None, thresholdValue[2], exclusive)
					# Match 10:20
					elif (NagiosPlugin._isNumeric (thresholdValue[0]) and float (thresholdValue[0]) <= float (thresholdValue[2])):
						threshold = NagiosPlugin._DefaultThresholdHandler (thresholdValue[0], thresholdValue[2], exclusive)

				# No match
				if (threshold is not None):
					thresholds.append (threshold)
				else:
					raise OptionValueError ("'%s' is not a valid range for '%s'" % (value, opt))

			setattr (parser.values, option.dest, thresholds)

	def __init__ (self, version, description, usage = None, timeout = 10, epilog = None, thresholdHandler = None, thresholdWarningDefault = [], thresholdCriticalDefault = []):
		self.version = version
		self.description = description
		self.epilog = epilog
		self.returnValue = self.returnValues['OK']
		self.returnString = ""
		self.performanceData = []

		# Setup default threshold handler
		if (thresholdHandler is None):
			thresholdHandler = self._DefaultThresholdHandler

		# Setup argument handler
		self.parser = OptionParser (usage=usage, description=description, epilog=epilog)
		self.parser.add_option ("-V", "--version", action="store_true", help="show the version and exit")
		self.parser.add_option ("-v", "--verbose", action="count", help="show debugging information")
	 	self.parser.add_option ("-t", "--timeout", type="int", default=timeout, help="seconds before plugin times out (default: " + str (timeout) + ")")
		thresholdGroup = OptionGroup (self.parser, "Threshold options")
	 	thresholdGroup.add_option ("-w", "--warning", action="callback", type="string", help="warning threshold", callback=thresholdHandler.parseThreshold, default=thresholdWarningDefault)
	 	thresholdGroup.add_option ("-c", "--critical", action="callback", type="string", help="critical threshold", callback=thresholdHandler.parseThreshold, default=thresholdCriticalDefault)
		self.parser.add_option_group (thresholdGroup)

	def begin (self):
		# Process arguments
		(self.options, args) = self.parser.parse_args()

		if (self.options.version):
			print os.path.basename (sys.argv[0]) + " " + self.version
			sys.exit()

	def finish (self):
		# Generate output string
		for key in self.returnValues:
			if (self.returnValues[key] == self.returnValue):
				output = key
				break
		if (len (self.returnString)):
			output += ": %s" % self.returnString.strip()

		# Generate output with extended status data
		if (len (self.performanceData)):
			output += " - "
			for item in self.performanceData:
				output += "%s=%s" % (item['label'], item['value'])
				if (item['UOM'] is not None):
					output += item['UOM']
				output += " "

		# Generate performance data string
		if (len (self.performanceData)):
			output += "|"
			for item in self.performanceData:
				output += "'%s'=%s" % (item['label'], item['value'])
				if (item['UOM'] is not None):
					output += item['UOM']
				output += ";"
				if (item['warn'] is not None):
					output += item['warn']
				output += ";"
				if (item['crit'] is not None):
					output += item['crit']
				output += ";"
				if (item['min'] is not None):
					output += item['min']
				output += ";"
				if (item['max'] is not None):
					output += item['max']

		# Print output
		print ''.join (output)

		# Exit with correct return value
		sys.exit (self.returnValue)

	def addPerformanceData (self, label, value, thresholdPosition = 0, UOM = None, warn = None, crit = None, min = None, max = None):
		# Get warning and critical ranges
		if (thresholdPosition < len (self.options.critical) and self.options.critical[thresholdPosition] is not None):
			crit = str (self.options.critical[thresholdPosition])
		if (thresholdPosition < len (self.options.warning) and self.options.warning[thresholdPosition] is not None):
			warn = str (self.options.warning[thresholdPosition])

		# Add performance data to stack
		self.performanceData.append ({'label': label, 'value': value, 'UOM': UOM, 'warn': warn, 'crit': crit, 'min': min, 'max': max})

	def checkThreshold (self, value, thresholdPosition = 0):
		if (thresholdPosition < len (self.options.critical) and self.options.critical[thresholdPosition] is not None):
			thresholdReached = self.options.critical[thresholdPosition].checkValue (value)
			if (thresholdReached):
				self.returnValue = self.returnValues['CRITICAL']
				return self.returnValues['CRITICAL']

		if (thresholdPosition < len (self.options.warning) and self.options.warning[thresholdPosition] is not None):
			thresholdReached = self.options.warning[thresholdPosition].checkValue (value)
			if (thresholdReached):
				if (self.returnValue != self.returnValues['CRITICAL']):
					self.returnValue = self.returnValues['WARNING']
				return self.returnValues['WARNING']

		return self.returnValues['OK']
