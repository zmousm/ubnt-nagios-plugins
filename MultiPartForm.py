"""Accumulate the data to be used when posting a form."""
__version__ = "1.0"
__author__ = "unknown"
# zmousm: taken from here and simplified:
# http://code.google.com/p/uthcode/source/browse/trunk/python/urllib2-binary-upload.py?spec=svn533&r=533
# there are various other recipes, or one could also use poster:
# http://atlee.ca/software/poster/index.html
# but this was the easiest solution at the time (2012-03-16)

import itertools
import mimetools
import mimetypes

class MultiPartForm(object):

    def __init__(self):
        self.form_fields = []
        self.boundary = mimetools.choose_boundary()
        return
    
    def get_content_type(self):
        return 'multipart/form-data; boundary=%s' % self.boundary

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append((name, value))
        return

    def __str__(self):
        """Return a string representing the form data."""
        # Build a list of lists, each containing "lines" of the
        # request.  Each part is separated by a boundary string.
        # Once the list is built, return a string where each
        # line is separated by '\r\n'.  
        parts = []
        part_boundary = '--' + self.boundary
        
        # Add the form fields
        parts.extend(
            [ part_boundary,
              'Content-Disposition: form-data; name="%s"' % name,
              '',
              value,
            ]
            for name, value in self.form_fields
            )

        # Flatten the list and add closing boundary marker,
        # then return CR+LF separated data
        flattened = list(itertools.chain(*parts))
        flattened.append('--' + self.boundary + '--')
        flattened.append('')
        return '\r\n'.join(flattened)
