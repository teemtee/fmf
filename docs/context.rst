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
    expression ::= 'true' | 'false'
    dimension ::= [[:alnum:]]+
    binary_operator ::= '==' | '!=' | '<' | '<=' | '>' | '>=' |
        '~=' | '~!=' | '~<' | '~<=' | '~>' | '~>='
    unary_operator ::= 'is defined' | 'is not defined'
    values ::= value (',' value)*
    value ::= [[:alnum:]]+

Let's demonstrate the syntax on a couple of real-life examples::

    # check distro, compare specific release
    distro == fedora
    distro >= fedora-33

    # use boolean operators to build more complex expressions
    distro == fedora and arch = x86_64
    distro >= fedora-33 or distro >= rhel-8

    # check whether a dimension is defined
    collection is not defined

    # disable adjust rule (e.g. during debugging / experimenting)
    false and <original rule>

    # always enabled adjust rule (same as if the `when` key is omitted)
    true

The comma operator can be used to shorten the ``or`` expressions::

    # the following two lines are equivalent
    arch == x86_64 or arch == ppc64
    arch == x86_64, ppc64

    # works for less/greater than comparison as well
    distro < fedora-33 or distro < rhel-8
    distro < fedora-33, rhel-8

.. warning::

    Do not use the comma operator with the ``!=`` comparison.
    It is currently implemented with the ``or`` logic which is a
    bit weird, confusing to the users and it will be most probably
    changed to ``and`` in the future so that it can be interpreted
    as "none of the values in the list is equal".


Lazy Evaluation
---------------

Operator ``and`` takes precedence over ``or`` and rule evaluation
is lazy. It stops immediately when we know the final result.

Boolean Operations
------------------

When a dimension or outcome of the operation is not defined,
the expression is treated as ``CannotDecide``.

Boolean operations with ``CannotDecide``::

    CannotDecide  and  True         ==  CannotDecide
    CannotDecide  and  False        ==  False
    CannotDecide  or   True         ==  True
    CannotDecide  or   False        ==  CannotDecide
    CannotDecide  and  CannotDecide ==  CannotDecide
    CannotDecide  or   CannotDecide ==  CannotDecide


Dimensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each Dimension is a view on the Context in which metadata can be
adjusted. For example it can be arch, distro, component, product
or pipeline in which we run tests and so on.

Values are always converted to a string representation. Each
value is treated as if it was a component with version. Name of
the dimension doesn't matter, all are treated equally.

Values are case-sensitive by default, which means that values like
``centos`` and ``CentOS`` are considered different. When calling
the ``adjust()`` method on the tree, ``case_sensitive=False`` can
be used to make the value comparison case insensitive.

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

Value on the left always comes from dimension, it describes what
is known about the context and should be as specific as possible
(this is up to the calling tool). Value on the right comes from
the rule and the creator of this rule sets how precise they want
to be.

When the left side is not specific enough its missing version
parts are treated as if they were lower than the right side.
However, the left side needs to contain at least one version
part::

    git-2.3.4 < git-3   # True
    git-2 < git-3.2.1   # True
    git < git-3.2.1     # CannotDecide


Equality vs Comparison
----------------------

It is always possible to evaluate whether two values are (not)
equal. When the name and common version parts requested by the
right side match then the two values are equal::

    git-2.3.4 == git-2.3.4
    git-2.3.4 == git-2.3
    git-2.3.4 == git-2
    git-2.3.4 == git
    git-2.3.4 != git-1
    git-2.3.4 != fmf

However, comparing order of two values is defined only if they
match by name. If names don't match then values cannot be
compared and the expression has ``CannotDecide`` outcome::

    git-2.3.4 >= git-2     # True
    git-2.3.4 >= git-3     # False
    git-2.3.4 >= fmf-2     # CannotDecide


Major Version
-------------

Comparing distributions across their major versions can be tricky.
One cannot easily say that e.g. ``centos-8.0 > centos-7.9``. In
this case ``centos-8.0`` was released sooner than ``centos-7.9``
so is it really newer?

Quite often new features are implemented in given minor version
such as ``centos-7.9`` or ``centos-8.2`` which does not mean they
are available in ``centos-8.1`` so it is not possible to apply a
single rule such as ``distro >= centos-7.9`` to cover this case.

Another usage for this operators is to check for features specific
to a particular major version or a module stream.

The following operators make it possible to compare only within
the same major version::

    '~=' | '~!=' | '~<' | '~<=' | '~>' | '~>='

If their major versions are different then their minor versions
cannot be compared and as such are skipped during evaluation. The
following example shows how the special less than operator ``~<``
would be evaluated for given `centos` versions. Note that the
right side defines if the minor comparison is evaluated or not.

==========  ============ ============ ==========
~<          centos-7.9   centos-8.2   centos-8
centos-7.8  True         CannotDecide True
centos-7.9  False        CannotDecide True
centos-7    CannotDecide CannotDecide True
centos-8.1  CannotDecide True         False
centos-8.2  CannotDecide False        False
centos-8    CannotDecide CannotDecide False
==========  ============ ============ ==========

Here is a couple of examples to get a better idea of how the
comparison works for some special cases::

    fedora < fedora-33 ---> cannot (left side has no version parts)
    fedora-33 == fedora ---> True (right side wants only name)
    fedora-33 < fedora-rawhide ---> True (rawhide is newer than any number)

    centos-8.4.0 == centos ---> True
    centos-8.4.0 < centos-9 ---> True
    centos-8.4.0 ~< centos-9 ---> True (no minor comparison requested)
    centos-8.4.0 ~< centos-9.2 ---> cannot (minor comparison requested)
