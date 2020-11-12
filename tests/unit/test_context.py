# coding: utf-8

from __future__ import unicode_literals, absolute_import
import pytest

from fmf.context import Context, ContextValue
from fmf.context import InvalidRule, CannotDecide, InvalidContext


@pytest.fixture
def env_centos():
    return Context(
        arch="x86_64",
        distro="centos-8.4.0",
        component=["bash-5.0.17-1.fc32", "python3-3.8.5-5.fc32"],
        )


class TestExample(object):
    """ Examples of possible conditions """

    def test_simple_conditions(self, env_centos):
        """ Rules with single condition """

        # "Version" comparison if possible
        assert env_centos.matches("distro = centos")
        assert not env_centos.matches("distro = fedora")
        assert env_centos.matches("distro = centos,fedora")
        assert env_centos.matches("distro = centos-8")
        assert env_centos.matches("distro = centos-8.4")
        assert env_centos.matches("distro > centos-8.3")
        assert env_centos.matches("distro < centos-9")

        # Major/minor operator prefix '~' so it is
        # False if not comparable (when 'major' differs)
        with pytest.raises(CannotDecide):
            env_centos.matches("distro ~< centos-9")
        with pytest.raises(CannotDecide):
            env_centos.matches("distro ~>= centos-9")
        # Same major, can be compared
        assert env_centos.matches("distro ~>= centos-8.2")
        assert env_centos.matches("distro ~< centos-8.5")

        # Presence of a dimension
        assert env_centos.matches("fips !defined")
        assert not env_centos.matches("fips defined")

        # Operator 'contains' is not necessary anymore
        assert env_centos.matches("component = bash")
        assert env_centos.matches("component = bash, ksh")
        assert not env_centos.matches("component = csh, ksh")

    def test_multi_condition(self, env_centos):
        """ Rules with multiple conditions """
        assert env_centos.matches(
            "arch=x86_64 && distro != fedora")
        assert env_centos.matches(
            "distro = fedora && component >= bash-5.0 || "
            "distro = centos && component >= bash-4.9")
        assert not env_centos.matches(
            "distro = fedora && component >= bash-5.0 || "
            "distro = rhel && component >= bash-4.9")

    def test_minor_comparison_mode(self):
        """ How it minor comparison should work """
        fedora = Context(distro="fedora-33")
        centos = Context(distro="centos-7.3.0")
        centos6 = Context(distro="centos-6.9.0")

        # Simple version compare is not enough
        # Think about feature add in centos-7.4.0 and centos-6.9.0
        # so for 'centos' Context we want matches() == False
        # but for 'centos6' we want matches() == True
        rule = "distro >= centos-7.4.0"
        assert not centos.matches(rule)  # good
        assert not centos6.matches(rule)  # wrong for us

        rule = "distro >= centos-6.9.0"
        assert centos.matches(rule)  # wrong for us
        assert centos6.matches(rule)  # good for us

        assert centos.matches(
            "distro >= centos-7.4.0 || distro >= centos-6.9.0"
        )  # wrong for us
        assert not centos.matches(
            "distro >= centos-7.4.0 && distro >= centos-6.9.0"
        )  # wrong for us
        assert centos6.matches(
            "distro >= centos-7.4.0 || distro >= centos-6.9.0"
        )  # good
        assert not centos6.matches(
            "distro >= centos-7.4.0 && distro >= centos-6.9.0"
        )  # good

        # Here comes minor compare into the play as it skip incomparable majors
        assert not centos.matches(
            "distro ~>= centos-7.4.0 || distro ~>= centos-6.9.0"
        )  # good
        assert not centos.matches(
            "distro ~>= centos-7.4.0 && distro ~>= centos-6.9.0"
        )  # good
        assert centos6.matches(
            "distro ~>= centos-7.4.0 || distro ~>= centos-6.9.0"
        )  # good
        assert centos6.matches(
            "distro ~>= centos-7.4.0 && distro ~>= centos-6.9.0"
        )  # good


