#!/usr/bin/python

""" Module to check UBNT-AF24 radio links over HTTP """
__version__ = "1.0"
__author__ = "Zenon Mousmoulas"

import os
import sys
import socket
import traceback
import urllib2
import cookielib
import simplejson as json
from optparse import OptionGroup
from NagiosPlugin import NagiosPlugin
from MultiPartForm import MultiPartForm
from DictDotLookup import DictDotLookup

# Setup plugin
plugin = NagiosPlugin (version="1.0", usage="Usage: %prog -H <hostname> [-U <username>] -P <password> [options]", description="Nagios plugin for UBNT-AF24 radios (over HTTP)")

plugin.parser.get_option ("-w").help += "s (rxpower0,rxpower1,rxcapacity,txcapacity,txmodrate,distance,dactemp0,dactemp1,gps.dop_quality,gps.sats)"
plugin.parser.get_option ("-c").help += "s (rxpower0,rxpower1,rxcapacity,txcapacity,txmodrate,distance,dactemp0,dactemp1,gps.dop_quality,gps.sats)"

boolGroup = OptionGroup (plugin.parser, "Boolean check options")
boolGroup.add_option ("-b", "--boolean", help="Check that specific keys have particular values, otherwise the plugin returns CRITICAL (default: airfiber.rxpower0valid=1,airfiber.rxpower1valid=1,airfiber.rxoverload0=0,airfiber.rxoverload1=0,gps.status=1,gps.fix=1,airfiber.data_speed=1000Mbps-Full,airfiber.linkstate=operational)", default="airfiber.rxpower0valid=1,airfiber.rxpower1valid=1,airfiber.rxoverload0=0,airfiber.rxoverload1=0,gps.status=1,gps.fix=1,airfiber.data_speed=1000Mbps-Full,airfiber.linkstate=operational")
plugin.parser.add_option_group (boolGroup)

connGroup = OptionGroup (plugin.parser, "Connection options")
connGroup.add_option ("-H", "--httphost", help="HTTP(S) protocol, hostname, port (optional), as URL, e.g: http://example.com:port, https://example.com etc.")
plugin.parser.add_option_group (connGroup)

authGroup = OptionGroup (plugin.parser, "Authentication options")
authGroup.add_option ("-U", "--username", default="ubnt", help="username (default: 'ubnt')")
authGroup.add_option ("-P", "--password", help="password")
plugin.parser.add_option_group (authGroup)

