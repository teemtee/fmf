
======================
    fmf
======================

Flexible Metadata Format


Description
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``fmf`` Python module and command line tool implement a
flexible format for defining metadata in plain text files which
can be stored close to the source code and structured in a
hierarchical way with support for inheritance.

Although the proposal initially originated from user stories
centered around test execution, the format is general and thus
can be used in broader scenarios, e.g. test coverage mapping.

Using this approach it's also possible to combine both test
execution metadata and test coverage information. Thanks to
elasticity and hierarchy it provides ability to organize data
into well-sized text documents while preventing duplication.


Synopsis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Command line usage is straightforward::

    fmf command [options]

There are following commands available::

    fmf ls      List identifiers of available objects
    fmf show    Show metadata of available objects
    fmf init    Initialize a new metadata tree


Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

List names of all objects stored in the metadata tree::

    fmf ls

Show all test metadata (with 'test' attribute defined)::

    fmf show --key test

Show metadata for all tree nodes (not only leaves)::

    fmf show --key test --whole

List all attributes for the ``/recursion`` tests::

    fmf show --key test --name /recursion

Show all covered requirements::

    fmf show --key requirement --key coverage

Search for all tests with the ``Tier1`` tag defined and show a
brief summary of what was found::

    fmf show --key test --filter tags:Tier1 --verbose

Use arbitrary Python expressions to access deeper objects and
create more complex conditions::

    fmf show --condition "execute['how'] == 'shell'"

Initialize a new metadata tree in the current directory::

    fmf init

Check help message of individual commands for the full list of
available options.


Options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is the list of the most frequently used options.

Select
------

Limit which metadata should be listed.

--key=KEYS
    Key content definition (required attributes)

--name=NAMES
    List objects with name matching regular expression

--filter=FLTRS
    Apply advanced filter when selecting objects

--condition=EXPR
    Use arbitrary Python expression for filtering

--whole
    Consider the whole tree (leaves only by default)

For filtering regular expressions can be used as well. See
``pydoc fmf.filter`` for advanced filtering options.

Format
------

Choose the best format for showing the metadata.

--format=FMT
    Custom output format using the {} expansion

--value=VALUES
    Values for the custom formatting string

See online documentation for details about custom format.

Utils
-----

Various utility options.

--path PATHS
    Path to the metadata tree (default: current directory)

--verbose
    Print additional information standard error output

--debug
    Turn on debugging output, do not catch exceptions

Check help message of individual commands for the full list of
available options.


Install
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fmf package is available in Fedora and EPEL::

    dnf install fmf

Install the latest version from the Copr repository::

    dnf copr enable psss/fmf
    dnf install fmf

or use PIP (sudo required if not in a virtualenv)::

    pip install fmf

See documentation for more details about installation options.


Links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Git:
https://github.com/psss/fmf

Docs:
http://fmf.readthedocs.io/

Issues:
https://github.com/psss/fmf/issues

Releases:
https://github.com/psss/fmf/releases

Copr:
http://copr.fedoraproject.org/coprs/psss/fmf

PIP:
https://pypi.org/project/fmf/

Travis:
https://travis-ci.org/psss/fmf

Coveralls:
https://coveralls.io/github/psss/fmf


Authors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Petr Šplíchal, Jakub Krysl, Jan Ščotka, Alois Mahdal and Cleber
Rosa.


Copyright
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copyright (c) 2018 Red Hat, Inc.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or (at your option) any later version.

Nothing...
