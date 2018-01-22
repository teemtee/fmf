# coding: utf-8

""" Base Metadata Classes """

import os
import copy
import yaml

import fmf.utils as utils
from fmf.utils import log
from pprint import pformat as pretty

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SUFFIX = ".fmf"
MAIN = "main" + SUFFIX

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Metadata
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Tree(object):
    """ Metadata Tree """
    def __init__(self, data, name=None, parent=None):
        """
        Initialize data dictionary, optionally update data

        Data can be either string with directory path to be explored or
        a dictionary with the values already prepared.
        """

        # Family relations and name (identifier)
        self.parent = parent
        self.children = dict()
        self.data = dict()
        if name is None:
            self.name = os.path.basename(os.path.realpath(data))
        else:
            self.name = "/".join([self.parent.name, name])

        # Inherit data from parent
        if self.parent is not None:
            self.data = copy.deepcopy(self.parent.data)
        # Update data from dictionary or explore directory
        if isinstance(data, dict):
            self.update(data)
        else:
            self.grow(data)

    def update(self, data):
        """ Update metadata, handle virtual hiearchy """
        # Nothing to do if no data
        if data is None:
            return
        # Update data, detect special child attributes
        children = dict()
        for key, value in sorted(data.iteritems()):
            if key.startswith('/'):
                children[key.lstrip('/')] = value
            else:
                self.data[key] = value

        # Handle child attributes
        for name, data in sorted(children.iteritems()):
            try:
                self.children[name].update(data)
            except KeyError:
                self.children[name] = Tree(
                    data=data, name=name, parent=self)

    def get(self, name=None):
        """ Get desired attribute """
        if name is not None:
            return self.data
        return self.data[name]

    def child(self, name, data):
        """ Create or update child with given data """
        try:
            self.children[name].grow(data)
        except KeyError:
            self.children[name] = Tree(data, name, parent=self)

    def grow(self, path):
        """ Grow the metadata tree for the given directory path """
        if path is None:
            return
        path = path.rstrip("/")
        log.info("Walking through directory {0}".format(path))
        try:
            dirpath, dirnames, filenames = list(os.walk(path))[0]
        except IndexError:
            raise utils.FileError(
                "Unable to walk through the '{0}' directory.".format(path))
        children = dict()
        # Investigate main.fmf as the first file (for correct inheritance)
        filenames = sorted(
            [filename for filename in filenames if filename.endswith(SUFFIX)])
        try:
            filenames.insert(0, filenames.pop(filenames.index(MAIN)))
        except ValueError:
            pass
        # Check every metadata file and load data
        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            log.info("Checking file {0}".format(fullpath))
            with open(fullpath) as datafile:
                data = yaml.load(datafile)
            log.data(pretty(data))
            if filename == MAIN:
                self.update(data)
            else:
                self.child(os.path.splitext(filename)[0], data)
        # Explore every child directory
        for dirname in sorted(dirnames):
            self.child(dirname, os.path.join(path, dirname))

    def climb(self, whole=False):
        """ Climb through the tree (iterate leaf/all nodes) """
        if whole or not self.children:
            yield self
        for name, child in self.children.iteritems():
            for node in child.climb(whole):
                yield node

    def show(self, brief=False):
        """ Show metadata """
        # Show the name
        output = utils.color(self.name, 'red')
        if brief:
            return output
        # List available attributes
        try:
            for key, value in sorted(self.data.iteritems()):
                output += "\n{0}: ".format(utils.color(key, 'yellow'))
                if isinstance(value, basestring):
                    output += value
                elif isinstance(value, list) and all(
                        [isinstance(item, basestring) for item in value]):
                    output += utils.listed(value)
                else:
                    output += pretty(value)
                output
        except AttributeError:
            output = "No metadata"
        return output
