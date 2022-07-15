.. _contribute:

==================
    Contribute
==================


Introduction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Feel free and welcome to contribute to this project. You can start
with filing issues and ideas for improvement in GitHub tracker__.
Our favorite thoughts from The Zen of Python:

* Beautiful is better than ugly.
* Simple is better than complex.
* Readability counts.

We respect the `PEP8`__ Style Guide for Python Code. Here's a
couple of recommendations to keep on mind when writing code:

* Maximum line length is 99 for code and 72 for documentation.
* Comments should be complete sentences.
* The first word should be capitalized (unless identifier).
* When using hanging indent, the first line should be empty.
* The closing brace/bracket/parenthesis on multiline constructs
  is under the first non-whitespace character of the last line

__ https://github.com/psss/fmf
__ https://www.python.org/dev/peps/pep-0008/


Commits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is challenging to be both concise and descriptive, but that is
what a well-written summary should do. Consider the commit message
as something that will be pasted into release notes:

* The first line should have up to 50 characters.
* Complete sentence with the first word capitalized.
* Should concisely describe the purpose of the patch.
* Do not prefix the message with file or module names.
* Other details should be separated by a blank line.

Why should I care?

* It helps others (and yourself) find relevant commits quickly.
* The summary line will be re-used later (e.g. for rpm changelog).
* Some tools do not handle wrapping, so it is then hard to read.
* You will make the maintainers happy to read beautiful commits :)

You can get some more context in the `stackoverflow`__ article.

__ http://stackoverflow.com/questions/2290016/


Develop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to experiment, play with the latest bits and develop
improvements it is best to use a virtual environment::

    mkvirtualenv fmf
    git clone https://github.com/psss/fmf
    cd fmf
    pip install -e .

Install ``python3-virtualenvwrapper`` to easily create and enable
virtual environments using ``mkvirtualenv`` and ``workon``. Note
that if you have freshly installed the package you need to open a
new shell session to enable the wrapper functions.

Install the ``pre-commit`` hooks to run all available checks for
your commits to the project::

    pip install pre-commit
    pre-commit install

Or simply install all extra dependencies to make sure you have
everything needed for the development ready on your system::

    pip install '.[all]'


Makefile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are several Makefile targets defined to make the common
daily tasks easy & efficient:

make test
    Execute the test suite.

make smoke
    Perform quick basic functionality test.

make coverage
    Run the test suite under coverage and report results.

make docs
    Build documentation.

make packages
    Build rpm and srpm packages.

make tags
    Create or update the Vim ``tags`` file for quick searching.
    You might want to use ``set tags=./tags;`` in your ``.vimrc``
    to enable parent directory search for the tags file as well.

make clean
    Cleanup all temporary files.


Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the default set of tests directly on your localhost::

    tmt run

To run tests using pytest with the test coverage overview::

    make coverage

Install pytest and coverage using dnf or pip::

    dnf install python3-pytest python3-coverage
    pip install .[tests]


Docs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For building documentation locally install necessary modules::

    pip install .[docs]

Make sure docutils are installed in order to build man pages::

    dnf install python3-docutils

Building documentation is then quite straightforward::

    make docs

Find the resulting html pages under the ``docs/_build/html``
folder.
