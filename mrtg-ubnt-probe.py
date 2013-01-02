#!/usr/bin/python

""" MRTG probe for UBNT devices over HTTP """
__version__ = "2.0"
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
parser = OptionParser (usage="Usage: %prog -H <httphost> [-U <username>] -P <password> -k <source> <key> [options]", description="MRTG probe for UBNT devices (over HTTP)", epilog=None)
parser.add_option ("-V", "--version", action="store_true", help="show the version and exit")
parser.add_option ("-v", "--verbose", action="count", help="show debugging information")
parser.add_option ("-t", "--timeout", type="int", default=10, help="seconds before plugin times out (default: 10)")

connGroup = OptionGroup (parser, "Connection options")
connGroup.add_option ("-H", "--httphost", help="HTTP(S) protocol, hostname, port (optional), as URL, e.g: http://example.com:port, https://example.com etc.")
parser.add_option_group (connGroup)

authGroup = OptionGroup (parser, "Authentication options")
authGroup.add_option ("-U", "--username", default="ubnt", help="username (default: 'ubnt')")
authGroup.add_option ("-P", "--password", help="password")
parser.add_option_group (authGroup)

dataGroup = OptionGroup (parser, "Options for data sources and values returned by the program")
dataGroup.add_option("-k", "--source-key", nargs=2, action="append", help="This option should be used as many times as the number of values to be returned by the program. It must be followed by exactly two (2) arguments: the source of data the program will poll and the key for the value to be probed. The first argument will be used to construct the URL to be requested through HTTP from the device (GET /<source>.cgi). For the second argument, any key that appears in the selected data source may be given, using dotted notation to perform nested lookups in JSON data structures. Example: -k stats airfiber.txcapacity -k stats airfiber.rxcapacity")
dataGroup.add_option("-e", "--expression", action="append", help="Specify an optional expression [to be interpreted by Python using eval()] that shall be used to modify the corresponding value before it is returned. This option must be used as many times as the number of source-key options, so that expressions are matched with keys. Any occurences of VAL in an expression will be replaced by the corresponding value. If an empty string is given, processing is skipped for the corresponding value. Example: -e \"VAL*1000\" \"VAL/1000\"")
parser.add_option_group (dataGroup)

outputGroup = OptionGroup (parser, "Options for data output")
outputGroup.add_option("-f", "--output-format", type="choice", choices=["MRTG"], default="MRTG", help="Choose an output format for values returned by the program, available options are: MRTG (default): Print each value on a new line, MRTG expects two values.")
parser.add_option_group(outputGroup)

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

	if (options.source_key is None):
		parser.error ("-k/--source-key option is required")

	if ((options.expression is not None) and (len(options.expression) != len(options.source_key))):
		parser.error ("-e/--expression option must be used as many times as the -k/--source-key option")

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
	form.add_field('uri', '/index.cgi')
	body = str(form)
	req = Request(options.httphost + '/login.cgi')
	req.add_header('Content-type', form.get_content_type())
	req.add_header('Content-length', len(body))
	req.add_data(body)
	if (verbose >= 2):
		print "Logging in"
	resp = urlopen(req)
	# Check we reached the right page after redirection post login
	if (resp.geturl() != options.httphost + '/index.cgi'):
		if (verbose >= 2):
			print "Login may have failed"
		raise Exception("reached a wrong page: " + resp.geturl())

	# Avoid leaving open sessions
	def sessionclose():
		req = Request(options.httphost + '/logout.cgi')
		if (verbose >= 2):
			print "Logging out"
		resp = urlopen(req)

	# Poll data sources (only once for each data source)
	data = datasourceuri = {}
	for source in dict(options.source_key).keys():
		datasourceuri[source] = "/%s.cgi" % source

		req = Request(options.httphost + datasourceuri[source])
		if (verbose >= 2):
			print "Collecting data (%s)" % datasourceuri[source]
		resp = urlopen(req)

		# Check we reached the right page after redirection post login
		if (resp.geturl() != options.httphost + datasourceuri[source]):
			raise Exception("reached a wrong page: " + resp.geturl())

		# Check content-type (last resort) before passing to JSON parser
		contype = resp.info()['Content-type']
		if (contype != "application/json"):
			raise Exception("response has wrong content-type: " + contype)

		d = json.loads(resp.read())
		d = DictDotLookup(d)

		data[source] = d

	sessionclose()

	if (not len (data)):
		raise Exception("no valid sources or no data collected from sources")

	# Process keys
	returndata = []
	for i in range(len(options.source_key)):
		(source, key) = options.source_key[i]

		if (not len (key)):
			raise Exception("invalid key (empty string)")

		# Attempt to find key in data source
		try:
			key_data = eval ('data[source].%s' % key)
		except AttributeError:
			raise Exception("no key %s found in data source (URL: %s)" % (key, options.httphost + datasourceuri[source]))

		# Massage value with expression
		if (options.expression is not None):
			expression = options.expression[i]
			if (expression):
				expression = expression.replace("VAL", "key_data")
				key_data = eval (expression)

		returndata.append(key_data)

	# Return values
	if (options.output_format == "MRTG"):
		for val in returndata:
			print val

except Exception, e:
	if (verbose >= 2):
		traceback.print_exc(e)
	print "ERROR: %s" % str(e)

	sessionclose()

