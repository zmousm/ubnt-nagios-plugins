ubnt-nagios-plugins
===================

Nagios plugins for monitoring UBNT radio links.
Supported platforms are:
- AirMAX (http://www.ubnt.com/airmax) and
- AirFiber (http://www.ubnt.com/airfiber)

AirMAX plugin implicitly supports only point-to-point links, i.e. an
AP with a single STA. AirFiber is point-to-point anyway; only AF24 is
supported (the only model available at the time of this writing).

The plugins login to the device's web interface (a read-only account
can be used) and fetch data in JSON format by requesting
e.g. /status.cgi; the same thing happens for data shown in the "main"
tab through a web browser.

Both plugins work with warning and critical thresholds. The threshold
format is explained here:
http://nagiosplug.sourceforge.net/developer-guidelines.html#THRESHOLDFORMAT

See the plugin usage (run with -h) for the labels of these
thresholds. They should be self-explanatory for each platform.

The AirFiber plugin additionally supports an arbitrary number of
checks for on/off values, as plenty of them are available on this
platform. The most meaningful are used by default (see the help for
boolean checks), but more may be available; look for them in the
output of http://device/status.cgi. To give one more example of how
this can be used, if you wanted to check that the operating speed of
eth0 (the config port on AF24) is 100 Mbps, you would append this to
the boolean checks: interfaces[2].status.speed=100


The plugins are inspired by the script posted here:
http://forum.ubnt.com/showthread.php?t=27170
and are heavily based on this implementation:
http://www.omniflux.com/devel/#ubntm
which is discussed here:
http://forum.ubnt.com/showthread.php?t=27170

The basic difference is that data is fetched over HTTP rather than
over SSH. Arbitrary checks, specified in dotted notation (see above),
is another difference.

--
Zenon Mousmoulas

Last updated: 2012-12-11
