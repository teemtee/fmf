"""Metadata collectors with their own discovery and storage methods."""

import copy
import re
from abc import ABC, abstractmethod
from inspect import isabstract

import fmf.utils as utils
from fmf._compat.metadata import entry_points


class _Merge:
    """Format-independent merge operations shared by trees and collectors."""

    def __init__(self, name):
        self.name = name

    def _merge_plus(self, data, key, value, prepend=False):
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
                            list_item, self.name))
                self._merge_special(list_item, value)
            return

        # Parent is a dict and child is a list of dict
        # (replace parent dict with the list of its special-merged copies)
        if isinstance(data[key], dict) and isinstance(value, list):
            result_list = []
            for list_item in value:
                if not isinstance(list_item, dict):
                    raise utils.MergeError(
                        "MergeError: Item '{0}' in {1} must be a dictionary.".format(
                            list_item, self.name))
                result_dict = copy.deepcopy(data[key])
                self._merge_special(result_dict, list_item)
                result_list.append(result_dict)
            data[key] = result_list
            return

        # Use the special merge for merging dictionaries
        if isinstance(data[key], dict) and isinstance(value, dict):
            self._merge_special(data[key], value)
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
                    key, self.name, str(error)))

    def _merge_regexp(self, data, key, value):
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
                            key, self.name))
            elif isinstance(data[key], str):
                data[key] = re.sub(pattern, replacement, data[key])
            else:
                raise utils.MergeError(
                    "MergeError: Key '{0}' in {1} (wrong type).".format(
                        key, self.name))

    def _merge_minus_regexp(self, data, key, value):
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
                    key, self.name))

    def _merge_minus(self, data, key, value):
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
                    key, self.name))

    def _merge_special(self, data, source):
        """
        Merge source dict into data, handle special suffixes
        """

        for key, value in source.items():
            # Handle special attribute merging
            if key.endswith('+'):
                self._merge_plus(data, key.rstrip('+'), value)
            elif key.endswith('+<'):
                self._merge_plus(data, key.rstrip('+<'), value, prepend=True)
            elif key.endswith('-~'):
                self._merge_minus_regexp(data, key.rstrip('-~'), value)
            elif key.endswith('-'):
                self._merge_minus(data, key.rstrip('-'), value)
            elif key.endswith('~'):
                self._merge_regexp(data, key.rstrip('~'), value)
            # Otherwise just update the value
            else:
                data[key] = value


class Plugin(ABC):
    """Collect a complete hierarchy, without a shared filesystem walk.

    Instances belong to one tree. ``grow`` chooses which files or test
    items to collect, and adds raw metadata through ``load`` and Tree.child.
    Inheritance is applied by Tree once all collectors have finished.
    """

    CONFIG_SECTION = None

    def read_config(self, config):
        """Read this collector's optional section of .fmf/config."""
        self.config = config.get(self.CONFIG_SECTION, {})
        if not isinstance(self.config, dict):
            raise utils.FileError(f"Plugin config '{self.CONFIG_SECTION}' must be a mapping")

    @classmethod
    def for_tree(cls, config):
        """Create configured collectors, with native FMF metadata loaded first."""
        from fmf.plugins.fmf import FmfPlugin

        classes = [FmfPlugin]
        for entry in entry_points(group='fmf.plugins'):
            try:
                plugin = entry.load()
                if not isinstance(plugin, type) or not issubclass(plugin, Plugin):
                    raise TypeError("entry point must provide a Plugin subclass")
                if isabstract(plugin):
                    raise TypeError("entry point must provide a concrete Plugin subclass")
                if plugin not in classes:
                    classes.append(plugin)
            except Exception as error:
                raise utils.FileError(f"Failed to load plugin '{entry.name}': {error}") from error
        instances = []
        for plugin in classes:
            instance = plugin()
            instance.read_config(config)
            instances.append(instance)
        return instances

    @staticmethod
    def merge(node, data, source):
        """Apply the common +, -, and regexp operators to a data mapping."""
        _Merge(node.name)._merge_special(data, source)

    def load(self, node, data, source):
        """Attach raw metadata and its storage owner to an in-memory node."""
        node.sources.append(str(source))
        node._raw_data = copy.deepcopy(data)
        node._source_plugin = self
        node.update(data)

    @staticmethod
    def for_node(node):
        """Find the collector responsible for a node's editable source."""
        while node._source_plugin is None:
            if node.parent is None:
                raise utils.GeneralError(
                    "No raw data found, does the Tree grow on a filesystem?")
            node = node.parent
        return node._source_plugin

    @abstractmethod
    def grow(self, tree, path):
        """Discover and select this format's metadata under path.

        A collector may walk directories, invoke a test framework's collection
        API, or enumerate other sources. Recursive discovery belongs here;
        call this method directly when descending, not Tree.grow().
        """

    def read(self, node):
        """Return editable raw metadata for a node."""
        raise NotImplementedError(f"{type(self).__name__} does not support editing")

    def write(self, node):
        """Persist a node's edited raw metadata."""
        raise NotImplementedError(f"{type(self).__name__} does not support writing")
