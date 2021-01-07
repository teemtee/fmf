# coding: utf-8

""" Base Metadata Classes """

from __future__ import unicode_literals, absolute_import

import os
import re
import copy
import yaml

import fmf.context
import fmf.utils as utils
from io import open
from fmf.utils import log
from pprint import pformat as pretty

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SUFFIX = ".fmf"
MAIN = "main" + SUFFIX
IGNORED_DIRECTORIES = ['/dev', '/proc', '/sys']

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  YAML
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Handle both older and newer yaml loader
# https://msg.pyyaml.org/load
try:
    from yaml import FullLoader as YamlLoader
except ImportError: # pragma: no cover
    from yaml import SafeLoader as YamlLoader

# Load all strings from YAML files as unicode
# https://stackoverflow.com/questions/2890146/
def construct_yaml_str(self, node):
    return self.construct_scalar(node)
YamlLoader.add_constructor(
    'tag:yaml.org,2002:str', construct_yaml_str)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Metadata
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Tree(object):
    """ Metadata Tree """
    def __init__(self, data, name=None, parent=None):
        """
        Initialize metadata tree from directory path or data dictionary

        Data parameter can be either a string with directory path to be
        explored or a dictionary with the values already prepared.
        """

        # Bail out if no data and no parent given
        if not data and not parent:
            raise utils.GeneralError(
                "No data or parent provided to initialize the tree.")

        # Initialize family relations, object data and source files
        self.parent = parent
        self.children = dict()
        self.data = dict()
        self.sources = list()
        self.root = None
        self.version = utils.VERSION
        self.original_data = dict()

        # Special handling for top parent
        if self.parent is None:
            self.name = "/"
            if not isinstance(data, dict):
                self._initialize(path=data)
                data = self.root
        # Handle child node creation
        else:
            self.root = self.parent.root
            self.name = os.path.join(self.parent.name, name)
        # Initialize data
        if isinstance(data, dict):
            self.update(data)
        else:
            self.grow(data)

        # Apply inheritance when all scattered data are gathered.
        # This is done only once, from the top parent object.
        if self.parent is None:
            self.inherit()

        log.debug("New tree '{0}' created.".format(self))

    def __unicode__(self):
        """ Use tree name as identifier """
        return self.name # pragma: no cover

    def _initialize(self, path):
        """ Find metadata tree root, detect format version """
        # Find the tree root
        root = os.path.abspath(path)
        try:
            while ".fmf" not in next(os.walk(root))[1]:
                if root == "/":
                    raise utils.RootError(
                        "Unable to find tree root for '{0}'.".format(
                            os.path.abspath(path)))
                root = os.path.abspath(os.path.join(root, os.pardir))
        except StopIteration:
            raise utils.FileError("Invalid directory path: {0}".format(root))
        log.info("Root directory found: {0}".format(root))
        self.root = root
        # Detect format version
        try:
            with open(os.path.join(self.root, ".fmf", "version")) as version:
                self.version = int(version.read())
                log.info("Format version detected: {0}".format(self.version))
        except IOError as error:
            raise utils.FormatError(
                "Unable to detect format version: {0}".format(error))
        except ValueError:
            raise utils.FormatError("Invalid version format")

    def _merge_plus(self, data, key, value):
        """ Handle extending attributes using the '+' suffix """
        # Nothing to do if key not in parent
        if key not in data:
            data[key] = value
            return
        # Use dict.update() for merging dictionaries
        if type(data[key]) == type(value) == dict:
            self._merge_special(data[key], value)
            return
        # Attempt to apply the plus operator
        try:
            data[key] = data[key] + value
        except TypeError as error:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} ({2}).".format(
                    key, self.name, str(error)))

    def _merge_minus(self, data, key, value):
        """ Handle reducing attributes using the '-' suffix """
        # Cannot reduce attribute if key is not present in parent
        if key not in data:
            data[key] = value
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} (not inherited).".format(
                    key, self.name))
        # Subtract numbers
        if type(data[key]) == type(value) in [int, float]:
            data[key] = data[key] - value
        # Replace matching regular expression with empty string
        elif type(data[key]) == type(value) == type(""):
            data[key] = re.sub(value, '', data[key])
        # Remove given values from the parent list
        elif type(data[key]) == type(value) == list:
            data[key] = [item for item in data[key] if item not in value]
        # Remove given key from the parent dictionary
        elif type(data[key]) == dict and type(value) == list:
            for item in value:
                data[key].pop(item, None)
        else:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} (wrong type).".format(
                    key, self.name))

    def _merge_special(self, data, source):
        """ Merge source dict into data, handle special suffixes """
        for key, value in sorted(source.items()):
            # Handle special attribute merging
            if key.endswith('+'):
                self._merge_plus(data, key.rstrip('+'), value)
            elif key.endswith('-'):
                self._merge_minus(data, key.rstrip('-'), value)
            # Otherwise just update the value
            else:
                data[key] = value

    @staticmethod
    def init(path):
        """ Create metadata tree root under given path """
        root = os.path.abspath(os.path.join(path, ".fmf"))
        if os.path.exists(root):
            raise utils.FileError("{0} '{1}' already exists.".format(
                "Directory" if os.path.isdir(root) else "File", root))
        try:
            os.makedirs(root)
            with open(os.path.join(root, "version"), "w") as version:
                version.write("{0}\n".format(utils.VERSION))
        except OSError as error:
            raise utils.FileError("Failed to create '{}': {}.".format(
                root, error))
        return root

    def merge(self, parent=None):
        """ Merge parent data """
        # Check parent, append source files
        if parent is None:
            parent = self.parent
        if parent is None:
            return
        self.sources = parent.sources + self.sources
        # Merge child data with parent data
        data = copy.deepcopy(parent.data)
        self._merge_special(data, self.data)
        self.data = data

    def inherit(self):
        """ Apply inheritance """
        # Preserve original data and merge parent
        # (original data needed for custom inheritance extensions)
        self.original_data = self.data
        self.merge()
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
            # Ensure there are no 'None' keys
            if key is None:
                raise utils.FormatError("Invalid key 'None'.")
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

    def adjust(self, context, key='adjust', undecided='skip'):
        """
        Adjust tree data based on provided context and rules

        The 'context' should be an instance of the fmf.context.Context
        class describing the environment context. By default, the key
        'adjust' of each node is inspected for possible rules that
        should be applied. Provide 'key' to use a custom key instead.

        Optional 'undecided' parameter can be used to specify what
        should happen when a rule condition cannot be decided because
        context dimension is not defined. By default, such rules are
        skipped. In order to raise the fmf.context.CannotDecide
        exception in such cases use undecided='raise'.
        """

        # Check context sanity
        if not isinstance(context, fmf.context.Context):
            raise utils.GeneralError(
                "Invalid adjust context: '{}'.".format(type(context).__name__))

        # Adjust rules should be a dictionary or a list of dictionaries
        try:
            rules = self.data.pop(key)
            log.debug("Applying adjust rules for '{}'.".format(self))
            log.data(rules)
            if isinstance(rules, dict):
                rules = [rules]
            if not isinstance(rules, list):
                raise utils.FormatError(
                    "Invalid adjust rule format in '{}'. "
                    "Should be a dictionary or a list of dictionaries, "
                    "got '{}'.".format(self.name, type(rules).__name__))
        except KeyError:
            rules = []

        # Check and apply each rule
        for rule in rules:

            # Rule must be a dictionary
            if not isinstance(rule, dict):
                raise utils.FormatError("Adjust rule should be a dictionary.")

            # There must be a condition defined
            try:
                condition = rule.pop('when')
            except KeyError:
                raise utils.FormatError("No condition defined in adjust rule.")

            # The optional 'continue' key should be a bool
            continue_ = rule.pop('continue', True)
            if not isinstance(continue_, bool):
                raise utils.FormatError(
                    "The 'continue' value should be bool, "
                    "got '{}'.".format(continue_))

            # The 'because' key is reserved for optional comments (ignored)
            rule.pop('because', None)

            # Apply remaining rule attributes if context matches
            try:
                if context.matches(condition):
                    self._merge_special(self.data, rule)

                    # First matching rule wins, skip the rest unless continue
                    if not continue_:
                        break
            # Handle undecided rules as requested
            except fmf.context.CannotDecide:
                if undecided == 'skip':
                    continue
                elif undecided == 'raise':
                    raise
                else:
                    raise utils.GeneralError(
                        "Invalid value for the 'undecided' parameter. Should "
                        "be 'skip' or 'raise', got '{}'.".format(undecided))

        # Adjust all child nodes as well
        for child in self.children.values():
            child.adjust(context, key, undecided)


    def get(self, name=None, default=None):
        """
        Get attribute value or return default

        Whole data dictionary is returned when no attribute provided.
        Supports direct values retrieval from deep dictionaries as well.
        Dictionary path should be provided as list. The following two
        examples are equal:

        tree.data['hardware']['memory']['size']
        tree.get(['hardware', 'memory', 'size'])

        However the latter approach will also correctly handle providing
        default value when any of the dictionary keys does not exist.

        """
        # Return the whole dictionary if no attribute specified
        if name is None:
            return self.data
        if not isinstance(name, list):
            name = [name]
        data = self.data
        try:
            for key in name:
                data = data[key]
        except KeyError:
            return default
        return data

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
        if path != '/':
            path = path.rstrip("/")
        if path in IGNORED_DIRECTORIES: # pragma: no cover
            log.debug("Ignoring '{0}' (special directory).".format(path))
            return
        log.info("Walking through directory {0}".format(
            os.path.abspath(path)))
        try:
            dirpath, dirnames, filenames = next(os.walk(path))
        except StopIteration:
            log.debug("Skipping '{0}' (not accessible).".format(path))
            return
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
            fullpath = os.path.abspath(os.path.join(dirpath, filename))
            log.info("Checking file {0}".format(fullpath))
            try:
                with open(fullpath, encoding='utf-8') as datafile:
                    data = yaml.load(datafile, Loader=YamlLoader)
            except yaml.error.YAMLError as error:
                    raise(utils.FileError("Failed to parse '{0}'\n{1}".format(
                            fullpath, error)))
            log.data(pretty(data))
            # Handle main.fmf as data for self
            if filename == MAIN:
                self.sources.append(fullpath)
                self.update(data)
            # Handle other *.fmf files as children
            else:
                self.child(os.path.splitext(filename)[0], data, fullpath)
        # Explore every child directory (ignore hidden dirs and subtrees)
        for dirname in sorted(dirnames):
            if dirname.startswith("."):
                continue
            # Ignore metadata subtrees
            if os.path.isdir(os.path.join(path, dirname, SUFFIX)):
                log.debug("Ignoring metadata tree '{0}'.".format(dirname))
                continue
            self.child(dirname, os.path.join(path, dirname))
        # Remove empty children (ignore directories without metadata)
        for name in list(self.children.keys()):
            child = self.children[name]
            if not child.data and not child.children:
                del(self.children[name])
                log.debug("Empty tree '{0}' removed.".format(child.name))

    def climb(self, whole=False):
        """ Climb through the tree (iterate leaf/all nodes) """
        if whole or not self.children:
            yield self
        for name, child in self.children.items():
            for node in child.climb(whole):
                yield node

    def find(self, name):
        """ Find node with given name """
        for node in self.climb(whole=True):
            if node.name == name:
                return node
        return None

    def prune(self, whole=False, keys=[], names=[], filters=[], conditions=[]):
        """ Filter tree nodes based on given criteria """
        for node in self.climb(whole):
            # Select only nodes with key content
            if not all([key in node.data for key in keys]):
                continue
            # Select nodes with name matching regular expression
            if names and not any(
                    [re.search(name, node.name) for name in names]):
                continue
            # Apply filters and conditions if given
            try:
                if not all([utils.filter(filter, node.data, regexp=True)
                        for filter in filters]):
                    continue
                if not all([utils.evaluate(condition, node.data, node)
                        for condition in conditions]):
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
                output += value.rstrip("\n")
            elif isinstance(value, list) and all(
                    [isinstance(item, type("")) for item in value]):
                output += utils.listed(value)
            else:
                output += pretty(value)
            output
        return output + "\n"

    @staticmethod
    def node(reference):
        """
        Return Tree node referenced by the fmf identifier

        Keys supported in the reference:

        url .... git repository url (optional)
        ref .... branch, tag or commit ('master' by default)
        path ... metadata tree root ('.' by default)
        name ... tree node name ('/' by default)

        See the documentation for the full fmf id specification:
        https://fmf.readthedocs.io/en/latest/concept.html#identifiers
        Raises ReferenceError if referenced node does not exist.
        """

        # Fetch remote git repository
        if 'url' in reference:
            path = reference.get('path', '.').lstrip('/')
            repository = utils.fetch(
                reference.get('url'), reference.get('ref', 'master'))
            root = os.path.join(repository, path)
        # Use local files
        else:
            root = reference.get('path', '.')
            if not root.startswith('/') and root != '.':
                raise utils.ReferenceError(
                    'Relative path "%s" specified.' % root)
        found_node = Tree(root).find(reference.get('name', '/'))
        if found_node is None:
            raise utils.ReferenceError(
                "No tree node found for '{0}' reference".format(reference))
        # FIXME Should be able to remove .cache if required
        return found_node
