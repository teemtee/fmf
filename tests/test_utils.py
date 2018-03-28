# coding: utf-8

from __future__ import unicode_literals, absolute_import

import pytest
from fmf.utils import filter, FilterError, FileError, TypeError
from fmf.base import Tree


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Filter
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def test_filter():
    """ Function filter() """
    data = {"tag": ["Tier1", "TIPpass"], "category": ["Sanity"]}
    # Invalid filter format
    with pytest.raises(FilterError):
        filter("x & y", data)
    with pytest.raises(FilterError):
        filter("status:proposed", data)
    # Basic stuff and negation
    filter("tag: Tier1", data) == True
    filter("tag: -Tier2", data) == True
    filter("category: Sanity", data) == True
    filter("category: -Regression", data) == True
    filter("tag: Tier2", data) == False
    filter("tag: -Tier1", data) == False
    filter("category: Regression", data) == False
    filter("category: -Sanity", data) == False
    # ORs and ANDs
    filter("tag: Tier1 | tag: Tier2", data) == True
    filter("tag: -Tier1 | tag: -Tier2", data) == True
    filter("tag: Tier1 | tag: TIPpass", data) == True
    filter("tag: Tier1 | category: Regression", data) == True
    filter("tag: Tier1 & tag: TIPpass", data) == True
    filter("tag: Tier1 & category: Sanity", data) == True
    filter("tag: Tier2 | tag: Tier3", data) == False
    filter("tag: Tier1 & tag: Tier2", data) == False
    filter("tag: Tier2 & tag: Tier3", data) == False
    filter("tag: Tier1 & category: Regression", data) == False
    filter("tag: Tier2 | category: Regression", data) == False
    # Syntactic sugar
    filter("tag: Tier1, Tier2", data) == True
    filter("tag: Tier1, TIPpass", data) == True
    filter("tag: Tier1; TIPpass", data) == True
    filter("tag: -Tier2", data) == True
    filter("tag: -Tier1, -Tier2", data) == True
    filter("tag: -Tier1, -Tier2", data) == True
    filter("tag: -Tier1; -Tier2", data) == False
    filter("tag: Tier2, Tier3", data) == False
    filter("tag: Tier1; Tier2", data) == False
    filter("tag: Tier2; Tier3", data) == False
    filter("tag: Tier1; -TIPpass", data) == False
    # Regular expressions
    filter("tag: Tier.*", data, regexp=True) == True
    filter("tag: Tier[123]", data, regexp=True) == True
    filter("tag: NoTier.*", data, regexp=True) == False
    filter("tag: -Tier.*", data, regexp=True) == False
    # Case insensitive
    filter("tag: tier1", data, sensitive=False) == True
    filter("tag: tippass", data, sensitive=False) == True
    # Unicode support
    filter("tag: -ťip", data) == True
    filter("tag: ťip", data) == False
    filter("tag: ťip", {"tag": ["ťip"]}) == True
    filter("tag: -ťop", {"tag": ["ťip"]}) == True


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Tree
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def test_tree():
    """ Class tree() """

    with pytest.raises(FileError):
        Tree("")

    tree = Tree("tests/")

    tree.update(None)
    assert(".hidden" not in tree.children)
    assert(".test" not in tree.children)

    data = tree.data
    assert(data["tag"] != "TIPpass")
    assert(data["tag"] == "Tier1")
    tree.update({"tag": ["Tier1", "TIPpass"], "time": 1, "desc": "Desc"})
    data = tree.data
    assert('TIPpass' in data['tag'])

    # adding to attributes using '+'
    tree.update({"tag+": ["test"], "time+": 2, "desc+": "some", "new+": "New"})
    data = tree.data
    assert("new+" not in data)
    assert (data["new"] == "New")
    assert("time+" not in data)
    assert (data["time"] != 1)
    assert (data["time"] == 3)
    assert("desc+" not in data)
    assert (data["desc"] != "Desc")
    assert (data["desc"] == "Descsome")
    assert("tag+" not in data)
    assert("Add" not in data["tag"])
    assert("Tier1" in data["tag"])
    with pytest.raises(TypeError):
        tree.update({"time+": "string"})

    # tree.get()
    isinstance(tree.get(), dict)
    assert(not isinstance(tree.get("time"), type("")))
    assert(isinstance(tree.get("time"), int))

    # tree.show()
    assert(not isinstance(tree.show(brief=True), dict))
    assert(isinstance(tree.show(brief=True), type("")))
    assert(not isinstance(tree.show(), dict))
    assert(isinstance(tree.show(), type("")))
