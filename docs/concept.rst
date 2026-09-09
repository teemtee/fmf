
======================
    Concept
======================

In order to keep test execution efficient when number of test
cases grows, it is crucial to maintain corresponding metadata,
which define some aspects of how the test coverage is executed.

This tool implements a flexible format for defining metadata in
plain text files which can be stored close to the test code and
structured in a hierarchical way with support for inheritance.

Although the proposal initially originated from user stories
centered around test execution, the format is general and thus
can be used in broader scenarios, e.g. test coverage mapping.

Using this approach it's also possible to combine both test
execution metadata and test coverage information. Thanks to
elasticity and hierarchy it provides ability to organize data
into well-sized text documents while preventing duplication.


Stones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are essential corner stones for the design:

* Text files under version control
* Keep common uses cases simple
* Use hierarchy to organize content
* Prevent duplication where possible
* Metadata close to the test code
* Solution should be open source
* Focus on essential use cases


Stories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Important user stories to be covered:

* As a tester or developer I want to easy read and modify metadata and see history.
* As a tester I want to select a subset of test cases for execution by specifying a tag.
* As a tester I want to define a maximum time for a test case to run.
* As a tester I want to specify which environment is relevant for testing.
* As a user I want to easily define common metadata for multiple cases to simplify maintenance.
* As a user I want to provide specific metadata for selected tests to complement common metadata.
* As an individual tester and test contributor I want to execute specific single test case.
* As an automation tool I need a metadata storage with good api, extensible, quick for reading.


Choices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These choices have been made:

* Use git for version control and history of changes.
* Yaml format easily readable for both machines and humans.


Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A dedicated file name extension ``fmf`` as an abbreviation of
Flexible Metadata Format is used to easily find all metadata
files on the filesystem:

* smoke.fmf
* main.fmf

Special file name ``main.fmf`` works similarly as ``index.html``.
It can be used to define the top level data for the directory. All
metadata files are expected to be using the ``utf-8`` encoding.


Attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The format does not define attribute naming in any way. This is up
to individual projects. The only exception is the special name
``main`` which is reserved for main directory index.

Attribute namespacing can be introduced as needed to prevent
collisions between similar attributes. For example:

* test-description, requirement-description
* test:description, requirement:description
* test_description, requirement_description


.. _trees:

Trees
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Metadata form a tree where inheritance is applied. The tree root
is defined by an ``.fmf`` directory (similarly as ``.git``
identifies top of the git repository). The ``.fmf`` directory
contains at least a ``version`` file with a single integer number
defining version of the format.


.. _config:

Config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, all hidden files are ignored when exploring metadata
on the disk. If a specific file or directory should be included in
the search, create a simple config file ``.fmf/config`` with the
following format:

.. code-block:: yaml

    explore:
        include:
          - .plans
          - .tests

In the example above files or directories named ``.plans`` or
``.tests`` will be included in the discovered metadata. Note that
the ``.fmf`` directory cannot be used for storing metadata.


Plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.8

A plugin system allows reading metadata from multiple file formats
beyond ``.fmf`` (YAML) files. This enables extracting test metadata
directly from source files like Python tests or Bash scripts. The
built-in ``FmfPlugin`` handles the traditional ``.fmf`` files and is
always available.

Registration
------------

Plugins are discovered through the ``fmf.plugins`` `entry point group
<https://packaging.python.org/en/latest/specifications/entry-points/>`__.
A package advertises a plugin in its ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."fmf.plugins"]
    bash = "mypackage.plugins:BashPlugin"

Any plugin installed in the current environment is picked up
automatically.

Loading order
-------------

When more than one plugin can handle the same file, the first plugin in
load order (the order in which the plugin modules are discovered) is used.
The order is not user configurable.

.. warning::

    As with :ref:`elasticity <elasticity>`, the resolution order when the
    *same* node is defined by several formats (for example a ``.fmf`` file
    and a source file at the same level) is not yet fully specified. Avoid
    relying on cross-format overrides until the behavior is well defined.

Configuration
-------------

