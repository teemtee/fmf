.. _context:

======================
    Context
======================

Motivation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Imagine you have a test which can run only for Fedora 33 and
newer. Or your tests' require depend on which distribution you
are running. For these cases you need just a slight tweak to your
metadata but you can't really use the :ref:`virtual` cases as only
one of them should run.

This is exactly where adjusting metadata based on the given
Context will help you. Let's see some examples to demonstrate the
usage on a real-life use case.

Disable test by setting the ``enabled`` attribute::

    enabled: true
    adjust:
        enabled: false
        when: distro < fedora-33
        because: The feature was added in Fedora-33

Tweak the ``require`` attribute for an older distro::

    require:
      - procps-ng
    adjust:
        require: procps
        when: distro ~= centos-6


Syntax
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To get a better idea of the ``when`` condition syntax including
supported operators consult the following grammar outline::

    condition ::= expression (bool expression)*
    bool ::= and | or
    expression ::= dimension binary_operator values
    expression ::= dimension unary_operator
    dimension ::= [[:alnum:]]+
    binary_operator ::= '==' | '!=' | '<' | '<=' | '>' | '>=' |
        '~=' | '~!=' | '~<' | '~<=' | '~>' | '~>='
    unary_operator ::= 'is defined' | 'is not defined'
    values ::= value (',' value)*
    value ::= [[:alnum:]]+

Lazy evaluation
    Operator ``and`` takes precedence over ``or`` and rule
    evaluation is lazy. It stops immediately when we know the
    final result.

Expression skipping
    When a dimension or outcome of the operation is not defined,
    the expression is skipped over.


Dimensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each Dimension is a view on the Context in which metadata can be
adjusted. For example it can be arch, distro, component, product
or pipeline in which we run tests and so on.

Each value is treated as if it was a component with version. Name
of the dimension doesn't matter, all are treated equally. For some
dimensions, such as ``arch``,  only comparison for equality makes
sense. Note that the implementation does not raise an error when
comparing ``aarch64 > x86_64``. In this case the alphabetical
order is defined, you were warned.

The characters ``:`` or ``.`` or ``-`` are used as version
separators and are handled in the same way. The following examples
demonstrate how the ``name`` and ``version`` parts are parsed::

    centos-8.3.0
        name: centos
        version: 8, 3, 0

    python3-3.8.5-5.fc32
        name: python3
        version: 3, 8, 5, 5, fc32

    x86_64
        name: x86_64
        version: no version parts


Comparison
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comparing distribution across their major versions can be tricky.
One cannot easily say that e.g. ``centos-8.0 > centos-7.9``.
In this case ``centos-8.0`` was released sooner than
``centos-7.9`` so is it really newer?

To extend the example from motivation: How would you correctly
enable test only on centos versions where some feature is
available if it was added in centos-8.2 and centos-7.9?

The following operators make it possible to compare only within
the same major::

    '~=' | '~!=' | '~<' | '~<=' | '~>' | '~>='

If their major versions are different the outcome is not defined
and as such it is skipped during evaluation. The following example
shows how the special less than operator ``~<`` would be evaluated
for given `centos` versions:

==========  ========== ==========
~<          centos-7.9 centos-8.2
centos-7.8   True         skip
centos-7.9   False        skip
centos-8.1   skip         True
centos-8.2   skip         False
==========  ========== ==========
