""" Base Metadata Classes """

from __future__ import annotations

import copy
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Mapping
from io import open
from pprint import pformat as pretty
# TODO: py3.10: typing.Optional, typing.Union -> '|' operator
from typing import Any, Optional, Union

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

import jsonschema
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError

import fmf.context
import fmf.utils as utils
from fmf.utils import dict_to_yaml, log

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SUFFIX = ".fmf"
MAIN = "main" + SUFFIX
IGNORED_DIRECTORIES = ['/dev', '/proc', '/sys']

# TypeHints
RawDataType: TypeAlias = Union[None, int, float, str, bool]
ListDataType: TypeAlias = list[Union[RawDataType, 'ListDataType', 'DictDataType']]
DictDataType: TypeAlias = dict[str, Union[RawDataType, ListDataType, 'DictDataType']]
# Equivalent to:
# JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
DataType: TypeAlias = Union[RawDataType, ListDataType, DictDataType]
TreeData: TypeAlias = dict[str, DataType]
TreeDataPath: TypeAlias = Union[TreeData, str]  # Either TreeData or path
JsonSchema: TypeAlias = Mapping[str, Any]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Metadata
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Cannot specify class Tree(Mapping[str, Tree | DataType]]):
# This has a different .get method interface incompatible with mypy
class Tree:
    """ Metadata Tree """
    parent: Optional[Tree]
    children: dict[str, Tree]
    data: TreeData
    sources: list[str]
    root: Optional[str]
    version: int
    original_data: TreeData
    name: str
    _commit: Optional[Union[str, bool]]
    _raw_data: TreeData
    _updated: bool
    _directives: TreeData
    _symlinkdirs: list[str]

    def __init__(self, data: Optional[TreeDataPath],
                 name: Optional[str] = None,
                 parent: Optional[Tree] = None):
        """
        Initialize metadata tree from directory path or data dictionary

        Data parameter can be either a string with directory path to be
        explored or a dictionary with the values already prepared.
        """

        # Bail out if no data and no parent given
        if not data and parent is None:
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
        self._commit = None
        self._raw_data = dict()
        # Track whether the data dictionary has been updated
        # (needed to prevent removing nodes with an empty dict).
        self._updated = False

        # Special directives
        self._directives = dict()

        # Store symlinks in while walking tree in grow() to detect
        # symlink loops
        if parent is None:
            self._symlinkdirs = []
        else:
            self._symlinkdirs = parent._symlinkdirs

        # Special handling for top parent
        if self.parent is None:
            self.name = "/"
            if not isinstance(data, dict):
                assert data is not None
                self._initialize(path=data)
                data = self.root
        # Handle child node creation
        else:
            self.root = self.parent.root
            assert name is not None
            self.name = os.path.join(self.parent.name, name)

        # Update data from a dictionary (handle empty nodes)
        if isinstance(data, dict) or data is None:
            self.update(data)
        # Grow the tree from a directory path
        else:
            self.grow(data)

        # Apply inheritance when all scattered data are gathered.
        # This is done only once, from the top parent object.
        if self.parent is None:
            self.inherit()

        log.debug(f"New tree '{self}' created.")

    @property
    def commit(self) -> Union[str, bool]:
        """
        Commit hash if tree grows under a git repo, False otherwise

        Return current commit hash if the metadata tree root is located
        under a git repository. For metadata initialized from a dict or
        local directory with no git repo 'False' is returned instead.
        """
        if self._commit is not None:
            return self._commit

        # No root, no commit (tree parsed from a dictionary)
        if self.root is None:
            self._commit = False
            return self._commit

        # Check root directory for current commit
        try:
            output, _ = utils.run(
                ['git', 'rev-parse', '--verify', 'HEAD'], cwd=self.root)
            self._commit = output.strip()
            return self._commit
        except subprocess.CalledProcessError:
            self._commit = False
            return self._commit

    def __str__(self):
        """ Use tree name as identifier """
        return self.name

    def _initialize(self, path: str) -> None:
        """ Find metadata tree root, detect format version """
        # Find the tree root
        root = os.path.abspath(path)
        try:
            while ".fmf" not in next(os.walk(root))[1]:
                if root == "/":
                    raise utils.RootError(
                        f"Unable to find tree root for '{os.path.abspath(path)}'.")
                root = os.path.abspath(os.path.join(root, os.pardir))
        except StopIteration:
            raise utils.FileError(f"Invalid directory path: {root}")
        log.info(f"Root directory found: {root}")
        self.root = root
        # Detect format version
        try:
            with open(os.path.join(self.root, ".fmf", "version")) as version:
                self.version = int(version.read())
                log.info(f"Format version detected: {self.version}")
        except IOError as error:
            raise utils.FormatError("Unable to detect format version") from error
        except ValueError:
            raise utils.FormatError("Invalid version format")

    def _merge_plus(self, data: TreeData, key: str,
                    value: DataType, prepend: bool = False) -> None:
        """ Handle extending attributes using the '+' suffix """
        try:
            # Nothing to do if key not in parent
            if key not in data:
                data[key] = value
                return
            # Use the special merge for merging dictionaries
            data_val = data[key]
            if isinstance(data_val, dict) and isinstance(value, (dict, Mapping)):
                self._merge_special(data_val, value)
                data[key] = data_val
                return
            # Attempt to apply the plus operator
            if prepend:
                data_val = value + data_val  # type: ignore
            else:
                data_val = data_val + value  # type: ignore
            data[key] = data_val
        except TypeError as error:
            raise utils.MergeError(f"MergeError: Key '{key}' in {self.name}.") from error

    def _merge_minus(self, data: TreeData, key: str, value: DataType) -> None:
        """ Handle reducing attributes using the '-' suffix """
        try:
            # Cannot reduce attribute if key is not present in parent
            if key not in data:
                data[key] = value
                raise utils.MergeError(
                    f"MergeError: Key '{key}' in {self.name} (not inherited).")
            # Subtract numbers
            data_val = data[key]
            if type(data_val) == type(value) in [int, float]:
                data_val -= value  # type: ignore
            # Replace matching regular expression with empty string
            elif isinstance(data_val, str) and isinstance(value, str):
                data_val = re.sub(value, '', data_val)
            # Remove given values from the parent list
            elif isinstance(data_val, list) and isinstance(value, list):
                data_val = [item for item in data_val if item not in value]
            # Remove given key from the parent dictionary
            elif isinstance(data_val, dict) and isinstance(value, list):
                for item in value:
                    assert isinstance(item, str)
                    data_val.pop(item, None)
            else:
                raise TypeError(f"Incompatible types: {type(data_val)} - {type(value)}")
            data[key] = data_val
        except TypeError as error:
            raise utils.MergeError(
                f"MergeError: Key '{key}' in {self.name} (wrong type).") from error

    def _merge_special(self, data: TreeData, source: TreeData) -> None:
        """ Merge source dict into data, handle special suffixes """
        for key, value in sorted(source.items()):
            # Handle special attribute merging
            if key.endswith('+'):
                self._merge_plus(data, key.rstrip('+'), value)
            elif key.endswith('+<'):
                self._merge_plus(data, key.rstrip('+<'), value, prepend=True)
            elif key.endswith('-'):
                self._merge_minus(data, key.rstrip('-'), value)
            # Otherwise just update the value
            else:
                data[key] = value

    def _process_directives(self, directives: TreeData) -> None:
        """ Check and process special fmf directives """

        def check(value: DataType, type_: type, name: Optional[str] = None) -> None:
            """ Check for correct type """
            if not isinstance(value, type_):
                name = f" '{name}'" if name else ""
                raise fmf.utils.FormatError(
                    f"Invalid fmf directive{name} in '{self.name}': "
                    f"Should be a '{type_.__name__}', "
                    f"got a '{type(value).__name__}' instead.")

        # Directives should be a directory
        check(directives, dict)

        # Check for proper values
        for key, value in directives.items():
            if key == "inherit":
                check(value, bool, name="inherit")
                continue
            # No other directive supported
            raise fmf.utils.FormatError(
                f"Unknown fmf directive '{key}' in '{self.name}'.")

        # Everything ok, store the directives
        self._directives.update(directives)

    @staticmethod
    def init(path: str) -> str:
        """ Create metadata tree root under given path """
        root = os.path.abspath(os.path.join(path, ".fmf"))
        if os.path.exists(root):
            raise utils.FileError(
                f"{'Directory' if os.path.isdir(root) else 'File'} '{root}' already exists.")
        try:
            os.makedirs(root)
            with open(os.path.join(root, "version"), "w") as version:
                version.write(f"{utils.VERSION}\n")
        except OSError as error:
            raise utils.FileError(f"Failed to create '{root}'.") from error
        return root

    def merge(self, parent: Optional[Tree] = None) -> None:
        """ Merge parent data """
        # Check parent, append source files
        if parent is None:
            parent = self.parent
        if parent is None:
            return
        # Do not inherit when disabled
        if self._directives.get("inherit") is False:
            return
        self.sources = parent.sources + self.sources
        # Merge child data with parent data
        data = copy.deepcopy(parent.data)
        self._merge_special(data, self.data)
        self.data = data

    def inherit(self) -> None:
        """ Apply inheritance """
        # Preserve original data and merge parent
        # (original data needed for custom inheritance extensions)
        self.original_data = self.data
        self.merge()
        log.debug(f"Data for '{self}' inherited.")
        log.data(pretty(self.data))
        # Apply inheritance to all children
        for child in self.children.values():
            child.inherit()

    def update(self, data: Optional[TreeData]) -> None:
        """ Update metadata, handle virtual hierarchy """
        # Make a note that the data dictionary has been updated
        # None is handled in the same way as an empty dictionary
        self._updated = True
        # Nothing to do if no data
        if data is None:
            return

        # Handle fmf directives first
        try:
            directives = data.pop("/")
            self._process_directives(directives)  # type: ignore
        except KeyError:
            pass

        # Process the metadata
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
                assert isinstance(value, dict) or isinstance(value, str) or value is None
                self.child(name, value)
            # Update regular attributes
            else:
                self.data[key] = value
        log.debug(f"Data for '{self}' updated.")
        log.data(pretty(self.data))

    def adjust(self,
               context: fmf.context.Context,
               key: str = 'adjust',
               undecided: str = 'skip') -> None:
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
                f"Invalid adjust context: '{type(context).__name__}'.")

        # Adjust rules should be a dictionary or a list of dictionaries
        try:
            rules = copy.deepcopy(self.data[key])
            log.debug(f"Applying adjust rules for '{self}'.")
            log.data(str(rules))
            if isinstance(rules, dict):
                rules = [rules]
            if not isinstance(rules, list):
                raise utils.FormatError(
                    f"Invalid adjust rule format in '{self.name}'. "
                    f"Should be a dictionary or a list of dictionaries, "
                    f"got '{type(rules).__name__}'.")
        except KeyError:
            rules = []

        # Check and apply each rule
        for rule in rules:

            # Rule must be a dictionary
            if not isinstance(rule, dict):
                raise utils.FormatError("Adjust rule should be a dictionary.")

            # Missing 'when' means always enabled rule
            try:
                condition = rule.pop('when')
            except KeyError:
                condition = True

            assert isinstance(condition, str) or isinstance(condition, bool)
            # The optional 'continue' key should be a bool
            continue_ = rule.pop('continue', True)
            if not isinstance(continue_, bool):
                raise utils.FormatError(
                    f"The 'continue' value should be bool, got '{continue_}'.")

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
                        f"Invalid value for the 'undecided' parameter. Should "
                        f"be 'skip' or 'raise', got '{undecided}'.")

        # Adjust all child nodes as well
        for child in self.children.values():
            child.adjust(context, key, undecided)

    def get(self, name: Optional[Union[list[str], str]] = None,
            default: DataType = None) -> DataType:
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
                data = data[key]  # type: ignore
        except KeyError:
            return default
        return data

    def child(self, name: str, data: Optional[TreeDataPath],
              source: Optional[str] = None) -> None:
        """ Create or update child with given data """
        try:
            # Update data from a dictionary (handle empty nodes)
            if isinstance(data, dict) or data is None:
                self.children[name].update(data)
            # Grow the tree from a directory path
            else:
                self.children[name].grow(data)
        except KeyError:
            self.children[name] = Tree(data, name, parent=self)
        # Save source file
        if source is not None:
            self.children[name].sources.append(source)
            if data is None:
                self.children[name]._raw_data = {}
            else:
                assert isinstance(data, dict)
                self.children[name]._raw_data = copy.deepcopy(data)

    def grow(self, path: str) -> None:
        """
        Grow the metadata tree for the given directory path

        Note: For each path, grow() should be run only once. Growing the tree
        from the same path multiple times with attribute adding using the "+"
        sign leads to adding the value more than once!
        """
        if path != '/':
            path = path.rstrip("/")
        if path in IGNORED_DIRECTORIES:  # pragma: no cover
            log.debug(f"Ignoring '{path}' (special directory).")
            return
        log.info(f"Walking through directory {os.path.abspath(path)}")
        try:
            dirpath, dirnames, filenames = next(os.walk(path))
        except StopIteration:
            log.debug(f"Skipping '{path}' (not accessible).")
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
            log.info(f"Checking file {fullpath}")
            try:
                with open(fullpath, encoding='utf-8') as datafile:
                    # Workadound ruamel s390x read issue - fmf/issues/164
                    content = datafile.read()
                    data = YAML(typ="safe").load(content)
            except (YAMLError, DuplicateKeyError) as error:
                raise utils.FileError(f"Failed to parse '{fullpath}'.") from error
            log.data(pretty(data))
            # Handle main.fmf as data for self
            if filename == MAIN:
                self.sources.append(fullpath)
                self._raw_data = copy.deepcopy(data)
                self.update(data)
            # Handle other *.fmf files as children
            else:
                self.child(os.path.splitext(filename)[0], data, fullpath)
        # Explore every child directory (ignore hidden dirs and subtrees)
        for dirname in sorted(dirnames):
            if dirname.startswith("."):
                continue
            fulldir = os.path.join(dirpath, dirname)
            if os.path.islink(fulldir):
                # According to the documentation, calling os.path.realpath
                # with strict = True will raise OSError if a symlink loop
                # is encountered. But it does not do that with a loop with
                # more than one node
                fullpath = os.path.realpath(fulldir)
                if fullpath in self._symlinkdirs:
                    log.debug(f"Not entering symlink loop {fulldir}")
                    continue
                else:
                    self._symlinkdirs.append(fullpath)

            # Ignore metadata subtrees
            if os.path.isdir(os.path.join(path, dirname, SUFFIX)):
                log.debug(f"Ignoring metadata tree '{dirname}'.")
                continue
            self.child(dirname, os.path.join(path, dirname))
        # Ignore directories with no metadata (remove all child nodes which
        # do not have children and their data haven't been updated)
        for name in list(self.children.keys()):
            child = self.children[name]
            if not child.children and not child._updated:
                del self.children[name]
                log.debug(f"Empty tree '{child.name}' removed.")

    def climb(self, whole: bool = False) -> Iterator[Tree]:
        """ Climb through the tree (iterate leaf/all nodes) """
        if whole or not self.children:
            yield self
        for name, child in self.children.items():
            for node in child.climb(whole):
                yield node

    def find(self, name: str) -> Optional[Tree]:
        """ Find node with given name """
        for node in self.climb(whole=True):
            if node.name == name:
                return node
        return None

    def prune(self, whole: bool = False,
              keys: Optional[list[str]] = None,
              names: Optional[list[str]] = None,
              filters: Optional[list[str]] = None,
              conditions: Optional[list[str]] = None,
              sources: Optional[list[str]] = None) -> Iterator[Tree]:
        """ Filter tree nodes based on given criteria """
        keys = keys or []
        names = names or []
        filters = filters or []
        conditions = conditions or []

        # Expand paths to absolute
        sources_set = set()
        if sources:
            sources_set = {os.path.abspath(src) for src in sources}

        for node in self.climb(whole):
            # Select only nodes with key content
            if not all([key in node.data for key in keys]):
                continue
            # Select nodes with name matching regular expression
            if names and not any(
                    [re.search(name, node.name) for name in names]):
                continue
            # Select nodes defined by any of the source files
            if sources_set and not sources_set.intersection(node.sources):
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

    def show(
            self,
            brief: bool = False,
            formatting: Optional[str] = None,
            values: Optional[list[str]] = None) -> str:
        """ Show metadata """
        values = values or []

        # Custom formatting
        if formatting is not None:
            formatting = re.sub("\\\\n", "\n", formatting)
            name = self.name  # noqa: F841
            data = self.data  # noqa: F841
            root = self.root  # noqa: F841
            sources = self.sources  # noqa: F841
            evaluated = []
            for str_v in values:
                evaluated.append(eval(str_v))
            return formatting.format(*evaluated)

        # Show the name
        output = utils.color(self.name, 'red')
        if brief or not self.data:
            return f"{output}\n"
        # List available attributes
        for key, val in sorted(self.data.items()):
            output = f"{output}\n{utils.color(key, 'green')}: "
            if isinstance(val, str):
                output += val.rstrip("\n")
            elif isinstance(val, list) and all(isinstance(item, str) for item in val):
                output += utils.listed(val)  # type: ignore
            else:
                output += pretty(val)
        return f"{output}\n"

    @staticmethod
    def node(reference: TreeData) -> Tree:
        """
        Return Tree node referenced by the fmf identifier

        Keys supported in the reference:

        url .... git repository url (optional)
        ref .... branch, tag or commit (default branch if not provided)
        path ... metadata tree root ('.' by default)
        name ... tree node name ('/' by default)

        See the documentation for the full fmf id specification:
        https://fmf.readthedocs.io/en/latest/concept.html#identifiers
        Raises ReferenceError if referenced node does not exist.
        """

        # Fetch remote git repository
        if 'url' in reference:
            tree = utils.fetch_tree(
                str(reference.get('url')),
                reference.get('ref'),  # type: ignore
                str(reference.get('path', '.')).lstrip('/'))
        # Use local files
        else:
            root = str(reference.get('path', '.'))
            if not root.startswith('/') and root != '.':
                raise utils.ReferenceError(
                    f'Relative path "{root}" specified.')
            tree = Tree(root)
        found_node = tree.find(str(reference.get('name', '/')))
        if found_node is None:
            raise utils.ReferenceError(
                f"No tree node found for '{reference}' reference")
        assert isinstance(found_node, Tree)
        return found_node

    def copy(self) -> Tree:
        """
        Create and return a deep copy of the node and its subtree

        It is possible to call copy() on any node in the tree, not
        only on the tree root node. Note that in that case, parent
        node and the rest of the tree attached to it is not copied
        in order to save memory.
        """
        original_parent = self.parent
        self.parent = None
        duplicate = copy.deepcopy(self)
        self.parent = duplicate.parent = original_parent
        return duplicate

    def validate(self,
                 schema: JsonSchema,
                 schema_store: Optional[dict[str,
                                             Any]] = None) -> utils.JsonSchemaValidationResult:
        """
        Validate node data with given JSON Schema and schema references.

        schema_store is a dict of schema references and their content.

        Return a named tuple utils.JsonSchemaValidationResult
        with the following two items:

          result ... boolean representing the validation result
          errors ... A list of validation errors

        Raises utils.JsonSchemaError if the supplied schema was invalid.
        """
        schema_store = schema_store or {}
        try:
            resolver = jsonschema.RefResolver.from_schema(
                schema, store=schema_store)
        except AttributeError as error:
            raise utils.JsonSchemaError("Provided schema cannot be loaded.") from error

        validator = jsonschema.Draft4Validator(schema, resolver=resolver)

        try:
            validator.validate(self.data)
            return utils.JsonSchemaValidationResult(True, [])

        # Data file validated by schema contains errors
        except jsonschema.exceptions.ValidationError:
            return utils.JsonSchemaValidationResult(
                False, list(validator.iter_errors(self.data)))

        # Schema file is invalid
        except (
                jsonschema.exceptions.SchemaError,
                jsonschema.exceptions.RefResolutionError,
                jsonschema.exceptions.UnknownType
                ) as error:
            raise utils.JsonSchemaError("Errors found in provided schema:") from error

    def _locate_raw_data(self) -> tuple[TreeData, TreeData, str]:
        """
        Detect location of raw data from which the node has been created

        Find the closest parent node which has raw data defined. In the
        raw data identify the dictionary corresponding to the current
        node, create if needed. Detect the raw data source filename.

        Return tuple with the following three items:

        node_data ... dictionary containing raw data for the current node
        full_data ... full raw data from the closest parent node
        source ... file system path where the full raw data are stored

        """
        # List of node names in the virtual hierarchy
        hierarchy: list[str] = []

        # Find the closest parent with raw data defined
        node = self
        while True:
            # Raw data found
            full_data = node._raw_data
            if full_data:
                break
            # No raw data, perhaps a Tree initialized from a dict?
            if not node.parent:
                raise utils.GeneralError(
                    "No raw data found, does the Tree grow on a filesystem?")
            # Extend virtual hierarchy with the current node name, go up
            hierarchy.insert(0, "/" + node.name.rsplit("/")[-1])
            node = node.parent

        # Localize node data dictionary in the virtual hierarchy
        node_data = full_data
        for key in hierarchy:
            # Create a virtual hierarchy level if missing
            if key not in node_data:
                node_data[key] = {}
            # Initialize as an empty dict if leaf node is empty
            if node_data[key] is None:
                node_data[key] = {}
            assert isinstance(node_data, dict)
            node_data = node_data[key]  # type: ignore

        # The full raw data were read from the last source
        return node_data, full_data, node.sources[-1]

    def __enter__(self) -> TreeData:
        """
        Experimental: Modify metadata and store changes to disk

        This provides an experimental support for storing modified node
        data to disk. For now, the implementation is very simple, data
        are always stored into the last source file from which node data
        were read.

        The provided object contains only raw data. There is no support
        for inheritance, elasticity or data merging. For example, if you
        have defined "key+: value" in the file for node and you will add
        "key: other" it will result into "othervalue".

        Example usage:

            with Tree('.').find('/tests/core/smoke') as test:
                test['tier'] = 0

        Note that white space will be stripped and comments removed as
        export to yaml does not preserve this information. The feature
        is experimental and can be later modified, use at your own risk.
        """
        return self._locate_raw_data()[0]

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Experimental: Store modified metadata to disk """
        _, full_data, source = self._locate_raw_data()
        with open(source, "w", encoding='utf-8') as file:
            file.write(dict_to_yaml(full_data))

    def __getitem__(self, key: str) -> Union[DataType, Tree]:
        """
        Dictionary method to get child node or data item

        To get a child the key has to start with a '/'.
        as identification of child item string
        """
        if key.startswith("/"):
            return self.children[key[1:]]
        else:
            return self.data[key]

    def __len__(self) -> int:
        return len(self.children) + len(self.data)

    def __iter__(self) -> Iterator[str]:
        for c in self.children:
            yield f"/{c}"
        for d in self.data:
            yield d

    def __contains__(self, item: str) -> bool:
        if item.startswith("/"):
            return item[1:] in self.children
        else:
            return item in self.data
