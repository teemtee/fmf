.. _releases:

======================
    Releases
======================


fmf-1.5.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fmf :ref:`trees` can now be built from hidden files and
directories as well. Use a simple :ref:`config` file to specify
names which should be included in the search.


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
