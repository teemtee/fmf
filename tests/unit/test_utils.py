# coding: utf-8

from __future__ import unicode_literals, absolute_import

import pytest
import fmf.utils as utils
from fmf.utils import filter, listed


class TestFilter(object):
    """ Function filter() """

    def setup_method(self, method):
        self.data = {"tag": ["Tier1", "TIPpass"], "category": "Sanity"}

    def test_invalid(self):
        """ Invalid filter format """
        with pytest.raises(utils.FilterError):
            filter("x & y", self.data)
        with pytest.raises(utils.FilterError):
            filter("status:proposed", self.data)
        with pytest.raises(utils.FilterError):
            filter("x: 1", None)

    def test_basic(self):
        """ Basic stuff and negation """
        assert(filter("tag: Tier1", self.data) == True)
        assert(filter("tag: -Tier2", self.data) == True)
        assert(filter("category: Sanity", self.data) == True)
        assert(filter("category: -Regression", self.data) == True)
        assert(filter("tag: Tier2", self.data) == False)
        assert(filter("tag: -Tier1", self.data) == False)
        assert(filter("category: Regression", self.data) == False)
        assert(filter("category: -Sanity", self.data) == False)

    def test_operators(self):
        """ Operators """
        assert(filter("tag: Tier1 | tag: Tier2", self.data) == True)
        assert(filter("tag: -Tier1 | tag: -Tier2", self.data) == True)
        assert(filter("tag: Tier1 | tag: TIPpass", self.data) == True)
        assert(filter("tag: Tier1 | category: Regression", self.data) == True)
        assert(filter("tag: Tier1 & tag: TIPpass", self.data) == True)
        assert(filter("tag: Tier1 & category: Sanity", self.data) == True)
        assert(filter("tag: Tier2 | tag: Tier3", self.data) == False)
        assert(filter("tag: Tier1 & tag: Tier2", self.data) == False)
        assert(filter("tag: Tier2 & tag: Tier3", self.data) == False)
        assert(filter("tag: Tier1 & category: Regression", self.data) == False)
        assert(filter("tag: Tier2 | category: Regression", self.data) == False)

    def test_sugar(self):
        """ Syntactic sugar """
        assert(filter("tag: Tier1, Tier2", self.data) == True)
        assert(filter("tag: Tier1, TIPpass", self.data) == True)
        assert(filter("tag: -Tier2", self.data) == True)
        assert(filter("tag: -Tier1, -Tier2", self.data) == True)
        assert(filter("tag: -Tier1, -Tier2", self.data) == True)
        assert(filter("tag: Tier2, Tier3", self.data) == False)

    def test_regexp(self):
        """ Regular expressions """
        assert(filter("tag: Tier.*", self.data, regexp=True) == True)
        assert(filter("tag: Tier[123]", self.data, regexp=True) == True)
        assert(filter("tag: NoTier.*", self.data, regexp=True) == False)
        assert(filter("tag: -Tier.*", self.data, regexp=True) == False)

    def test_case(self):
        """ Case insensitive """
        assert(filter("tag: tier1", self.data, sensitive=False) == True)
        assert(filter("tag: tippass", self.data, sensitive=False) == True)

    def test_unicode(self):
        """ Unicode support """
        assert(filter("tag: -ťip", self.data) == True)
        assert(filter("tag: ťip", self.data) == False)
        assert(filter("tag: ťip", {"tag": ["ťip"]}) == True)
        assert(filter("tag: -ťop", {"tag": ["ťip"]}) == True)


class TestPluralize(object):
    """ Function pluralize() """

    def test_basic(self):
        assert(utils.pluralize("cloud") == "clouds")
        assert(utils.pluralize("sky") == "skies")
        assert(utils.pluralize("boss") == "bosses")


class TestListed(object):
    """ Function listed() """

    def test_basic(self):
        assert(listed(range(1)) == '0')
        assert(listed(range(2)) == '0 and 1')

    def test_quoting(self):
        assert(listed(range(3), quote='"') == '"0", "1" and "2"')

    def test_max(self):
        assert(listed(range(4), max=3) == '0, 1, 2 and 1 more')
        assert(listed(range(5), 'number', max=2) == '0, 1 and 3 more numbers')

    def test_text(self):
        assert(listed(range(6), 'category') == '6 categories')
        assert(listed(7, "leaf", "leaves") == '7 leaves')
        assert(listed(0, "item") == "0 items")


class TestSplit(object):
    """ Function split() """

    def test_basic(self):
        assert(utils.split('a b c') == ['a', 'b', 'c'])
        assert(utils.split('a, b, c') == ['a', 'b', 'c'])
        assert(utils.split(['a, b', 'c']) == ['a', 'b', 'c'])


class TestLogging(object):
    """ Logging """

    def test_level(self):
        for level in [1, 4, 7, 10, 20, 30, 40]:
            utils.Logging('fmf').set(level)
            assert(utils.Logging('fmf').get() == level)

    def test_smoke(self):
        utils.Logging('fmf').set(utils.LOG_ALL)
        utils.info("something")
        utils.log.info("info")
        utils.log.debug("debug")
        utils.log.cache("cache")
        utils.log.data("data")
        utils.log.all("all")


class TestColoring(object):
    """ Coloring """

    def test_invalid(self):
        with pytest.raises(RuntimeError):
            utils.Coloring().set(3)

    def test_mode(self):
        for mode in range(3):
            utils.Coloring().set(mode)
            assert(utils.Coloring().get() == mode)

    def test_color(self):
        utils.Coloring().set()
        text = utils.color("text", "lightblue", enabled=True)


class TestCheckout_remote(object):
    """ Remote reference from fmf github """
    def test_get_remote_id(self):
        remote_id = {
            'url': 'https://github.com/psss/fmf.git',
            'ref': '0.10',
            'path': 'examples/deep',
        }

        destination = utils.checkout_remote(remote_id)
        assert utils.os.path.isfile(utils.os.path.join(destination, 'fmf.spec'))

        remote_id['url'] = 'BAH_'
        with pytest.raises(utils.GeneralError):
            utils.checkout_remote(remote_id)
