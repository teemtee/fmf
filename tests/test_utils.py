# coding: utf-8

from __future__ import unicode_literals, absolute_import

import pytest
from fmf.utils import filter, FilterError


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
    assert(filter("tag: Tier1", data) == True)
    assert(filter("tag: -Tier2", data) == True)
    assert(filter("category: Sanity", data) == True)
    assert(filter("category: -Regression", data) == True)
    assert(filter("tag: Tier2", data) == False)
    assert(filter("tag: -Tier1", data) == False)
    assert(filter("category: Regression", data) == False)
    assert(filter("category: -Sanity", data) == False)

    # ORs and ANDs
    assert(filter("tag: Tier1 | tag: Tier2", data) == True)
    assert(filter("tag: -Tier1 | tag: -Tier2", data) == True)
    assert(filter("tag: Tier1 | tag: TIPpass", data) == True)
    assert(filter("tag: Tier1 | category: Regression", data) == True)
    assert(filter("tag: Tier1 & tag: TIPpass", data) == True)
    assert(filter("tag: Tier1 & category: Sanity", data) == True)
    assert(filter("tag: Tier2 | tag: Tier3", data) == False)
    assert(filter("tag: Tier1 & tag: Tier2", data) == False)
    assert(filter("tag: Tier2 & tag: Tier3", data) == False)
    assert(filter("tag: Tier1 & category: Regression", data) == False)
    assert(filter("tag: Tier2 | category: Regression", data) == False)

    # Syntactic sugar
    assert(filter("tag: Tier1, Tier2", data) == True)
    assert(filter("tag: Tier1, TIPpass", data) == True)
    assert(filter("tag: Tier1; TIPpass", data) == True)
    assert(filter("tag: -Tier2", data) == True)
    assert(filter("tag: -Tier1, -Tier2", data) == True)
    assert(filter("tag: -Tier1, -Tier2", data) == True)
    assert(filter("tag: -Tier1; -Tier2", data) == False)
    assert(filter("tag: Tier2, Tier3", data) == False)
    assert(filter("tag: Tier1; Tier2", data) == False)
    assert(filter("tag: Tier2; Tier3", data) == False)
    assert(filter("tag: Tier1; -TIPpass", data) == False)

    # Regular expressions
    assert(filter("tag: Tier.*", data, regexp=True) == True)
    assert(filter("tag: Tier[123]", data, regexp=True) == True)
    assert(filter("tag: NoTier.*", data, regexp=True) == False)
    assert(filter("tag: -Tier.*", data, regexp=True) == False)

    # Case insensitive
    assert(filter("tag: tier1", data, sensitive=False) == True)
    assert(filter("tag: tippass", data, sensitive=False) == True)

    # Unicode support
    assert(filter("tag: -ťip", data) == True)
    assert(filter("tag: ťip", data) == False)
    assert(filter("tag: ťip", {"tag": ["ťip"]}) == True)
    assert(filter("tag: -ťop", {"tag": ["ťip"]}) == True)
