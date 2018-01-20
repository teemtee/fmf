
======================
    Concept
======================

In order to keep test execution efficient when number of test
cases grows, it is crucial to maintain corresponding metadata,
which define some aspects of how the test coverage is executed.

This tool implements a flexible format for defining metadata in
plain text files which can be stored close to the test code and
structured in a hiearchical way with support for inheritance.

Although the proposal initially originated from user stories
centered around test execution, the format is general and thus
can be used in broader scenarios, e.g. test coverage mapping.

Using this approach it's also possible to combine both test
execution metadata and test coverage information. Thanks to
elasticity and hiearchy it provides ability to organize data
into well-sized text documents while preventing duplication.


Stones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are essential corner stones for the design:

* Text files under version control
* Keep common uses cases simple
* Use hiearchy to organize content
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


Naming
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A dedicated file name extension ``fmf`` as an abbreviation of
Flexible Metadata Format to easily find all metadata files:

* main.fmf
* smoke.fmf

The format does not define attribute naming in any way. This is up
to individual projects. The only exception is the special name
``main`` which is reserved for main directory index.

Attribute namespacing can be introduced as needed to prevent
collisions between similar attributes. For example:

* test-description, requirement-description
* test:description, requirement:description
* test_description, requirement_description


Objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Objects are identified by path from the root directory. Special
file name ``main.fmf`` works similarly as ``index.html``:

    +-------------------------------+-----------------------+
    | Location                      | Identifier            |
    +===============================+=======================+
    | wget/main.fmf                 | wget                  |
    +-------------------------------+-----------------------+
    | wget/download/main.fmf        | wget/download         |
    +-------------------------------+-----------------------+
    | wget/download/smoke.fmf       | wget/download/smoke   |
    +-------------------------------+-----------------------+
