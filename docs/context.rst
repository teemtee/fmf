.. _context:

======================
    Context
======================

Motivation
~~~~~~~~~~~~~~~~~~~~~~

Imagine you have a test which can run only for Fedora-33 and newer.
Or your tests' require depend on which distribution you are running.

For all these cases you need just a slight tweak to your metadata
but you can't really use Virtual cases as only one of them should run.

And here is where Context will help you.

Example - Disable test by setting enabled attribute
    enabled: True
    adjust:
        when: distro < Fedora-33
        enabled: False
        because: Feature was added in Fedora-33

Example - Tweak require attribute
    require:
        - procps-ng
    adjust:
        when: distro ~= centos-6
        require: procps


Syntax
~~~~~~~~~~~~~~~~~~~~~~

    rule ::= expression (bool expression)*
    bool ::= and | or
    expression ::= dimension operator values
    expression ::= dimension operator_left
    dimension ::= [[:alnum:]]+
    operator ::= '==' | '!=' | '<' | '<=' | '>' | '>=' | '~=' | '~!=' |
        '~<' | '~<=' | '~>' | '~>='
    operator_left ::= 'is defined' | 'is not defined'
    values ::= value (',' value)*
    value ::= [[:alnum:]]+

Operator 'and' takes precedence over 'or' and rule evaluation is lazy - it stops immediately we know the final result.
Skipping expression - When dimension or outcome of the operation is not defined, expression is skipped over.


Dimension and values
~~~~~~~~~~~~~~~~~~~~~~

Each Dimension is a view on Context in which metadata can be adjusted.
It can be arch, distro, component, product, pipeline in which we run tests and so on.


Each value is treated as if it was a component with version. Name of the dimension doesn't matter, all are treated equally.
In some dimensions any operation than equality doesn't make sense but FMF won't forbid you to compare 'aarch64 > x86_64'. Alphabetical order is defined, you were warned.

As version separator one can use ':' or '.' or '-'.

Examples:
    centos-8.3.0
        name: centos
        version: 8, 3, 0
    python3-3.8.5-5.fc32
        name: python3
        version: 3, 8, 5, 5, fc32
    x86_64
        name: x86_64
        version: no version parts


Minor comparison operators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comparing distribution across their majors can be tricky. One cannot easily say that e.g. `centos-8.0 > centos-7.9`.
In this case centos-8.0 was released sooner than centos-7.9 so is it really newer?

To extend the example from motivation:
How would you correctly enable test only on centos versions where some feature is available if it was added in centos-8.2 and centos-7.9?

These operators ('~=' | '~!=' | '~<' | '~<=' | '~>' | '~>=') make possible to compare only within the same major.
If their major versions are different the outcome is not defined and as such it is skipped.

==========  ========== ==========
  <         centos-7.9 centos-8.2
centos-7.8   True         skip
centos-7.9   False        skip
centos-8.1   skip         True
centos-8.2   skip         False
==========  ========== ==========
