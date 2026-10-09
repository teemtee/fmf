"""Interfaces shared by metadata collectors.

Collectors receive a fresh, uninherited Tree in ``grow(tree, path)``. They
control discovery and selection, then attach raw data with ``load``. Never
call ``inherit`` during collection: the loader retains each contribution
(including duplicate merge keys from different collectors) and applies
inheritance once, after all raw trees have been combined.

For example, a test-framework adapter can use its own collection API::

    from fmf.plugins import Plugin

    class TestsPlugin(Plugin):
        CONFIG_SECTION = 'tests'

        def grow(self, tree, path):
            for item in collect_tests(path, self.config):
                tree.child(item.name, {})
                self.load(tree.children[item.name], item.metadata, item.source)

Here ``collect_tests`` represents the adapter's own implementation, which
may use pytest collection, including classes, parametrization and selection.
A pytest adapter is not bundled. Framework collection may execute imports
and hooks; adapters should document this behavior.

Register a collector as an installed entry point::

    [project.entry-points."fmf.plugins"]
    tests = "my_package:TestsPlugin"

The native collector is registered by the fmf package through the same
mechanism. All filesystem collectors are instantiated once per loaded tree.
Dictionary input uses an in-memory backend without discovering external
packages. Each collector owns a ``merger_class`` instance and may override
its operators or its ``merge`` method. The default merger implements FMF's
``+``, ``+<``, ``-``, ``~`` and ``-~`` syntax.

The lifecycle includes optional root detection (``initialize``), root creation
(``init``), configuration (``read_config``), collection (``grow``), raw updates
(``update``), merging (``merge``) and editing (``read`` and ``write``). A
collector that writes its own sources declares ``writable = True``. Otherwise
the loader asks another collector's ``prepare_edit`` for an editable overlay.
``NotImplementedError`` means a capability is unavailable; parse or I/O errors
are propagated, rather than silently redirected to another writer.

Ordinary collectors run in entry-point name order. Overlay collectors run
last, also in name order. Native FMF is an overlay collector, so a sidecar
created for a read-only test item overrides its collected metadata on reload.
At a node, raw contributions are merged in that order, after inheriting the
parent; repeated ``tags+`` keys therefore append once per contribution. The
last attached source owns direct editing. This does not distribute one edit
across multiple source formats. Virtual children use their nearest source
owner. In-memory edits have no persistent filesystem destination.

Native fallback sidecars materialize effective metadata and override it on
reload. They do not edit the read-only source; removing a sidecar key reveals
any value still provided by that source or its parent. Metadata that cannot
be represented without reinterpreting another backend's operators is rejected.

Compatibility adapters remain on Tree for ``init``, ``grow``, ``child``,
``update``, ``explore_include`` and ``_initialize``; they delegate through the
loader or selected backend, without importing a concrete plugin. The private
``_loader``, ``_plugin`` and ``_inherit`` constructor options are used only for
building raw collector trees. Dictionary context-manager edits now update the
owned raw mapping, rather than raising an unsupported-operation error.

``Tree.climb``, ``find`` and ``prune`` continue to operate on the resulting
in-memory hierarchy, independently of source discovery.
"""

import copy
import re
from abc import ABC, abstractmethod
from pprint import pformat as pretty

import fmf.utils as utils
from fmf.utils import log


