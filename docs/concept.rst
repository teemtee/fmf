
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