class TestContextValue(object):
    impossible_split = ["x86_64", "ppc64", "fips", "errata"]
    splittable = [
        ("centos-8.3.0", ("centos", "8", "3", "0")),
        ("python3-3.8.5-5.fc32", ("python3", "3", "8", "5", "5", "fc32")),
    ]

    def test_simple_names(self):
        """ Values with simple name """
        for name in self.impossible_split:
            assert ContextValue(name)._to_compare == tuple([name])
        for name, _ in self.splittable:
            assert ContextValue([name])._to_compare == tuple([name])

    def test_split_to_version(self):
        """ Possible/impossible splitting to version"""
        for name in self.impossible_split:
            assert ContextValue._split_to_version(name) == tuple([name])
        for name, expected in self.splittable:
            assert ContextValue._split_to_version(name) == (expected)

    def test_eq(self):
        assert ContextValue("name") == ContextValue("name")
        assert ContextValue("name1-2-3") == ContextValue("name1-2-3")
        assert ContextValue("name1-2-3") != ContextValue("name1-2-4")
        assert ContextValue("foo") != ContextValue("bar")
        assert ContextValue("value-123") == ContextValue(["value", "123"])

    def test_version_cmp(self):
        first = ContextValue("name")
        assert first.version_cmp(ContextValue("name")) == 0
        assert first.version_cmp(ContextValue("name"), minor_mode=True) == 0
        assert first.version_cmp(ContextValue("name-1")) == 0
        assert first.version_cmp(ContextValue("name-1"), minor_mode=True) == 0
        assert first.version_cmp(ContextValue("name-1-2")) == 0
        # Name X name-1-2 has no major nor minor on the left side
        assert (
            first.version_cmp(ContextValue("name-1-2"), minor_mode=True) == 0)

        second = ContextValue("name-1-2-3")
        assert second.version_cmp(ContextValue("name")) == 0
        assert second.version_cmp(ContextValue("name"), minor_mode=True) == 0
        assert second.version_cmp(ContextValue("name-1")) == 0
        assert (
            second.version_cmp(ContextValue("name-1"), minor_mode=True) == 0)
        # Same minor
        assert second.version_cmp(ContextValue("name-1-2")) == 0
        assert (
            second.version_cmp(ContextValue("name-1-2"), minor_mode=True) == 0)

        third = ContextValue("name-1-2-3")
        assert third.version_cmp(ContextValue("aaa")) > 0
        assert third.version_cmp(ContextValue("zzz")) < 0
        with pytest.raises(CannotDecide):
            third.version_cmp(ContextValue("aaa"), minor_mode=True)

        # Minor mode should care only about minor, aka Y presence
        # so name-1 vs name-2 is defined, but name-1-1 vs name-2-1 is not
        fourth = ContextValue("name-2")
        assert fourth.version_cmp(ContextValue("name-2")) == 0
        assert fourth.version_cmp(ContextValue("name-2"), minor_mode=True) == 0
        assert fourth.version_cmp(ContextValue("name-3")) < 0
        assert fourth.version_cmp(ContextValue("name-3"), minor_mode=True) < 0
        assert fourth.version_cmp(ContextValue("name-1")) > 0
        assert fourth.version_cmp(ContextValue("name-1"), minor_mode=True) > 0
        with pytest.raises(CannotDecide):
            assert fourth.version_cmp(
                ContextValue("name-1-1"), minor_mode=True)

        fifth = ContextValue("name-2-1")
        for undecidable in ["name-1", "name-1-1", ""]:
            with pytest.raises(CannotDecide):
                fifth.version_cmp(ContextValue(undecidable), minor_mode=True)

        # More error states
        with pytest.raises(CannotDecide):
            first.version_cmp(Context()) # different object classes

        sixth = ContextValue([])
        with pytest.raises(CannotDecide):
            sixth.version_cmp(first, minor_mode=True)
        with pytest.raises(CannotDecide):
            sixth.version_cmp(first)
        assert sixth != Context()

    def test_version_cmp_fedora(self):
        """ Fedora comparison """
        f33 = ContextValue("fedora-33")
        frawhide = ContextValue("fedora-rawhide")

        assert f33.version_cmp(ContextValue("fedora-33")) == 0
        assert f33.version_cmp(ContextValue("fedora-13")) > 0
        assert f33.version_cmp(ContextValue("fedora-43")) < 0

        assert frawhide.version_cmp(ContextValue("fedora-rawhide")) == 0
        assert frawhide.version_cmp(f33) > 0
        assert f33.version_cmp(frawhide) < 0

    def test_prints(self):
        f33 = ContextValue("fedora-33")
        str(f33)
        repr(f33)


