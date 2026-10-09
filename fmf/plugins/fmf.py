"""Native FMF discovery and storage, moved from Tree."""

import copy
import os
from pathlib import Path
from pprint import pformat as pretty

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError

import fmf.utils as utils
from fmf.plugins import Plugin
from fmf.plugins.dictionary import DictionaryPlugin
from fmf.utils import dict_to_yaml, log

SUFFIX = ".fmf"
MAIN = "main" + SUFFIX
IGNORED_DIRECTORIES = ['/dev', '/proc', '/sys']


class FmfPlugin(Plugin):
    """Discover .fmf files using the original recursive directory walk."""

    CONFIG_SECTION = 'fmf'
    writable = True
    overlay = True

    def __init__(self):
        super().__init__()
        self.dictionary = DictionaryPlugin()
        self._symlinkdirs = []

    def initialize(self, tree, path):
        """
        Find metadata tree root, detect format version, check for config
        """

        # Find the tree root
        root = os.path.abspath(path)
        try:
            while ".fmf" not in next(os.walk(root))[1]:
                if root == "/":
                    return False
                root = os.path.abspath(os.path.join(root, os.pardir))
        except StopIteration:
            raise utils.FileError("Invalid directory path: {0}".format(root))
        log.info("Root directory found: {0}".format(root))
        tree.root = root

        # Detect format version
        try:
            with open(os.path.join(tree.root, ".fmf", "version")) as version:
                tree.version = int(version.read())
                log.info("Format version detected: {0}".format(tree.version))
        except IOError as error:
            raise utils.FormatError(
                "Unable to detect format version: {0}".format(error))
        except ValueError:
            raise utils.FormatError("Invalid version format")

        # Check for the config file
        config_file_path = Path(tree.root) / ".fmf/config"
        try:
            tree.config = YAML(typ="safe").load(config_file_path.read_text())
            if tree.config is None:
                tree.config = {}
            if not isinstance(tree.config, dict):
                raise utils.FileError("The fmf config must be a mapping")
            log.debug(f"Config file '{config_file_path}' loaded.")
        except FileNotFoundError:
            log.debug("Config file not found.")
        except YAMLError as error:
            raise utils.FileError(f"Failed to parse '{config_file_path}'.\n{error}")

        return True

    def init(self, path):
        """
        Create metadata tree root under given path
        """

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

    def explore_include(self, tree):
        """
        Additional filenames to be explored
        """

        try:
            explore_include = tree.config["explore"]["include"]
            if not isinstance(explore_include, list):
                raise utils.GeneralError(
                    f"The 'include' config section should be a list, found '{explore_include}'.")
            if ".fmf" in explore_include:
                raise utils.GeneralError(
                    "The '.fmf' directory cannot be used for storing fmf metadata.")
        except KeyError:
            explore_include = []
        return explore_include

    def grow(self, tree, path):
        """
        Grow the metadata tree for the given directory path

        Note: For each path, grow() should be run only once. Growing the tree
        from the same path multiple times with attribute adding using the "+"
        sign leads to adding the value more than once!
        """

        if path != '/':
            path = path.rstrip("/")
        if path in IGNORED_DIRECTORIES:  # pragma: no cover
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
            if filename.startswith(".") and filename not in self.explore_include(tree):
                continue
            fullpath = os.path.abspath(os.path.join(dirpath, filename))
            log.info("Checking file {0}".format(fullpath))
            try:
                with open(fullpath, encoding='utf-8') as datafile:
                    # Workadound ruamel s390x read issue - fmf/issues/164
                    content = datafile.read()
                    data = YAML(typ="safe").load(content)
            except (YAMLError, DuplicateKeyError) as error:
                raise utils.FileError(
                    f"Failed to parse '{fullpath}'.\n{error}")
            log.data(pretty(data))
            # Handle main.fmf as data for self
            if filename == MAIN:
                self.load(tree, data, fullpath)
            # Handle other *.fmf files as children
            else:
                name = os.path.splitext(filename)[0]
                tree.child(name, data, fullpath)
                tree.children[name]._source_plugin = self

        # Explore every child directory (ignore hidden dirs and subtrees)
        for dirname in sorted(dirnames):
            if dirname.startswith(".") and dirname not in self.explore_include(tree):
                continue
            fulldir = os.path.join(dirpath, dirname)
            if os.path.islink(fulldir):
                # According to the documentation, calling os.path.realpath
                # with strict = True will raise OSError if a symlink loop
                # is encountered. But it does not do that with a loop with
                # more than one node
                fullpath = os.path.realpath(fulldir)
                if fullpath in self._symlinkdirs:
                    log.debug("Not entering symlink loop {}".format(fulldir))
                    continue
                else:
                    self._symlinkdirs.append(fullpath)

            # Ignore metadata subtrees
            if os.path.isdir(os.path.join(path, dirname, SUFFIX)):
                log.debug("Ignoring metadata tree '{0}'.".format(dirname))
                continue
            if dirname not in tree.children:
                tree.child(dirname, {})
                tree.children[dirname]._updated = False
            self.grow(tree.children[dirname], os.path.join(path, dirname))

        # Ignore directories with no metadata (remove all child nodes which
        # do not have children and their data haven't been updated)
        for name in list(tree.children.keys()):
            child = tree.children[name]
            if not child.children and not child._updated:
                del tree.children[name]
                log.debug("Empty tree '{0}' removed.".format(child.name))

    def read(self, node):
        return self.dictionary.locate(node)[0]

    def write(self, node):
        _, full_data, owner = self.dictionary.locate(node)
        destination = Path(owner.sources[-1])
        if getattr(owner, '_new_source', False):
            destination.parent.mkdir(parents=True, exist_ok=True)
            mode = 'x'
        else:
            mode = 'w'
        content = dict_to_yaml(full_data)
        with destination.open(mode, encoding='utf-8') as file:
            file.write(content)
        owner._new_source = False

    def prepare_edit(self, node):
        """Provide a native sidecar for a read-only collector's metadata."""
        from fmf.base import Tree

        if node.root is None:
            raise NotImplementedError
        root = Path(node.root).resolve()
        relative = node.name.lstrip('/')
        destination = root / (relative + SUFFIX) if relative else root / MAIN
        if not destination.resolve().is_relative_to(root):
            raise utils.FileError(f"Sidecar destination is outside the tree: {destination}")
        new_source = not destination.exists()
        if new_source:
            # A fallback is an explicit snapshot of effective metadata, not a
            # reinterpretation of another collector's raw operator syntax.
            data = copy.deepcopy(node.data)
            roundtrip = {}
            self.merge(node, roundtrip, copy.deepcopy(data))
            if roundtrip != data:
                raise utils.FileError(
                    f"FMF cannot represent '{node.name}' without reinterpreting merge keys.")
        else:
            try:
                data = YAML(typ="safe").load(destination.read_text(encoding='utf-8'))
            except YAMLError as error:
                raise utils.FileError(f"Failed to parse '{destination}'.\n{error}") from error
        editable = Tree({}, _loader=node._loader, _plugin=self, _inherit=False)
        editable.name, editable.root = node.name, node.root
        self.load(editable, data, str(destination))
        editable._new_source = new_source
        return editable
