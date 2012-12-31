#!/usr/bin/python

""" MRTG probe for UBNT devices over HTTP """
__version__ = "1.0"
__author__ = "Zenon Mousmoulas"

import os
import sys
import socket
import traceback
import urllib2
import cookielib
if sys.version_info < (2, 6):
	import simplejson as json
else:
	import json
from optparse import OptionParser, OptionValueError, OptionGroup
from MultiPartForm import MultiPartForm
from DictDotLookup import DictDotLookup

# Setup argument handler
parser = OptionParser (usage="Usage: %prog -H <hostname> [-U <username>] -P <password> -s <source> -k <key1> <key2> [options]", description="MRTG probe for UBNT devices (over HTTP)", epilog=None)
parser.add_option ("-V", "--version", action="store_true", help="show the version and exit")
parser.add_option ("-v", "--verbose", action="count", help="show debugging information")
parser.add_option ("-t", "--timeout", type="int", default=10, help="seconds before plugin times out (default: 10)")

dataGroup = OptionGroup (parser, "Options for data source and values returned by the program")
dataGroup.add_option("-s", "--source", help="Specify the source of data the program will poll. This option expects exactly one (1) argument that will be used to construct the URL to be requested through HTTP from the device: GET /<source>.cgi")
dataGroup.add_option("-k", "--keys", nargs=2, help="Pick the keys that you want the program to return values for. This option must be followed by exactly two (2) arguments. Any key that appears in the selected data source may be given, using dotted notation to perform nested lookups in JSON data structures. Example: -k airfiber.txcapacity airfiber.rxcapacity")
dataGroup.add_option("-f", "--formulas", nargs=2, help="Specify optional formulas (expressions to be interepreted by Python using eval()) that shall be used to modify values before they are returned by the program. This option must be followed by exactly two (2) arguments. The order in which the formulas are given corresponds to the order that keys are specified. Any occurences of VAL in a formula will be replaced by the corresponding value. If an empty string is given processing is skipped for the corresponding value. Example: -f \"VAL*1000\" \"VAL/1000\"")
parser.add_option_group (dataGroup)

connGroup = OptionGroup (parser, "Connection options")
connGroup.add_option ("-H", "--httphost", help="HTTP(S) protocol, hostname, port (optional), as URL, e.g: http://example.com:port, https://example.com etc.")
parser.add_option_group (connGroup)

authGroup = OptionGroup (parser, "Authentication options")
authGroup.add_option ("-U", "--username", default="ubnt", help="username (default: 'ubnt')")
authGroup.add_option ("-P", "--password", help="password")
parser.add_option_group (authGroup)

try:
	(options, args) = parser.parse_args()
	verbose = options.verbose

	if (options.version):
		print "%s %s" % (os.path.basename (sys.argv[0]), __version__)
		sys.exit()

	# Validate arguments
	if (options.httphost is None):
		parser.error ("-H/--httphost is required")

	if (options.password is None):
		parser.error ("-P/--password option is required")

	if (options.source is None):
		parser.error ("-s/--source option is required")

	datasourceuri = "/%s.cgi" % options.source

	if (options.keys is None):
		parser.error ("-k/--keys option is required")

	# Prepare login
	form = MultiPartForm()
	form.add_field('username', options.username)
	form.add_field('password', options.password)
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
	req = Request(options.httphost + '/login.cgi')
	if (verbose >= 2):
		print "Opening session"
	resp = urlopen(req)

	# Post the form to login
	form.add_field('uri', datasourceuri)
	body = str(form)
	req = Request(options.httphost + '/login.cgi')
	req.add_header('Content-type', form.get_content_type())
	req.add_header('Content-length', len(body))
	req.add_data(body)
	if (verbose >= 2):
		print "Logging in and collecting data"
	resp = urlopen(req)

	# Check we reached the right page after redirection post login
	if (resp.geturl() != options.httphost + datasourceuri):
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
	data = DictDotLookup(data)

	# Avoid leaving open sessions
	req = Request(options.httphost + '/logout.cgi')
	resp = urlopen(req)

	returndata = []
	for key in options.keys:
		if (not len (key)):
			continue

		try:
			key_data = eval ('data.' + key)
		except AttributeError:
			raise Exception("No key %s found in data source (URL: %s)" % (key, options.httphost + datasourceuri))

		if (options.formulas is not None):
			formula = options.formulas[options.keys.index(key)]
			if (len (formula)):
				formula = formula.replace("VAL", "key_data")
				key_data = eval (formula)

		returndata.append(key_data)

	for val in returndata:
		print val

except Exception, e:
	if (verbose >= 2):
		traceback.print_exc(e)
	print "ERROR: %s" % str(e)
