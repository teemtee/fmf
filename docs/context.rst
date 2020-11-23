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
of the dimension doesn't matter, all are treated equally.

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

Left vs Right side of the expression

Value on the left always comes from dimension, it describes what is known
about the context and should be as specific as possible (this is up to the
calling tool). Value on the right comes from the rule and the creator of this
rule sets how precise they want to be.
When Left side is not specific enough its missing version parts are treated as
if they were lower than the right side. However Left side needs to contain at least
one version part.

Equality vs comparing order

It is always possible to evaluate whether two values are (not) equal.
When names and common version parts as requested by the right side match
then two values are equal.

However order between two values is defined only if they match by name.
If names don't match then values cannot be compared and expression is
skipped.


Comparing within same Major version

Comparing distribution across their major versions can be tricky.
One cannot easily say that e.g. ``centos-8.0 > centos-7.9``.
In this case ``centos-8.0`` was released sooner than
``centos-7.9`` so is it really newer?

To extend the example from motivation: How would you correctly
enable test only on centos versions where some feature is
available if it was added in centos-8.2 and centos-7.9?

Another usage of this operations is to check for features specific
to a major version or or module stream.

The following operators make it possible to compare only within
the same major::

    '~=' | '~!=' | '~<' | '~<=' | '~>' | '~>='

If their major versions are different then their minor versions cannot
be compared and as such are skipped during evaluation. The following
example shows how the special less than operator ``~<`` would be evaluated
for given `centos` versions. Note that Right side defines if minor comparison
is being evaluated or not.


==========  ========== ========== ==========
~<          centos-7.9 centos-8.2 centos-8
centos-7.8   True         skip    True
centos-7.9   False        skip    True
centos-7     skip         skip    True
centos-8.1   skip         True    False
centos-8.2   skip         False   False
centos-8     skip         skip    False
==========  ========== ========== ==========

More examples::

    centos < fedora ---> skip (cannot be decided)
    fedora < fedora ---> False
    fedora < fedora-33 ---> skip (left side has no version parts)
    foo-1 < foo-1.1 ---> True (missing version part on left is padded)
    fedora-33 < fedora ---> False (right side wants only name)
    fedora-33 == fedora ---> True (right side wants only name)
    fedora-33 ~= fedora ---> True (right side wants only name, no minor comparison requested)
    fedora < fedora-33 ---> True (missing version parts are lower)
    fedora ~< fedora-33 ---> skip (right side wants also major version to match)
    fedora-32 ~< fedora-33 ---> True
    centos-8.4.0 == centos ---> True
    centos-8.4.0 < centos-9 ---> True
    centos-8.4.0 ~< centos-9 ---> True (no minor comparison requested)
    centos-8.4.0 ~< centos-9.2 ---> skip (minor comparison requested)
    fedora-33 < fedora-rawhide ---> True (rawhide is newer then any number)
