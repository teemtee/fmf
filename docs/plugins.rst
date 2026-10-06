Metadata plugins
================

Plugins collect metadata using their own discovery and selection methods.
``Tree.grow()`` calls each collector once for the requested path; it does not
walk files or dispatch by extension. The built-in ``FmfPlugin`` retains the
native FMF directory walk, YAML loading, root detection and write-back.
``Tree`` keeps the in-memory hierarchy, inheritance, adjustment, filtering and
display API. Existing FMF trees need no configuration changes.

Writing a collector
-------------------

Subclass ``fmf.plugin.Plugin`` and implement ``grow(tree, path)``. Create nodes
with ``tree.child(name, data)`` or nested dictionaries, and attach editable
source metadata with ``self.load(node, data, source)``. ``load`` records the
collector that owns the source. A source can represent multiple collected
items, rather than one metadata file per node.

For example, a framework adapter can collect test items itself::

    from fmf.plugin import Plugin

    class TestsPlugin(Plugin):
        CONFIG_SECTION = 'tests'

        def grow(self, tree, path):
            for item in collect_tests(path, self.config):
                tree.child(item.name, {})
                self.load(tree.children[item.name], item.metadata, item.source)

``collect_tests`` here stands for the adapter's own discovery implementation.
A pytest adapter could use pytest collection (including its selection rules,
classes and parametrized items); it is not restricted to parsing individual
``.py`` files. Such an adapter is not included in fmf. Framework collection
may import test modules and execute collection hooks, so the adapter must
document that behavior.

Recursive collectors call their own ``grow`` method, not ``Tree.grow``:
otherwise every collector would be invoked again for each directory. The FMF
collector's hidden-file, subtree and symlink rules apply only to FMF discovery;
other collectors define and document their own traversal boundaries.

All collectors finish before inheritance and the standard ``+``, ``+<``, ``-``,
``~`` and ``-~`` operations are applied. These operations live in the common
plugin module and can also be called with ``Plugin.merge(node, data, source)``.
Prefer supplying raw merge keys through ``load`` so inheritance applies them
once. ``Tree.climb`` and ``Tree.prune`` continue to query the combined metadata
hierarchy after collection; format-specific test selection belongs in ``grow``.

Registration and configuration
------------------------------

Advertise an installed plugin using an entry point::

    [project.entry-points."fmf.plugins"]
    tests = "my_package:TestsPlugin"

The built-in FMF collector always runs first, including when fmf is used from
a source checkout. External collectors follow entry-point discovery order;
registering the same class more than once does not run it twice. Instances
and configuration are local to each tree. The default ``read_config`` reads
the mapping named by ``CONFIG_SECTION`` from ``.fmf/config``; a plugin can
override it to validate its own options. No file-matching registry is involved.
A filesystem tree still uses ``.fmf/version`` to identify its root.

When collectors contribute to the same node, later updates replace matching
raw keys and retain other keys, as with ``Tree.update``. External entry-point
order is not a priority contract: plugins should avoid overlapping ownership.
Only the most recently attached source is edited for a node; write-back does
not distribute edits over multiple formats. Installed plugins are Python code
and are trusted like other installed dependencies.

Storage
-------

Implement ``read(node)`` to return an editable raw mapping and ``write(node)``
to persist it. The Tree context manager delegates both operations to the
collector that attached the node's source (or its closest source-owning
ancestor for virtual children). Collectors that do not implement these methods
are read-only and raise ``NotImplementedError`` when editing is attempted.
There is no automatic YAML fallback for another format.

The FMF collector uses the existing raw hierarchy lookup and YAML serialization.
As before, write-back preserves raw merge keys but strips comments and
formatting. It remains experimental and writes on context exit, including when
the context body raises an exception. Empty FMF source mappings are editable.
