.. _releases:

======================
    Releases
======================


fmf-1.7.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:ref:`context` dimension names can now contain dash characters as
well so that multi-word names such as ``deployment-mode`` can be
used.

The merge suffix, for example ``+`` in the ``environment+`` key,
is now correctly stripped from the nodes defined in the root of
the tree as well.

A new callback ``additional_rules_callback`` can now be provided
to the :py:meth:`fmf.Tree.adjust` method and affect which nodes
should be adjusted using the ``additional_rules``.


fmf-1.6.1
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to allow adjust rules to merge dictionaries, nested
dictionaries need to keep the suffix in their name. This behavior
reverts to fmf-1.4.0 and is now documented in :ref:`merging<merging>`
section.


fmf-1.6.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to search :ref:`context` dimension values using regular
expressions, it is now possible to use operator ``~`` for matching
patterns and operator ``!~`` for non matching patterns.

When exploring trees using the :py:meth:`fmf.Tree.climb()` and
:py:meth:`fmf.Tree.prune()` methods, optional parameter ``sort``
can be used to preserve the original order in which child nodes
where inserted into the tree. See the :ref:`sort` section for more
details.


fmf-1.5.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fmf :ref:`trees` can now be built from hidden files and
directories as well. Use a simple :ref:`config` file to specify
names which should be included in the search.

The ``+`` operator now can be used for merging ``list`` of
dictionaries with a single ``dict``. This can be for example
useful when extending the ``discover`` step config which defines
several phases:

.. code-block:: yaml

    discover:
      - how: fmf
        url: https://github.com/project/one
      - how: fmf
        url: https://github.com/project/two

    /tier1:
        summary: Run tier one tests
        discover+:
            filter: "tier:1"

    /tier2:
        summary: Run tier two tests
        discover+:
            filter: "tier:2"

See the :ref:`merging<merging>` section for more details and
examples.

The ``-`` operator no longer raises exception when the key is not
defined by the parent node. This allows reducing values even for
cases where user does not have write permissions for the parent
data. For example, in order to make sure that the ``mysql``
package is not included in the list of required or recommended
packages, you can now safely use this:

.. code-block:: yaml

    discover:
        how: fmf
        adjust-tests:
          - require-: [mysql]
          - recommend-: [mysql]

When merging inherited values from parent, merge operations are
now performed in the exact order in which user specified them, the
keys are no longer sorted before the merging step.


fmf-1.4.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

New :ref:`merging<merging>` suffixes ``~`` and ``-~`` can be used
to **modify or remove data based on regular expressions**. For
example, renaming all required packages can be done easily in this
way::

    require~: /python2-/python3-/

The :py:func:`fmf.filter()` function now supports **searching by
node name**. Just specify the desired name instead of the ``key:
value`` pair. For example, to search for all tests with the name
starting with ``/test/core`` and tag ``quick`` you can do::

    /tests/core/.* & tag: quick

It is now possible to **escape boolean operators** ``|`` and ``&``
as well. This allows to use more complex regular expressions like
this::

    tag: Tier(1\|2\|3)

The new :ref:`select<select>` directive can be used to **include
branch nodes or skip leaf nodes** when searching the tree using
the :py:meth:`fmf.Tree.climb` method.

The :py:meth:`fmf.Tree.adjust` method now supports new parameter
``additional_rules`` for providing **additional adjust rules**
which are applied after the rules detected in the node itself.