try:
	plugin.begin()
	verbose = plugin.options.verbose

	# Validate arguments
	if (plugin.options.httphost is None):
		plugin.parser.error ("-H/--httphost is required")

	if (plugin.options.password is None):
		plugin.parser.error ("-P/--password option is required")

	# Prepare login
	form = MultiPartForm()
	form.add_field('username', plugin.options.username)
	form.add_field('password', plugin.options.password)
	form.add_field('Submit', 'Login')
	# We need session cookies
	cj = cookielib.LWPCookieJar()
	opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
	urllib2.install_opener(opener)
	# Shortcuts...
	urlopen = urllib2.urlopen
	Request = urllib2.Request
	# Set timeout for requests
	socket.setdefaulttimeout(10)

	# Must get a session cookie first
	req = Request(plugin.options.httphost + '/login.cgi')
	if (verbose >= 2):
		print "Opening session"
	resp = urlopen(req)

	# Post the form to login
	form.add_field('uri', '/status.cgi')
	body = str(form)
	req = Request(plugin.options.httphost + '/login.cgi')
	req.add_header('Content-type', form.get_content_type())
	req.add_header('Content-length', len(body))
	req.add_data(body)
	if (verbose >= 2):
		print "Logging in and collecting data"
	resp = urlopen(req)

	# Check we reached the right page after redirection post login
 	if (resp.geturl() != plugin.options.httphost + '/status.cgi'):
		if (verbose >= 2):
			print "Login may have failed"
 		raise Exception("Reached a wrong page: " + resp.geturl())

	# Check content-type (last resort) before passing to JSON parser
	contype = resp.info()['Content-type']
	if (contype != "application/json"):
		if (verbose >= 2):
			print "Login may have failed"
		raise Exception("Response has wrong content-type: " + contype)

	data = json.loads(resp.read())

	# Avoid leaving open sessions
	req = Request(plugin.options.httphost + '/logout.cgi')
	resp = urlopen(req)

	# Collect performance data
	plugin.addPerformanceData ('rxpower0', str (data['airfiber']['rxpower0']), 0, min='-100', max='0')
	plugin.addPerformanceData ('rxpower1', str (data['airfiber']['rxpower1']), 1, min='-100', max='0')
	plugin.addPerformanceData ('rxcapacity', data['airfiber']['rxcapacity'], 2, min='0', max='750000000')
	plugin.addPerformanceData ('txcapacity', data['airfiber']['txcapacity'], 3, min='0', max='750000000')
	txmodrate = str (data['airfiber']['txmodrate']).rstrip('x')
	plugin.addPerformanceData ('txmodrate', txmodrate, 4, min='0', max='6')
	plugin.addPerformanceData ('distance', data['wireless']['distance'], 5, min='100', max='15000')
	plugin.addPerformanceData ('dactemp0', str (data['airfiber']['dactemp0']), 6, min='-50', max='65')
	plugin.addPerformanceData ('dactemp1', str (data['airfiber']['dactemp1']), 7, min='-50', max='65')
	gps_dop = float (data['gps']['dop'])
	gps_dop_qual = 0
	if (gps_dop > 20):
		gps_dop_qual = 10
	elif (gps_dop > 15):
		gps_dop_qual = 20
	elif (gps_dop > 10):
		gps_dop_qual = 30
	elif (gps_dop > 7):
		gps_dop_qual = 40
	elif (gps_dop > 5):
		gps_dop_qual = 50
	elif (gps_dop > 3.5):
		gps_dop_qual = 60
	elif (gps_dop > 2):
		gps_dop_qual = 70
	elif (gps_dop > 1.5):
		gps_dop_qual = 80
	elif (gps_dop > 1):
		gps_dop_qual = 90
	elif (gps_dop > 0):
		gps_dop_qual = 100
	plugin.addPerformanceData ('gps.dop_quality', gps_dop_qual, 8, min='0', max='100', UOM='%')
	plugin.addPerformanceData ('gps.sats', data['gps']['sats'], 9, min='0', max='10')

 	# Check thresholds
	if (plugin.checkThreshold (data['airfiber']['rxpower0'], 0) != plugin.returnValues['OK']):
		plugin.returnString += " rxpower0"
	if (plugin.checkThreshold (data['airfiber']['rxpower1'], 1) != plugin.returnValues['OK']):
		plugin.returnString += " rxpower1"
	if (plugin.checkThreshold (data['airfiber']['rxcapacity'], 2) != plugin.returnValues['OK']):
		plugin.returnString += " rxcapacity"
	if (plugin.checkThreshold (data['airfiber']['txcapacity'], 3) != plugin.returnValues['OK']):
		plugin.returnString += " txcapacity"
	if (plugin.checkThreshold (int (txmodrate), 4) != plugin.returnValues['OK']):
		plugin.returnString += " txmodrate"
	if (plugin.checkThreshold (data['wireless']['distance'], 5) != plugin.returnValues['OK']):
		plugin.returnString += " distance"
	if (plugin.checkThreshold (data['airfiber']['dactemp0'], 6) != plugin.returnValues['OK']):
		plugin.returnString += " dactemp0"
	if (plugin.checkThreshold (data['airfiber']['dactemp1'], 7) != plugin.returnValues['OK']):
		plugin.returnString += " dactemp1"
	if (plugin.checkThreshold (gps_dop_qual, 8) != plugin.returnValues['OK']):
		plugin.returnString += " gps.dop_quality"
	if (plugin.checkThreshold (data['gps']['sats'], 9) != plugin.returnValues['OK']):
		plugin.returnString += " gps.sats"

	# Check booleans
	data = DictDotLookup(data)
	boolchecks = plugin.options.boolean.split(",")
	for boolcheck in boolchecks:
		if (not len (boolcheck)):
			continue
		boolcheckKeyVal = boolcheck.partition("=")
		if (not len (boolcheckKeyVal[0]) or not len (boolcheckKeyVal[2])):
			continue
		try:
			boolcheckKeyVal_actual = eval ('data.' + boolcheckKeyVal[0])
		except AttributeError:
			plugin.returnValue = plugin.returnValues['UNKNOWN']
			plugin.returnString = boolcheckKeyVal[0]
			plugin.finish()
		if (not str (boolcheckKeyVal_actual) == boolcheckKeyVal[2]):
			plugin.returnValue = plugin.returnValues['CRITICAL']
			plugin.returnString += " %s" % boolcheckKeyVal[0]
		plugin.addPerformanceData (boolcheckKeyVal[0], str (boolcheckKeyVal_actual))

 	# Output result
 	plugin.finish()

except Exception, e:
	if (verbose >= 2):
		traceback.print_exc(e)
	plugin.returnValue = plugin.returnValues['UNKNOWN']
	plugin.returnString = str(e)

 	# Output result
 	plugin.finish()
