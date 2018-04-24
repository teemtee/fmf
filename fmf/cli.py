# coding: utf-8

"""
Command line interface for the Flexible Metadata Format

Usage: fmf [path...] [options]

By default object identifiers and associated attributes are printed,
each on a separate line. It is also possible to use the --format option
together with --value options to generate custom output. Python syntax
for expansion using {} is used to place values as desired. For example:

    fmf --format 'name: {0}, tester: {1}\\n' \\
        --value 'name' --value 'data["tester"]'

Individual attribute values can be access through the 'data' dictionary,
variable 'name' contains the object identifier. Python modules 'os' and
'os.path' are available as well and can be used for processing attribute
values as desired:

    fmf --format '{}' --value 'os.path.dirname(data["path"])'

See online documentation for more details and examples:

    http://fmf.readthedocs.io/
"""

from __future__ import unicode_literals, absolute_import, print_function

import os
import os.path
import sys
import argparse

import fmf
import fmf.utils as utils

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Options
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Options(object):
    """ Command line options parser """

    def __init__(self):
        """ Prepare the parser. """
        self.parser = argparse.ArgumentParser(
            usage=__doc__)

        # Select
        group = self.parser.add_argument_group("Select")
        group.add_argument(
            "--key", dest="keys", action="append", default=[],
            help="Key content definition (required attributes)")
        group.add_argument(
            "--name", dest="names", action="append", default=[],
            help="List objects with name matching regular expression")
        group.add_argument(
            "--filter", dest="filters", action="append", default=[],
            help="Apply advanced filter (pydoc fmf.filter)")
        group.add_argument(
            "--whole", dest="whole", action="store_true",
            help="Consider the whole tree (leaves only by default)")

        # Formating
        group = self.parser.add_argument_group("Format")
        group.add_argument(
            "--brief", action="store_true",
            help="Show object names only (no attributes)")
        group.add_argument(
            "--format", dest="formatting", default=None,
            help="Custom output format using the {} expansion")
        group.add_argument(
            "--value", dest="values", action="append", default=[],
            help="Values for the custom formatting string")

        # Utilities
        group = self.parser.add_argument_group("Utils")
        group.add_argument(
            "--verbose", action="store_true",
            help="Print information about parsed files to stderr")
        group.add_argument(
            "--debug", action="store_true",
            help="Turn on debugging output, do not catch exceptions")

    def parse(self, cmdline=None):
        """ Parse the options. """
        # Split command line if given as string (used for testing)
        if isinstance(cmdline, type("")):
            cmdline = cmdline.split()
        # Otherwise use sys.argv (plus decode unicode for Python 2)
        if cmdline is None:
            try:
                cmdline = [arg.decode("utf-8") for arg in sys.argv[1:]]
            except AttributeError:
                cmdline = sys.argv[1:]
        return self.parser.parse_known_args(cmdline)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main(cmdline=None):
    """ Parse options, gather metadata, print requested data """

    # Parse command line arguments
    options, arguments = Options().parse(cmdline)
    if not arguments:
        arguments = ["."]

    # Enable debugging output
    if options.debug:
        utils.log.setLevel(utils.LOG_DEBUG)

    # Show metadata for each path given
    output = []
    for path in arguments:
        if options.verbose:
            utils.info("Checking {0} for metadata.".format(path))
        tree = fmf.Tree(path)
        for node in tree.prune(
                options.whole, options.keys, options.names, options.filters):
            show = node.show(options.brief, options.formatting, options.values)
            # List source files when in debug mode
            if options.debug:
                for source in node.sources:
                    show += utils.color("{0}\n".format(source), "blue")
            if show is not None:
                output.append(show)

    # Print output and summary
    joined = ("" if options.brief or options.formatting else "\n").join(output)
    try:
        print(joined, end="")
    except UnicodeEncodeError:
        print(joined.encode('utf-8'), end="")
    if options.verbose:
        utils.info("Found {0}.".format(utils.listed(len(output), "object")))
    return joined
