import unittest

import pytest

from fmf.plugins.pytest import TMT


@TMT.tag("Tier1")
@TMT.tier("0")
@TMT.summary("This is basic testcase")
def test_pass():
    assert True


def test_fail():
    assert True


@TMT.summary("Some summary")
@pytest.mark.skip
def test_skip():
    assert True


@pytest.mark.parametrize("test_input", ["a", "b", "c"])
def test_parametrize(test_input):
    assert bool(test_input)


class TestCls(unittest.TestCase):
    def test(self):
        self.assertTrue(True)
