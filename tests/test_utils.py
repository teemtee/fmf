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
