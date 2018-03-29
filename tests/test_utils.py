# coding: utf-8

from __future__ import unicode_literals, absolute_import

import os
import pytest
from fmf.utils import filter, FilterError, FileError, MergeError
from fmf.base import Tree


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../examples/wget"
MERGE = PATH + "/../examples/merge"


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

    # No directory path given
    with pytest.raises(FileError):
        Tree("")

    # Load examples
    wget = Tree(WGET)
    merge = Tree(MERGE)

    # Hidden files and directories should be ignored
    assert(".hidden" not in wget.children)

    # Check inheritance and data types on the wget/recursion/deep object
    deep = [node for node in wget.climb() if 'deep' in node.name][0]
    assert(deep.data['depth'] == 1000)
    assert(deep.data['description'] == 'Check recursive download options')
    assert(deep.data['tags'] == ['Tier2'])

    # Check attribute adding
    child = [node for node in merge.climb() if 'child' in node.name][0]
    assert('General' in child.data['description'])
    assert('Specific' in child.data['description'])
    assert(child.data['tags'] == ['Tier1', 'Tier2'])
    assert(child.data['time'] == 15)
    assert('time+' not in child.data)
    with pytest.raises(MergeError):
        child.update({"time+": "string"})

    # Tree.get()
    assert(isinstance(wget.get(), dict))
    assert('Petr' in wget.get('tester'))

    # Tree.show()
    assert(isinstance(wget.show(brief=True), type("")))
    assert(isinstance(wget.show(), type("")))
    assert('wget' in wget.show())
