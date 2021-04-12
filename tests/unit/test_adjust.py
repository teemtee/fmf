# coding: utf-8

from __future__ import unicode_literals, absolute_import

import copy
import pytest
import yaml

import fmf
from fmf.context import Context, CannotDecide
from fmf.utils import GeneralError, FormatError


@pytest.fixture
def fedora():
    """ Fedora 33 on x86_64 and ppc64 """
    return Context(distro="fedora-33", arch=["x86_64", "ppc64"])


@pytest.fixture
def centos():
    """ CentOS 8.4 """
    return Context(distro="centos-8.4")


@pytest.fixture
def mini():
    """ Simple tree node with minimum set of attributes """
    data = """
        enabled: true
        adjust:
            enabled: false
            when: distro = centos
        """
    return fmf.Tree(yaml.safe_load(data))


@pytest.fixture
def full():
    """ More complex metadata structure with inheritance """
    data = """
        duration: 5m
        enabled: true
        require: [one]
        adjust:
          - enabled: false
            when: distro = centos
            because: the feature is not there yet
            continue: false
          - duration: 1m
            when: arch = ppc64
            because: they are super fast
            continue: true
          - require+: [two]
            when: distro = fedora

        /inherit:
            summary: This test just inherits all rules.

        /define:
            summary: This test defines its own rules.
            adjust:
                recommend: custom-package
                when: distro = fedora

        /extend:
            summary: This test extends parent rules.
            adjust+:
              - require+: [three]
                when: distro = fedora
        """
    return fmf.Tree(yaml.safe_load(data))


class TestInvalid(object):
    """ Ensure that invalid input is correctly handled """

    def test_invalid_context(self, mini):
        with pytest.raises(GeneralError, match="Invalid adjust context"):
            mini.adjust(context="weird")

    def test_invalid_rules(self, mini, fedora):
        with pytest.raises(FormatError, match="Invalid adjust rule format"):
            mini.data["adjust"] = "weird"
            mini.adjust(fedora)

    def test_invalid_rule(self, mini, fedora):
        with pytest.raises(FormatError, match="should be a dictionary"):
            mini.data["adjust"] = ["weird"]
            mini.adjust(fedora)

    def test_invalid_continue(self, mini, fedora):
        with pytest.raises(FormatError, match="should be bool"):
            mini.data["adjust"]["continue"] = "weird"
            mini.adjust(fedora)

    def test_missing_condition(self, mini, fedora):
        with pytest.raises(FormatError, match="No condition defined"):
            mini.data["adjust"] = dict(key="value")
            mini.adjust(fedora)

    def test_undecided_invalid(self, mini, fedora):
        mini.data["adjust"] = dict(when="component = bash", enabled=False)
        with pytest.raises(GeneralError, match="Invalid value.*undecided"):
            mini.adjust(fedora, undecided="weird")


class TestSpecial(object):
    """ Check various special cases """

    def test_single_rule(self, mini, fedora):
        mini.adjust(fedora)

    def test_no_rule(self, mini, fedora):
        mini.data.pop("adjust")
        mini.adjust(fedora)
        assert mini.get() == dict(enabled=True)


class TestAdjust(object):
    """ Verify adjusting works as expected """

    def test_original(self, mini):
        assert mini.get("enabled") is True

    def test_adjusted(self, mini, centos):
        mini.adjust(centos)
        assert mini.get("enabled") is False

    def test_keep_original_adjust_rules(self, mini, centos):
        original_adjust = copy.deepcopy(mini.get("adjust"))
        mini.adjust(centos)
        assert mini.get("adjust") == original_adjust

    def test_skipped(self, mini, fedora):
        mini.adjust(fedora)
        assert mini.get("enabled") is True

    def test_undecided_skip(self, mini, fedora):
        mini.data["adjust"] = dict(when="component = bash", enabled=False)
        mini.adjust(fedora)
        assert mini.get("enabled") is True

    def test_undecided_raise(self, mini, fedora):
        mini.data["adjust"] = dict(when="component = bash", enabled=False)
        with pytest.raises(CannotDecide):
            mini.adjust(fedora, undecided="raise")

    def test_inherit_fedora(self, full, fedora):
        full.adjust(fedora)
        inherit = full.find("/inherit")
        assert inherit.get("enabled") == True
        assert inherit.get("duration") == "1m"
        assert inherit.get("require") == ["one", "two"]

    def test_inherit_fedora_x86_64(self, full):
        fedora = Context(distro="fedora-33", arch="x86_64")
        full.adjust(fedora)
        inherit = full.find("/inherit")
        assert inherit.get("enabled") == True
        assert inherit.get("duration") == "5m"
        assert inherit.get("require") == ["one", "two"]

    def test_inherit_centos(self, full, centos):
        full.adjust(centos)
        inherit = full.find("/inherit")
        assert inherit.get("enabled") == False
        assert inherit.get("duration") == "5m"
        assert inherit.get("require") == ["one"]

    def test_define_fedora(self, full, fedora):
        full.adjust(fedora)
        define = full.find("/define")
        assert define.get("enabled") == True
        assert define.get("duration") == "5m"
        assert define.get("require") == ["one"]
        assert define.get("recommend") == "custom-package"

    def test_define_centos(self, full, centos):
        full.adjust(centos)
        define = full.find("/define")
        assert define.get("enabled") == True
        assert define.get("duration") == "5m"
        assert define.get("require") == ["one"]
        assert "recommend" not in define.get()

    def test_extend_fedora(self, full, fedora):
        full.adjust(fedora)
        extend = full.find("/extend")
        assert extend.get("enabled") == True
        assert extend.get("duration") == "1m"
        assert extend.get("require") == ["one", "two", "three"]
        assert "recommend" not in extend.get()

    def test_extend_centos(self, full, centos):
        full.adjust(centos)
        extend = full.find("/extend")
        assert extend.get("enabled") == False
        assert extend.get("duration") == "5m"
        assert extend.get("require") == ["one"]
        assert "recommend" not in extend.get()

    def test_continue_default(self, full, fedora):
        """ The continue key should default to True """
        full.adjust(fedora)
        extend = full.find("/extend")
        assert extend.get("require") == ["one", "two", "three"]
