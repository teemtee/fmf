
======================
    fmf
======================

Flexible Metadata Format


Description
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``fmf`` Python module and command line tool implement a
flexible format for defining metadata in plain text files which
can be stored close to the source code and structured in a
hiearchical way with support for inheritance.

Although the proposal initially originated from user stories
centered around test execution, the format is general and thus
can be used in broader scenarios, e.g. test coverage mapping.

Using this approach it's also possible to combine both test
execution metadata and test coverage information. Thanks to
elasticity and hiearchy it provides ability to organize data
into well-sized text documents while preventing duplication.


Synopsis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Command line usage is straightforward::

    fmf [path...] [options]


Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

List all metadata stored in the current directory::

    fmf

Show all test metadata (with 'test' attribute defined)::

    fmf --key test

List all attributes for the ``wget/recursion`` tests::

    fmf --name wget/recursion

See ``fmf --help`` for complete list of available options.


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

--whole
    Consider the whole tree (leaves only by default)

Format
------

Choose the best format for showing the metadata.

--brief
    Show object names only (no attributes)

--format=FMT
    Output format (now: text, future: json, yaml)

Utils
-----

Various utility options.

--verbose
    Print additional information standard error output

--debug
    Turn on debugging output, do not catch exceptions

See ``fmf --help`` for complete list of available options.


Install
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install from the Copr repository::

    yum install fmf

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
https://pypi.python.org/pypi/fmf


Authors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Petr Šplíchal


Copyright
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copyright (c) 2018 Red Hat, Inc.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or (at your option) any later version.