class TestParser(object):
    # Missing expression
    rule_groups_invalid = ["foo<bar && ", "foo<bar && defined bar || "]

    invalid_expressions = [
        "bar",
        "bar |",
        "bar ||",
        "& baz",
        "&& baz",
        "dim !! value",
        "defined dim",  # should be different order
        ]

    def test_split_rule_to_groups(self):
        """ Split to lists """
        for invalid_rule in self.rule_groups_invalid:
            with pytest.raises(InvalidRule):
                Context.split_rule_to_groups(invalid_rule)

        # Valid wrt to group splitter
        assert Context.split_rule_to_groups("bar") == [["bar"]]
        assert Context.split_rule_to_groups(" bar   ") == [["bar"]]
        assert Context.split_rule_to_groups("foo = bar") == [["foo = bar"]]
        assert Context.split_rule_to_groups(
            "foo = bar && baz") == [["foo = bar", "baz"]]
        assert Context.split_rule_to_groups(
            "foo = bar && defined baz || !defined foo") == [
                ["foo = bar", "defined baz"],
                ["!defined foo"],
                ]
        assert Context.split_rule_to_groups("a ~= b || c>d || defined x") == [
            ["a ~= b"],
            ["c>d"],
            ["defined x"],
            ]

    def test_split_expression(self):
        """ Split to dimension/operand/value tuple """
        for invalid in self.invalid_expressions:
            with pytest.raises(InvalidRule):
                Context.split_expression(invalid)
        assert Context.split_expression("dim defined") == (
            "dim", "defined", None)
        assert Context.split_expression("dim !defined") == (
            "dim", "!defined", None)
        assert Context.split_expression("dim < value") == (
            "dim", "<", ["value"])
        assert Context.split_expression("dim < value-123") == (
            "dim", "<", ["value-123"])
        assert Context.split_expression("dim<value") == (
            "dim", "<", ["value"])
        assert Context.split_expression("dim < value,second") == (
            "dim", "<", ["value", "second"])
        assert Context.split_expression("dim < value , second") == (
            "dim", "<", ["value", "second"])

    def test_parse_rule(self):
        """ Rule parsing """
        for invalid in self.rule_groups_invalid + self.invalid_expressions:
            with pytest.raises(InvalidRule):
                Context.parse_rule(invalid)

        assert Context.parse_rule("dim defined") == [
            [("dim", "defined", None)]]
        assert Context.parse_rule("dim < value") == [
            [("dim", "<", [ContextValue("value")])]]
        assert Context.parse_rule("dim < value-123") == [
            [("dim", "<", [ContextValue("value-123")])]]
        assert Context.parse_rule("dim ~< value, second") == [
            [("dim", "~<", [ContextValue("value"), ContextValue("second")])]]
        assert Context.parse_rule(
            "dim < value && dim > valueB || dim != valueC") == [
            [
                ("dim", "<", [ContextValue("value")]),
                ("dim", ">", [ContextValue("valueB")])],
            [
                ("dim", "!=", [ContextValue("valueC")])]]