class Merger:
    """Format-independent merge operations shared by trees and collectors."""

    def _merge_plus(self, data, key, value, name, prepend=False):
        """
        Handle extending attributes using the '+' suffix
        """

        # Set the value if key is not present
        if key not in data:
            data[key] = value
            return

        # Parent is a list of dict and child is a dict
        # (just update every parent list item using the special merge)
        if isinstance(data[key], list) and isinstance(value, dict):
            for list_item in data[key]:
                if not isinstance(list_item, dict):
                    raise utils.MergeError(
                        "MergeError: Item '{0}' in {1} must be a dictionary.".format(
                            list_item, name))
                self._merge_special(list_item, value, name)
            return

        # Parent is a dict and child is a list of dict
        # (replace parent dict with the list of its special-merged copies)
        if isinstance(data[key], dict) and isinstance(value, list):
            result_list = []
            for list_item in value:
                if not isinstance(list_item, dict):
                    raise utils.MergeError(
                        "MergeError: Item '{0}' in {1} must be a dictionary.".format(
                            list_item, name))
                result_dict = copy.deepcopy(data[key])
                self._merge_special(result_dict, list_item, name)
                result_list.append(result_dict)
            data[key] = result_list
            return

        # Use the special merge for merging dictionaries
        if isinstance(data[key], dict) and isinstance(value, dict):
            self._merge_special(data[key], value, name)
            return

        # Attempt to apply the plus operator
        try:
            if prepend:
                data[key] = value + data[key]
            else:
                data[key] = data[key] + value
        except TypeError as error:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} ({2}).".format(
                    key, name, str(error)))

    def _merge_regexp(self, data, key, value, name):
        """
        Handle substitution of current values
        """

        # Nothing to substitute if the key is not present in parent
        if key not in data:
            return
        if isinstance(value, str):
            value = [value]
        for pattern, replacement in [utils.split_pattern_replacement(v) for v in value]:
            if isinstance(data[key], list):
                try:
                    data[key] = [re.sub(pattern, replacement, original) for original in data[key]]
                except TypeError:
                    raise utils.MergeError(
                        "MergeError: Key '{0}' in {1} (not a string).".format(
                            key, name))
            elif isinstance(data[key], str):
                data[key] = re.sub(pattern, replacement, data[key])
            else:
                raise utils.MergeError(
                    "MergeError: Key '{0}' in {1} (wrong type).".format(
                        key, name))

    def _merge_minus_regexp(self, data, key, value, name):
        """
        Handle removing current values if they match regexp
        """

        # A bit faster but essentially `any`
        def lazy_any_search(item, patterns):
            for p in patterns:
                if re.search(p, str(item)):
                    return True
            return False
        # Nothing to remove if the key is not present in parent
        if key not in data:
            return
        if isinstance(value, str):
            value = [value]
        if isinstance(data[key], list):
            data[key] = [item for item in data[key] if not lazy_any_search(item, value)]
        elif isinstance(data[key], str):
            if lazy_any_search(data[key], value):
                data[key] = ''
        elif isinstance(data[key], dict):
            for k in list(data[key].keys()):
                if lazy_any_search(k, value):
                    data[key].pop(k)
        else:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} (wrong type).".format(
                    key, name))

    def _merge_minus(self, data, key, value, name):
        """
        Handle reducing attributes using the '-' suffix
        """

        # Cannot reduce attribute if key is not present in parent
        if key not in data:
            return
        # Subtract numbers
        if isinstance(data[key], (int, float)) and isinstance(value, (int, float)):
            data[key] = data[key] - value
        # Replace matching regular expression with empty string
        elif isinstance(data[key], str) and isinstance(value, str):
            data[key] = re.sub(value, '', data[key])
        # Remove given values from the parent list
        elif isinstance(data[key], list) and isinstance(value, list):
            data[key] = [item for item in data[key] if item not in value]
        # Remove given key from the parent dictionary
        elif isinstance(data[key], dict) and isinstance(value, list):
            for item in value:
                data[key].pop(item, None)
        else:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} (wrong type).".format(
                    key, name))

    def _merge_special(self, data, source, name):
        """
        Merge source dict into data, handle special suffixes
        """

        for key, value in source.items():
            # Handle special attribute merging
            if key.endswith('+'):
                self._merge_plus(data, key.rstrip('+'), value, name)
            elif key.endswith('+<'):
                self._merge_plus(data, key.rstrip('+<'), value, name, prepend=True)
            elif key.endswith('-~'):
                self._merge_minus_regexp(data, key.rstrip('-~'), value, name)
            elif key.endswith('-'):
                self._merge_minus(data, key.rstrip('-'), value, name)
            elif key.endswith('~'):
                self._merge_regexp(data, key.rstrip('~'), value, name)
            # Otherwise just update the value
            else:
                data[key] = value

    def merge(self, node, data, source):
        """Merge one raw contribution using its originating node for diagnostics."""
        self._merge_special(data, source, node.name)


class Plugin(ABC):
    """Collect raw metadata with format-specific discovery and storage."""

    CONFIG_SECTION = None
    merger_class = Merger
    writable = False
    overlay = False

    def __init__(self):
        self.merger = self.merger_class()
        self.config = {}

    def read_config(self, config):
        """Read this collector's section of the tree configuration."""
        self.config = config.get(self.CONFIG_SECTION, {})
        if not isinstance(self.config, dict):
            raise utils.FileError(f"Plugin config '{self.CONFIG_SECTION}' must be a mapping")

    def initialize(self, tree, path):
        """Detect a supported tree root, returning False if not applicable."""
        return False

    def init(self, path):
        """Create a new tree root, if this format supports it."""
        raise NotImplementedError

    def explore_include(self, tree):
        """Return explicitly included hidden sources for compatibility."""
        return []

    def merge(self, node, data, source):
        """Apply this collector's merge semantics to a raw contribution."""
        self.merger.merge(node, data, source)

    def load(self, node, data, source=None):
        """Attach unmodified raw metadata and remember its source owner."""
        if source is not None:
            node.sources.append(source)
        node._raw_data = copy.deepcopy(data)
        node._source_plugin = self
        node._plugin = self
        self.update(node, data)

    def update(self, node, data):
        """
        Update metadata, handle virtual hierarchy
        """

        # Make a note that the data dictionary has been updated
        # None is handled in the same way as an empty dictionary
        node._updated = True
        # Nothing to do if no data
        if data is None:
            return

        # Handle fmf directives first
        try:
            directives = data.pop("/")
            node._process_directives(directives)
        except KeyError:
            pass

        # Process the metadata
        for key, value in data.items():
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
                node.child(name, value)
            # Update regular attributes
            else:
                node.data[key] = value
        log.debug("Data for '{0}' updated.".format(node))
        log.data(pretty(node.data))

    @abstractmethod
    def grow(self, tree, path):
        """Collect a raw tree using this format's traversal and selection.

        Recurse through this method, not Tree.grow(), to avoid invoking
        unrelated collectors. Keep merge keys intact until inheritance.
        """

    def read(self, node):
        """Return editable raw metadata for a node."""
        raise NotImplementedError(f"{type(self).__name__} does not support editing")

    def write(self, node):
        """Persist edited raw metadata."""
        raise NotImplementedError(f"{type(self).__name__} does not support writing")

    def prepare_edit(self, node):
        """Return a separate editable overlay node, or decline this capability."""
        raise NotImplementedError