Each plugin can read its own section from the ``.fmf/config`` file. A
plugin declares the name of its section through the ``config_section``
class attribute and picks up the settings by implementing the
``read_config()`` method. This keeps every plugin's options isolated in
a dedicated, clearly named block:

.. code-block:: yaml

    # .fmf/config
    fmf:
        # options for the built-in FmfPlugin
    bash:
        # options for a bash plugin

A plugin receives the whole parsed config and reads just its own part,
for example::

    class BashPlugin(Plugin):
        config_section = "bash"

        def read_config(self, config):
            self.settings = self.config_section_data(config)

The ``config_section_data()`` helper returns the mapping stored under the
plugin's ``config_section`` (or an empty dict when the section is missing
or the plugin defines no section). The built-in ``FmfPlugin`` reads the
``fmf`` section; it currently has no options and the section is reserved
for future settings.

Because the config is identical for every node in a tree, ``read_config()``
is called only *once per tree*, not for each file.

Performance
-----------

The plugin layer keeps loading fast. A single instance of each plugin is
created and reused for the whole tree instead of being constructed for every
file. Trees can hold thousands of ``.fmf`` files and constructing a plugin is
not free (``FmfPlugin`` builds a YAML parser in its constructor), so caching
the instance avoids a per-file cost that would otherwise dominate on large
trees. Plugins must therefore keep no per-file state: :meth:`read` and
:meth:`write` receive the filename as an argument, and configuration is
applied once via ``read_config()``.

File matching is also kept cheap. The default ``can_handle()`` checks the
plugin's ``extensions`` (a plain suffix test) first and only then its
``file_patterns``, which are compiled to regular expressions once and cached
on the class rather than recompiled for every file.

Available plugins
-----------------

* ``fmf.plugins.fmf.FmfPlugin`` -- YAML-based ``.fmf`` files (built-in)

Additional plugins (Bash scripts, Python/pytest tests) are planned; see
``PLUGIN_FUTURE.md`` for the implementation roadmap.


Names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Individual tree nodes are identified by path from the metadata
root directory plus optional hierarchy defined inside yaml files.
For example, let's have the metadata root defined in the ``wget``
directory. Below you can see node names for different files:


    +-------------------------------+-----------------------+
    | Location                      | Name                  |
    +===============================+=======================+
    | wget/main.fmf                 | /                     |
    +-------------------------------+-----------------------+
    | wget/download/main.fmf        | /download             |
    +-------------------------------+-----------------------+
    | wget/download/smoke.fmf       | /download/smoke       |
    +-------------------------------+-----------------------+


Identifiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Node names are unique across the metadata tree and thus can be
used as identifiers for local referencing across the same tree. In
order to reference remote fmf nodes from other trees a full ``fmf
identifier`` is defined as a dictionary containing keys with the
following meaning:

url
    Git repository containing the metadata tree. Use any format
    acceptable by the ``git clone`` command. Optional, if no
    repository url is provided, local files will be used.
ref
    Branch, tag or commit specifying the desired git revision.
    This is used to perform a ``git checkout`` in the repository.
    If not provided, the ``default branch`` is used.
path
    Path to the metadata tree root. Should be relative to the git
    repository root if ``url`` provided, absolute local filesystem
    path otherwise. Optional, by default ``.`` is used.
name
    Node name as defined by the hierarchy in the metadata tree.
    Optional, by default the parent node ``/`` is used, which
    represents the whole metadata tree.

Here's a full fmf identifier example::

    url: https://github.com/psss/fmf
    ref: 0.10
    path: /examples/wget
    name: /download/test

Use default values for ``ref`` and ``path`` to reference the
latest version of the smoke plan from the default branch::

    url: https://github.com/psss/fmf
    name: /plans/smoke

If desired, it is also possible to write the identifier on a
single line as supported by the ``yaml`` format::

    {url: "https://github.com/psss/fmf", name: "/plans/smoke"}

Let's freeze the stable test version by using a specific commit::

    url: https://github.com/psss/fmf
    ref: f24ef3f
    name: /tests/basic/filter

Reference a smoke plan from another metadata tree stored on the
local filesystem::

    path: /home/psss/git/tmt
    name: /plans/smoke

Local reference across the same metadata tree is also supported::

    name: /plans/smoke
