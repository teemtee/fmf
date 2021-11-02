"""
This is command line interface for the Flexible Metadata Format.

Available commands are::

    fmf ls      List identifiers of available objects
    fmf show    Show metadata of available objects
    fmf init    Initialize a new metadata tree
    fmf clean   Remove cache directory and its content

See online documentation for more details and examples:

    http://fmf.readthedocs.io/

Check also help message of individual commands for the full list
of available options.
"""

import argparse
import os
import os.path
import shlex
import sys

import fmf
import fmf.utils as utils

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Parser
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class Parser:
    """ Command line options parser """

    def __init__(self, arguments=None, path=None):
        """ Prepare the parser. """
        # Change current working directory (used for testing)
        if path is not None:
            os.chdir(path)
        # Split command line if given as a string (used for testing)
        if isinstance(arguments, str):
            self.arguments = shlex.split(arguments)
        # Otherwise use sys.argv
        if arguments is None:
            self.arguments = sys.argv
        # Enable debugging output if requested
        if "--debug" in self.arguments:
            utils.log.setLevel(utils.LOG_DEBUG)

        # Handle subcommands (mapped to format_* methods)
        self.parser = argparse.ArgumentParser(
            usage="fmf command [options]\n" + __doc__)
        self.parser.add_argument('command', help='Command to run')
        self.command = self.parser.parse_args(self.arguments[1:2]).command
        if not hasattr(self, "command_" + self.command):
            self.parser.print_help()
            raise utils.GeneralError(
                "Unrecognized command: '{0}'".format(self.command))
        # Initialize the rest and run the subcommand
        self.output = ""
        getattr(self, "command_" + self.command)()

    def options_select(self):
        """ Select by name, filter """
        group = self.parser.add_argument_group("Select")
        group.add_argument(
            "--key", dest="keys", action="append", default=[],
            help="Key content definition (required attributes)")
        group.add_argument(
            "--name", dest="names", action="append", default=[],
            help="List objects with name matching regular expression")
        group.add_argument(
            "--filter", dest="filters", action="append", default=[],
            help="Apply advanced filter (see 'pydoc fmf.filter')")
        group.add_argument(
            "--condition", dest="conditions", action="append", default=[],
            metavar="EXPR",
            help="Use arbitrary Python expression for filtering")
        group.add_argument(
            "--whole", dest="whole", action="store_true",
            help="Consider the whole tree (leaves only by default)")

    def options_formatting(self):
        """ Formating options """
        group = self.parser.add_argument_group("Format")
        group.add_argument(
            "--format", dest="formatting", default=None,
            help="Custom output format using the {} expansion")
        group.add_argument(
            "--value", dest="values", action="append", default=[],
            help="Values for the custom formatting string")

    def options_utils(self):
        """ Utilities """
        group = self.parser.add_argument_group("Utils")
        group.add_argument(
            "--path", action="append", dest="paths",
            help="Path to the metadata tree (default: current directory)")
        group.add_argument(
            "--verbose", action="store_true",
            help="Print information about parsed files to stderr")
        group.add_argument(
            "--debug", action="store_true",
            help="Turn on debugging output, do not catch exceptions")

    def command_ls(self):
        """ List names """
        self.parser = argparse.ArgumentParser(
            description="List names of available objects")
        self.options_select()
        self.options_utils()
        self.options = self.parser.parse_args(self.arguments[2:])
        self.show(brief=True)

    def command_clean(self):
        """ Clean cache """
        self.parser = argparse.ArgumentParser(
            description="Remove cache directory and its content")
        self.clean()

    def command_show(self):
        """ Show metadata """
        self.parser = argparse.ArgumentParser(
            description="Show metadata of available objects")
        self.options_select()
        self.options_formatting()
        self.options_utils()
        self.options = self.parser.parse_args(self.arguments[2:])
        self.show(brief=False)

    def command_init(self):
        """ Initialize tree """
        self.parser = argparse.ArgumentParser(
            description="Initialize a new metadata tree")
        self.options_utils()
        self.options = self.parser.parse_args(self.arguments[2:])
        # For each path create an .fmf directory and version file
        for path in self.options.paths or ["."]:
            root = fmf.Tree.init(path)
            print("Metadata tree '{0}' successfully initialized.".format(root))

    def show(self, brief=False):
        """ Show metadata for each path given """
        output = []
        for path in self.options.paths or ["."]:
            if self.options.verbose:
                utils.info("Checking {0} for metadata.".format(path))
            tree = fmf.Tree(path)
            for node in tree.prune(
                    self.options.whole, self.options.keys, self.options.names,
                    self.options.filters, self.options.conditions):
                if brief:
                    show = node.show(brief=True)
                else:
                    show = node.show(
                        brief=False,
                        formatting=self.options.formatting,
                        values=self.options.values)
                # List source files when in debug mode
                if self.options.debug:
                    for source in node.sources:
                        show += utils.color("{0}\n".format(source), "blue")
                if show is not None:
                    output.append(show)

        # Print output and summary
        if brief or self.options.formatting:
            joined = "".join(output)
        else:
            joined = "\n".join(output)
        print(joined, end="")
        if self.options.verbose:
            utils.info("Found {0}.".format(
                utils.listed(len(output), "object")))
        self.output = joined

    def clean(self):
        """ Remove cache directory """
        try:
            cache = utils.get_cache_directory(create=False)
            utils.clean_cache_directory()
            print("Cache directory '{0}' has been removed.".format(cache))
        except Exception as error:  # pragma: no cover
            utils.log.error(
                "Unable to remove cache, exception was: {0}".format(error))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main(arguments=None, path=None):
    """ Parse options, do what is requested """
    parser = Parser(arguments, path)
    return parser.output
