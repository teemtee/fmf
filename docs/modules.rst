
===============
    Modules
===============

.. _sort:

Sort
----

By default, when exploring test metadata in the tree, child nodes
are sorted alphabetically by node name. This applies to command
line usage such as ``fmf ls`` or ``fmf show`` as well as for the
:py:meth:`fmf.Tree.climb()` and :py:meth:`fmf.Tree.prune()`
methods.

If the tree content is not created from files on disk but created
manually using the :py:meth:`fmf.Tree.child()` method, the child
order can be preserved by providing the ``sort=False`` parameter
to the :py:meth:`fmf.Tree.climb()` and :py:meth:`fmf.Tree.prune()`
methods.

.. versionadded:: 1.6


fmf
---

.. automodule:: fmf
    :members:
    :undoc-members:

base
----

.. automodule:: fmf.base
    :members:
    :undoc-members:

utils
-----

.. automodule:: fmf.utils
    :members:
    :undoc-members:

cli
---

.. automodule:: fmf.cli
    :members:
    :undoc-members:
