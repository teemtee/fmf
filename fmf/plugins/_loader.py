"""Discover collectors and combine their raw hierarchies before inheritance."""

import copy
from inspect import isabstract

import fmf.utils as utils
from fmf._compat.metadata import entry_points
from fmf.plugins._base import Plugin
from fmf.plugins.dictionary import DictionaryPlugin


class Loader:
    """Own collector instances and lifecycle for one Tree."""

    def __init__(self):
        self.dictionary = DictionaryPlugin()
        self.plugins = None
        self.context = None

    def discover(self):
        if self.plugins is not None:
            return self.plugins
        instances = []
        classes = set()
        for entry in sorted(entry_points(group='fmf.plugins'), key=lambda entry: entry.name):
            try:
                plugin = entry.load()
                if not isinstance(plugin, type) or not issubclass(plugin, Plugin):
                    raise TypeError("entry point must provide a Plugin subclass")
                if isabstract(plugin):
                    raise TypeError("entry point must provide a concrete Plugin subclass")
                if plugin not in classes:
                    instances.append(plugin())
                    classes.add(plugin)
            except Exception as error:
                raise utils.FileError(f"Failed to load plugin '{entry.name}': {error}") from error
        self.plugins = sorted(instances, key=lambda plugin: plugin.overlay)
        return self.plugins

    def initialize(self, tree, path):
        for plugin in self.discover():
            if plugin.initialize(tree, path):
                self.context = plugin
                return
        raise utils.RootError(f"No installed metadata plugin recognizes '{path}'.")

    def init(self, path):
        for plugin in self.discover():
            try:
                return plugin.init(path)
            except NotImplementedError:
                continue
        raise utils.RootError("No installed metadata plugin can initialize a tree.")

    def load(self, tree, data):
        """Interpret input at the backend boundary, keeping Tree format-neutral."""
        if isinstance(data, dict) or data is None:
            if tree.parent is None:
                tree._plugin.load(tree, data)
            else:
                tree.update(data)
        else:
            if tree.parent is None:
                self.initialize(tree, data)
                data = tree.root
            self.grow(tree, data)

    def child(self, tree, name, data, source=None):
        from fmf.base import Tree

        if name not in tree.children:
            tree.children[name] = Tree({}, name, parent=tree, _loader=self,
                                       _plugin=tree._plugin, _inherit=False)
        node = tree.children[name]
        if source is not None:
            tree._plugin.load(node, data, source)
        else:
            self.load(node, data)

    def grow(self, tree, path):
        from fmf.base import Tree

        for plugin in self.discover():
            plugin.read_config(tree.config)
            raw = Tree({}, _loader=self, _plugin=plugin, _inherit=False)
            raw.root, raw.config, raw.version = tree.root, tree.config, tree.version
            raw.name = tree.name
            raw._updated = False
            raw._source_plugin = None
            plugin.grow(raw, path)
            self.combine(tree, raw)

    def combine(self, target, raw):
        """Retain ordered raw layers, including repeated keys such as tags+."""
        if not target._layers and target.data:
            target._layers.append((target._plugin, copy.deepcopy(target.data)))
        if raw._updated:
            target._layers.append((raw._plugin, copy.deepcopy(raw.data)))
            target._pending_layers = True
            target.data.update(copy.deepcopy(raw.data))
            target._plugin = raw._plugin
            target._updated = True
            if self.owner(raw) is not None:
                # Keep the collector's original ancestry for virtual-source
                # lookup; combined parents may belong to another collector.
                target._source_node = raw
        target._directives.update(raw._directives)
        if raw._source_plugin is not None:
            target._source_plugin = raw._source_plugin
            target._raw_data = raw._raw_data
        target.sources.extend(raw.sources)
        for name, child in raw.children.items():
            if name not in target.children:
                self.child(target, name, {})
            self.combine(target.children[name], child)

    def merge(self, node, data):
        if node._pending_layers:
            for plugin, source in node._layers:
                plugin.merge(node, data, copy.deepcopy(source))
            node._pending_layers = False
        else:
            node._plugin.merge(node, data, node.data)

    def owner(self, node):
        node = node._source_node or node
        while node._source_plugin is None:
            if node.parent is None:
                return None
            node = node.parent
        return node._source_plugin

    def edit(self, node):
        owner = self.owner(node)
        if owner is not None and owner.writable:
            return owner, node._source_node or node
        for plugin in self.discover():
            try:
                return plugin, plugin.prepare_edit(node)
            except NotImplementedError:
                continue
        raise utils.FileError(f"No installed plugin can store edits for '{node.name}'.")

    def explore_include(self, tree):
        if self.context is None:
            return []
        return self.context.explore_include(tree)
