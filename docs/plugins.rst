.. _plugins:

Plugins
=======

Metadata plugins are discovered automatically from installed Python
packages. Each plugin documents the file formats and options it supports.
Only install plugin packages you trust: loading them executes Python code.

Plugin options belong in the plugin's named section of ``.fmf/config``.
See the plugin's documentation for its section name and supported options.

Built-in plugins
----------------

The fmf plugin reads and writes YAML metadata in ``.fmf`` files. It has
no configurable options. Writing preserves metadata structure and merge
keys, but does not preserve YAML comments or formatting.

For implementation details, see :ref:`writing-plugins`.
