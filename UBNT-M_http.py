#!/usr/bin/python

""" Module to check UBNT-M radio links over HTTP """
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

# Setup plugin
plugin = NagiosPlugin (version="1.0", usage="Usage: %prog -H <hostname> [-U <username>] -P <password> [options]", description="Nagios plugin for UBNT-M radios (over HTTP)")

plugin.parser.get_option ("-w").help += "s (signal,signal chain0,signal chain1,noise,ccq,airmax quality,airmax capacity,tx rate,rx rate)"
plugin.parser.get_option ("-c").help += "s (signal,signal chain0,signal chain1,noise,ccq,airmax quality,airmax capacity,tx rate,rx rate)"

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
	plugin.addPerformanceData ('signal', str (data['wireless']['signal']), 0, min='-100', max='0')
	plugin.addPerformanceData ('signalchain0', str ((96 - data['wireless']['chainrssi'][0]) * -1), 1, min='-100', max='0')
	plugin.addPerformanceData ('signalchain1', str ((96 - data['wireless']['chainrssi'][1]) * -1), 2, min='-100', max='0')
	plugin.addPerformanceData ('noise', str (data['wireless']['noisef']), 3, min='-100', max='0')
	plugin.addPerformanceData ('ccq', str (data['wireless']['ccq'] / 10), 4, UOM='%')
	plugin.addPerformanceData ('airmaxquality', str (data['wireless']['polling']['quality']), 5, UOM='%')
	plugin.addPerformanceData ('airmaxcapacity', str (data['wireless']['polling']['capacity']), 6, UOM='%')
	plugin.addPerformanceData ('txrate', data['wireless']['txrate'], 7, min='0', max='270')
	plugin.addPerformanceData ('rxrate', data['wireless']['rxrate'], 8, min='0', max='270')

 	# Check thresholds
	if (plugin.checkThreshold (data['wireless']['signal'], 0) != plugin.returnValues['OK']):
		plugin.returnString += " signal"
	if (plugin.checkThreshold ((96 - data['wireless']['chainrssi'][0]) * -1, 1) != plugin.returnValues['OK']):
		plugin.returnString += " signalchain0"
	if (plugin.checkThreshold ((96 - data['wireless']['chainrssi'][1]) * -1, 2) != plugin.returnValues['OK']):
		plugin.returnString += " signalchain1"
	if (plugin.checkThreshold (data['wireless']['noisef'], 3) != plugin.returnValues['OK']):
		plugin.returnString += " noise"
	if (plugin.checkThreshold (data['wireless']['ccq'] / 10, 4) != plugin.returnValues['OK']):
		plugin.returnString += " ccq"
	if (plugin.checkThreshold (data['wireless']['polling']['quality'], 5) != plugin.returnValues['OK']):
		plugin.returnString += " airmaxquality"
	if (plugin.checkThreshold (data['wireless']['polling']['capacity'], 6) != plugin.returnValues['OK']):
		plugin.returnString += " airmaxcapacity"
	if (plugin.checkThreshold (data['wireless']['txrate'], 7) != plugin.returnValues['OK']):
		plugin.returnString += " txrate"
	if (plugin.checkThreshold (data['wireless']['rxrate'], 8) != plugin.returnValues['OK']):
		plugin.returnString += " rxrate"

 	# Output result
 	plugin.finish()

except Exception, e:
	if (verbose >= 2):
		traceback.print_exc(e)
	plugin.returnValue = plugin.returnValues['UNKNOWN']
	plugin.returnString = str(e)

 	# Output result
 	plugin.finish()
