# coding: utf-8

""" Base Metadata Classes """

from __future__ import unicode_literals, absolute_import

import os
import re
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
#  YAML
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Load all strings from YAML files as unicode
# https://stackoverflow.com/questions/2890146/
from yaml import Loader, SafeLoader

def construct_yaml_str(self, node):
    return self.construct_scalar(node)
Loader.add_constructor(
    'tag:yaml.org,2002:str', construct_yaml_str)
SafeLoader.add_constructor(
    'tag:yaml.org,2002:str', construct_yaml_str)

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
        self.sources = list()
        if name is None:
            self.name = os.path.basename(os.path.realpath(data))
            self.root = os.path.dirname(os.path.realpath(data))
        else:
            self.name = "/".join([self.parent.name, name])
            self.root = self.parent.root
        log.debug("New tree '{0}' created.".format(self))

        # Update data from dictionary or explore directory
        if isinstance(data, dict):
            self.update(data)
        else:
            self.grow(data)

    def __unicode__(self):
        """ Use tree name as identifier """
        return self.name

    def find_root_tree_elem(self, obj=None):
        """
        Traverse and return root tree element

        :param obj: base object
        :return: Tree element (root)
        """
        if not obj:
            obj = self
        if not obj.parent:
            return obj
        else:
            self.find_root_tree_elem(obj=obj.parent)

    def __remove_append_items(self, whole=False):
        """
        internal method, delete all append items (ends with +)

        :param whole: pass thru 'whole' param to climb
        :return: None
        """
        root_tree = self.find_root_tree_elem()
        for node in root_tree.climb(whole=whole):
            for key in sorted(node.data.keys()):
                if key.endswith('+'):
                    del node.data[key]

    @classmethod
    def merge_items(cls, reference_node, node):
        data = copy.deepcopy(reference_node.data)
        node.sources = reference_node.sources + node.sources
        for key, value in sorted(node.data.items()):
            if key + "+" in node.data:
                continue
            # Handle attribute adding
            if key.endswith('+'):
                origin_key = key
                key = key.rstrip('+')
                data[origin_key] = value
                if key in data:
                    try:
                        value = data[key] + value
                    except TypeError as error:
                        raise utils.MergeError(
                            "MergeError: Key '{0}' in {1} ({2}).".format(
                                key, node.name, str(error)))
            # And finally update the value
            data[key] = value
        node.data = data

    def reference_resolver(self, whole=False):
        """
        resolve references in names like /a/b/c/d@.x.y or /a/b/c/@y
        it uses simple references schema, do not use references to another references
        avoid usind / in reference because actual solution creates also this tree items
        it is bug or feature, who knows :-)

        :param whole: pass thru 'whole' param to climb
        :return: None
        """
        root_tree = self.find_root_tree_elem()
        reference_nodes = root_tree.prune(whole=whole, names=["@"])
        for node in reference_nodes:
            ref_item_name = "[^@]%s" % node.name.rsplit("@", 1)[1]
            reference_node = root_tree.find(ref_item_name, regexp=True)
            if not reference_node:
                raise ValueError("Unable to find reference for node: %s  via name search: %s" %
                                 (node.name, ref_item_name))
            log.debug("Reference solver for : %s  via item name: %s" % (node.name, reference_node.name))
            self.merge_items(reference_node=reference_node, node=node)
        self.__remove_append_items()

    def inherit(self):
        """ Apply inheritance and attribute merging """
        if self.parent is not None:
            self.merge_items(reference_node=self.parent, node=self)
        log.debug("Data for '{0}' inherited.".format(self))
        log.data(pretty(self.data))
        # Apply inheritance to all children
        for child in self.children.values():
            child.inherit()

    def update(self, data):
        """ Update metadata, handle virtual hierarchy """
        # Nothing to do if no data
        if data is None:
            return
        for key, value in sorted(data.items()):
            # Handle child attributes
            if key.startswith('/'):
                name = key.lstrip('/')
                # Handle deeper nesting (e.g. keys like /one/two/three) by
                # extracting only the first level of the hierarchy as name
                match = re.search("([^/]+)(/.*)", name)
                if match:
                    name = match.groups()[0]
                    value = {match.groups()[1]: value}
                # Update existing child or create a new one
                self.child(name, value)
            # Update regular attributes
            else:
                self.data[key] = value
        log.debug("Data for '{0}' updated.".format(self))
        log.data(pretty(self.data))

    def get(self, name=None):
        """ Get desired attribute """
        if name is None:
            return self.data
        return self.data[name]

    def child(self, name, data, source=None):
        """ Create or update child with given data """
        try:
            if isinstance(data, dict):
                self.children[name].update(data)
            else:
                self.children[name].grow(data)
        except KeyError:
            self.children[name] = Tree(data, name, parent=self)
        # Save source file
        if source is not None:
            self.children[name].sources.append(source)

    def grow(self, path):
        """
        Grow the metadata tree for the given directory path

        Note: For each path, grow() should be run only once. Growing the tree
        from the same path multiple times with attribute adding using the "+"
        sign leads to adding the value more than once!
        """
        if path is None:
            return
        path = path.rstrip("/")
        log.info("Walking through directory {0}".format(
            os.path.realpath(path)))
        try:
            dirpath, dirnames, filenames = list(os.walk(path))[0]
        except IndexError:
            raise utils.FileError(
                "Unable to walk through the '{0}' directory.".format(path))
        # Investigate main.fmf as the first file (for correct inheritance)
        filenames = sorted(
            [filename for filename in filenames if filename.endswith(SUFFIX)])
        try:
            filenames.insert(0, filenames.pop(filenames.index(MAIN)))
        except ValueError:
            pass
        # Check every metadata file and load data (ignore hidden)
        for filename in filenames:
            if filename.startswith("."):
                continue
            fullpath = os.path.realpath(os.path.join(dirpath, filename))
            log.info("Checking file {0}".format(fullpath))
            with open(fullpath) as datafile:
                data = yaml.load(datafile)
            log.data(pretty(data))
            # Handle main.fmf as data for self
            if filename == MAIN:
                self.sources.append(fullpath)
                self.update(data)
            # Handle other *.fmf files as children
            else:
                self.child(os.path.splitext(filename)[0], data, fullpath)
        # Explore every child directory (ignore hidden)
        for dirname in sorted(dirnames):
            if dirname.startswith("."):
                continue
            self.child(dirname, os.path.join(path, dirname))
        # Apply inheritance when all scattered data are gathered.
        # This is done only once, from the top parent object.
        if self.parent is None:
            self.inherit()

    def climb(self, whole=False):
        """ Climb through the tree (iterate leaf/all nodes) """
        if whole or not self.children:
            yield self
        for name, child in self.children.items():
            for node in child.climb(whole):
                yield node

    def find(self, name, regexp=False):
        """ Find node with given name """
        for node in self.climb():
            if not regexp:
                if node.name == name:
                    return node
            else:
                if re.search(name,node.name):
                    return node
        return None

    def prune(self, whole=False, keys=[], names=[], filters=[]):
        """ Filter tree nodes based on given criteria """
        for node in self.climb(whole):
            # Select only nodes with key content
            if not all([key in node.data for key in keys]):
                continue
            # Select nodes with name matching regular expression
            if names and not any(
                    [re.search(name, node.name) for name in names]):
                continue
            # Apply advanced filters if given
            try:
                if not all([utils.filter(filter, node.data)
                        for filter in filters]):
                    continue
            # Handle missing attribute as if filter failed
            except utils.FilterError:
                continue
            # All criteria met, thus yield the node
            yield node

    def show(self, brief=False, formatting=None, values=[]):
        """ Show metadata """
        # Show nothing if there's nothing
        if not self.data:
            return None

        # Custom formatting
        if formatting is not None:
            formatting = re.sub("\\\\n", "\n", formatting)
            name = self.name
            data = self.data
            root = self.root
            sources = self.sources
            evaluated = []
            for value in values:
                evaluated.append(eval(value))
            return formatting.format(*evaluated)

        # Show the name
        output = utils.color(self.name, 'red')
        if brief:
            return output + "\n"
        # List available attributes
        for key, value in sorted(self.data.items()):
            output += "\n{0}: ".format(utils.color(key, 'green'))
            if isinstance(value, type("")):
                output += value
            elif isinstance(value, list) and all(
                    [isinstance(item, type("")) for item in value]):
                output += utils.listed(value)
            else:
                output += pretty(value)
            output
        return output + "\n"