class TestContext(object):
    def test_creation(self):
        for created in [
                Context(dim_a="value", dim_b=["val"], dim_c=["foo", "bar"]),
                Context("dim_a=value && dim_b=val && dim_c == foo,bar")]:
            assert created._dimensions["dim_a"] == set([ContextValue("value")])
            assert created._dimensions["dim_b"] == set([ContextValue("val")])
            assert created._dimensions["dim_c"] == set(
                [ContextValue("foo"), ContextValue("bar")])
        # Invalid ways to create Context
        with pytest.raises(InvalidContext):
            Context("a=b", "c=d") # Just argument
        with pytest.raises(InvalidContext):
            Context("a=b || c=d") # Can't use OR
        with pytest.raises(InvalidContext):
            Context("a < d") # Operator other than =/==

    def test_prints(self):
        c = Context()
        str(c)
        repr(c)

    context = Context(
        # nvr like single
        distro="fedora-32",
        # raw name  single
        pipeline="ci",
        # raw name list
        arch=["x86_64", "ppc64le"],
        # nvr like list
        components=["bash-5.0.17-1.fc32", "curl-7.69.1-6.fc32"],
        )

    def test_matches_groups(self):
        """ and/or in rules with yes/no/cannotdecide outcome """
        context = Context(distro="centos-8.2.0")

        # Clear outcome
        assert context.matches("distro = centos-8.2.0 || distro = fedora")
        assert context.matches("distro = fedora || distro = centos-8.2.0")
        assert not context.matches("distro != centos-8.2.0 || distro = fedora")
        assert context.matches("distro = centos-8 && distro = centos-8.2")
        assert not context.matches("distro = centos-8 && distro = centos-8.6")

        # Some operands cannot be decided
        assert context.matches("distro = centos-8.2.0 || foo=bar")
        assert context.matches("foo=bar || distro = centos-8.2.0")
        assert context.matches(
            "foo=bar && distro = centos-8.2.0"
        )  # skip over 'foo' part since it is not defined
        assert not context.matches("foo=bar && distro = rhel")
        assert not context.matches("foo=bar || distro = centos-8.9.0")

        # Whole rule cannot be decided
        for undecidable in [
            "foo = baz",
            "foo = baz && distro ~= fedora-32",  # both are CannotDecide
            "foo = baz && distro ~= fedora-32 || do=done",
        ]:
            with pytest.raises(CannotDecide):
                context.matches(undecidable)

    def test_matches(self):
        """ yes/no/skip test per operand for matches """

        context = Context(
            distro="fedora-32",
            arch=["x86_64", "ppc64le"],
            component="bash-5.0.17-1.fc32",
            )

        # defined
        assert context.matches("distro defined")
        assert not context.matches("FOOBAR defined")
        # skip not possible for this operand

        # !defined
        assert context.matches("FOOBAR !defined")
        assert not context.matches("distro !defined")
        # skip not possible for this operand

        # ==
        assert context.matches("distro == fedora-32")
        assert not context.matches("distro == centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product == fedora-32")

        # !=
        assert not context.matches("distro != fedora-32")
        assert context.matches("distro != centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product != fedora-32")

        # ~= aka major/minor mode
        assert context.matches("distro ~= fedora")
        context.matches("distro ~= fedora-45")
        with pytest.raises(CannotDecide):  # fedora is not centos
            context.matches("distro ~= centos-8")
        with pytest.raises(CannotDecide):  # dimension product is not defined
            context.matches("product ~= fedora-32")

        # '<'
        assert context.matches("distro < fedora-33")
        assert not context.matches("distro < fedora-32")
        with pytest.raises(CannotDecide):
            context.matches("product < centos-8")

        # '~<':
        assert context.matches("distro ~< fedora-33")
        with pytest.raises(CannotDecide):
            context.matches("distro ~< centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~< centos-8")

        # '<=':
        assert context.matches("distro <= fedora-32")
        assert not context.matches("distro <= fedora-30")
        with pytest.raises(CannotDecide):
            context.matches("product <= centos-8")

        # '~<='
        assert context.matches("distro ~<= fedora-33")
        with pytest.raises(CannotDecide):
            context.matches("distro ~<= centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~<= centos-8")

        # '~!=':
        assert context.matches("distro ~!= fedora-33")
        assert not context.matches("distro ~!= fedora-32")
        with pytest.raises(CannotDecide):
            context.matches("distro ~!= centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~!= centos-8")

        # '>=':
        assert context.matches("distro >= fedora-32")
        assert not context.matches("distro >= fedora-40")
        with pytest.raises(CannotDecide):
            context.matches("product >= centos-8")

        # '~>=':
        assert context.matches("distro ~>= fedora-32")
        assert not context.matches("distro ~>= fedora-33")
        with pytest.raises(CannotDecide):
            context.matches("distro ~>= centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~>= centos-8")

        # '>':
        assert context.matches("distro > fedora-30")
        assert not context.matches("distro > fedora-40")
        with pytest.raises(CannotDecide):
            context.matches("product > centos-8")

        # '~>':
        assert context.matches("distro ~> fedora-30")
        assert not context.matches("distro ~> fedora-42")
        with pytest.raises(CannotDecide):
            context.matches("distro ~> centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~> centos-8")


