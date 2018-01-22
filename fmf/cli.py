# coding: utf-8

"""
Command line interface for Flexible Metadata Format

This module takes care of processing command line options
and providing requested output.
"""

import os
import re
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
            usage="fmf [path...] [options]")

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
            "--format", default="text",
            help="Output format (now: text, future: json, yaml)")

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
        # Split command line if given as string
        if isinstance(cmdline, basestring):
            cmdline = cmdline.split()

        # Otherwise properly decode command line arguments
        if cmdline is None:
            cmdline = [arg.decode("utf-8") for arg in sys.argv[1:]]
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
    output = ""

    # Enable debugging output
    if options.debug:
        utils.log.setLevel(utils.LOG_DEBUG)

    # Show metadata for each path given
    counter = 0
    for path in arguments:
        if options.verbose:
            utils.info("Checking {0} for metadata.".format(path))
        tree = fmf.Tree(path)
        for node in tree.climb(options.whole):
            # Select only nodes with key content
            if not all([key in node.data for key in options.keys]):
                continue
            # Select nodes with name matching regular expression
            if options.names and not any(
                    [re.search(name, node.name) for name in options.names]):
                continue
            # Apply advanced filters if given
            try:
                if not all([utils.filter(filter, node.data)
                        for filter in options.filters]):
                    continue
            # Handle missing attribute as if filter failed
            except utils.FilterError:
                continue
            show = node.show(brief=options.brief)
            print(show)
            output += show + "\n"
            counter += 1
    # Print summary
    if options.verbose:
        utils.info("Found {0}.".format(utils.listed(counter, "object")))
    return output