class TestOperands(object):
    """ more thorough testing for operations """

    context = Context(
        # nvr like single
        distro="fedora-32",
        # raw name  single
        pipeline="ci",
        # raw name list
        arch=["x86_64", "ppc64le"],
        # nvr like list
        components=["bash-5.0.17-1.fc32", "curl-7.69.1-6.fc32"],
        )

    # defined/!defined is too simple and covered by test_matches

    def test_equal(self):
        assert self.context.matches("distro=fedora-32")
        # One of them matches
        assert self.context.matches("distro=fedora-32,centos-8")
        assert not self.context.matches("distro=fedora-3")
        # Version-like comparison
        assert self.context.matches("distro=fedora")

        assert self.context.matches("pipeline=ci")
        # One of them matches
        assert self.context.matches("pipeline=ci,devnull")
        assert not self.context.matches("pipeline=devnull")

        assert self.context.matches("arch=x86_64")
        # One of them matches
        assert self.context.matches("arch=x86_64,aarch64")
        assert not self.context.matches("arch=aarch64")
        assert not self.context.matches("arch=aarch64,s390x")

    def test_not_equal(self):
        assert not self.context.matches("distro!=fedora-32")
        # One of them not matches
        assert self.context.matches("distro!=fedora-32,centos-8")
        assert self.context.matches("distro!=fedora-3")
        # Version-like comparison
        assert not self.context.matches("distro!=fedora")

        assert not self.context.matches("pipeline!=ci")
        # One of them matches
        assert self.context.matches("pipeline!=ci,devnull")
        assert self.context.matches("pipeline!=devnull")

        # One of them not matches
        assert self.context.matches("arch!=x86_64")
        # One of them not matches
        assert self.context.matches("arch!=x86_64,aarch64")
        assert self.context.matches("arch!=aarch64")
        assert self.context.matches("arch!=aarch64,s390x")

    def test_minor_eq(self):
        centos = Context(distro="centos-8.2.0")
        for undecidable in ["fedora", "fedora-3", "centos-7"]:
            with pytest.raises(CannotDecide):
                centos.matches("distro ~= {}".format(undecidable))
        assert centos.matches("distro ~= centos")
        assert centos.matches("distro ~= centos-8")
        assert centos.matches("distro ~= centos-8.2")
        assert not centos.matches("distro ~= centos-8.3")
        assert centos.matches("distro ~= centos-8.2.0")
        assert not centos.matches("distro ~= centos-8.3.0")
        assert centos.matches("distro ~= centos-8.2.0.0")
        assert not centos.matches("distro ~= centos-8.3.0.0")

        multi = Context(distro=["centos-8.2.0", "centos-7.6.0"])
        for undecidable in [
                "fedora",
                "fedora-3",
                "rhel-7",
                "rhel-7.8.0",
                "centos-6",
                "centos-6.5"]:
            with pytest.raises(CannotDecide):
                multi.matches("distro ~= {}".format(undecidable))
        assert multi.matches("distro ~= centos")
        assert multi.matches("distro ~= centos-8")
        assert not multi.matches("distro ~= centos-8.3")
        assert multi.matches("distro ~= centos-7")
        assert multi.matches("distro ~= centos-7.6")
        assert not multi.matches("distro ~= centos-7.5")

        multi_rh = Context(distro=["centos-8.2.0", "rhel-8.2.0", "fedora-40"])
        assert multi_rh.matches("distro ~= centos")
        assert multi_rh.matches("distro ~= rhel")
        assert multi_rh.matches("distro ~= fedora")

        assert multi_rh.matches("distro ~= centos-8")
        assert multi_rh.matches("distro ~= rhel-8")
        assert multi_rh.matches("distro ~= fedora-40")

        with pytest.raises(CannotDecide):
            multi_rh.matches("distro ~= centos-9")
        with pytest.raises(CannotDecide):
            multi_rh.matches("distro ~= rhel-9")
        assert not multi_rh.matches("distro ~= fedora-41")
