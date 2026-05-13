import re

import pytest

from fmf.context import (CannotDecide, Context, ContextValue, InvalidContext,
                         InvalidRule)


@pytest.fixture
def env_centos(context_cls: type[Context]):
    return context_cls(
        arch="x86_64",
        distro="centos-8.4.0",
        component=["bash-5.0.17-1.fc32", "python3-3.8.5-5.fc32"],
        )


class TestExample:
    """
    Examples of possible conditions
    """

    def test_simple_conditions(self, env_centos):
        """
        Rules with single condition
        """

        # "Version" comparison if possible
        assert env_centos.matches("distro == centos")
        assert not env_centos.matches("distro == fedora")
        assert env_centos.matches("distro == centos,fedora")
        assert env_centos.matches("distro == centos-8")
        assert env_centos.matches("distro == centos-8.4")
        assert env_centos.matches("distro > centos-8.3")
        assert env_centos.matches("distro < centos-9")

        # Major/minor operator prefix '~' so it is
        # No minor so it can be compared
        assert env_centos.matches("distro ~< centos-9")
        assert not env_centos.matches("distro ~>= centos-9")
        # Different Major for comparing Minor is not allowed
        with pytest.raises(CannotDecide):
            env_centos.matches("distro ~< centos-9.2")
        # Same major, can be compared
        assert env_centos.matches("distro ~>= centos-8.2")
        assert env_centos.matches("distro ~< centos-8.5")

        # Presence of a dimension
        assert env_centos.matches("fips is not defined")
        assert not env_centos.matches("fips is defined")

        # Operator 'contains' is not necessary anymore
        assert env_centos.matches("component = bash")
        assert env_centos.matches("component = bash, ksh")
        assert not env_centos.matches("component = csh, ksh")

    def test_multi_condition(self, env_centos):
        """
        Rules with multiple conditions
        """

        assert env_centos.matches(
            "arch=x86_64 and distro != fedora")
        assert env_centos.matches(
            "distro = fedora and component >= bash-5.0 or "
            "distro = centos and component >= bash-4.9")
        assert not env_centos.matches(
            "distro = fedora and component >= bash-5.0 or "
            "distro = rhel and component >= bash-4.9")

    def test_minor_comparison_mode(self, context_cls: type[Context]):
        """
        How it minor comparison should work
        """

        centos = context_cls(distro="centos-7.3.0")
        centos6 = context_cls(distro="centos-6.9.0")

        # Simple version compare is not enough
        # Think about feature added in centos-7.4.0 and centos-6.9.0
        # so for 'centos' Context we want matches() == False
        # but for 'centos6' we want matches() == True
        #
        rule = "distro >= centos-7.4.0"
        assert not centos.matches(rule)
        assert not centos6.matches(rule)  # we need the opposite outcome

        rule = "distro >= centos-6.9.0"
        assert centos.matches(rule)  # we need the opposite outcome
        assert centos6.matches(rule)

        assert centos.matches(
            "distro >= centos-7.4.0 or distro >= centos-6.9.0"
            )  # we need the opposite outcome
        assert not centos.matches(
            "distro >= centos-7.4.0 and distro >= centos-6.9.0"
            )  # we need the opposite outcome
        assert centos6.matches(
            "distro >= centos-7.4.0 or distro >= centos-6.9.0"
            )
        assert not centos6.matches(
            "distro >= centos-7.4.0 and distro >= centos-6.9.0"
            )

        # Here comes minor compare into the play as it skip incomparable majors
        # All outcomes are exactly as we need them to be
        # tmt uses undecided='skip' so rule is skipped
        with pytest.raises(CannotDecide):
            centos.matches(
                "distro ~>= centos-7.4.0 or distro ~>= centos-6.9.0"
                )
        assert not centos.matches(
            "distro ~>= centos-7.4.0 and distro ~>= centos-6.9.0"
            )
        assert centos6.matches(
            "distro ~>= centos-7.4.0 or distro ~>= centos-6.9.0"
            )
        # tmt uses undecided='skip' so rule is skipped
        with pytest.raises(CannotDecide):
            centos6.matches(
                "distro ~>= centos-7.4.0 and distro ~>= centos-6.9.0"
                )

    def test_true_false(self, context_cls: type[Context]):
        """
        true/false can be used in rule
        """

        empty = context_cls()
        assert empty.matches('true')
        assert empty.matches(True)
        assert not empty.matches('false')
        assert not empty.matches(False)

        fedora = context_cls(distro='fedora-rawhide')
        # e.g. ad-hoc disabling of rule
        assert not fedora.matches('false and distro == fedora')

        # or enable rule (can be done also by removing when key)
        assert fedora.matches('true or distro == centos-stream')

    def test_right_side_defines_precision(self, context_cls: type[Context]):
        """
        Right side defines how many version parts need to match
        """

        bar_830 = context_cls(dimension="bar-8.3.0")
        bar_ = context_cls(dimension="bar")  # so essentially bar-0.0.0

        # these are equal
        for value in "bar bar-8 bar-8.3 bar-8.3.0".split():
            for op in "== <= >=".split():
                assert bar_830.matches('dimension {0} {1}'.format(op, value))
            for op in "< > !=".split():
                if value == 'bar' and op != '!=':
                    continue
                assert not bar_830.matches(
                    'dimension {0} {1}'.format(op, value))
            # value prefixed so name doesn't match -> not equal
            assert not bar_830.matches('dimension == prefix_{0}'.format(value))
            assert bar_830.matches('dimension != prefix_{0}'.format(value))
            # value prefix so name doesn't match -> cannot be compared
            for op in "<= >=".split():
                with pytest.raises(CannotDecide):
                    bar_830.matches(
                        'dimension {0} prefix_{1}'.format(op, value))

        # valid comparison
        for value in "bar-7 bar-7.2 bar-8.1 bar-7.2.0 bar-8.1.0".split():
            for op in "< <= ==".split():
                assert not bar_830.matches(
                    "dimension {0} {1}".format(op, value))
            for op in "> >= !=".split():
                assert bar_830.matches("dimension {0} {1}".format(op, value))
            assert bar_.matches("dimension != {0}".format(value))
            assert not bar_.matches("dimension == {0}".format(value))

        # these are newer
        for value in "bar-9 bar-9.2 bar-9.2.0".split():
            for op in "> >= ==".split():
                assert not bar_830.matches(
                    'dimension {0} {1}'.format(op, value))
            for op in "< <= !=".split():
                assert bar_830.matches('dimension {0} {1}'.format(op, value))

        # cannot be compared
        for op in "< <= > >=".split():
            with pytest.raises(CannotDecide):
                bar_.matches("dimension {0} {1}".format(op, value))

    def test_right_side_defines_precision_tilda(self, context_cls: type[Context]):
        """
        Right side defines how many version parts need to match (~ operations)
        """

        bar_830 = context_cls(dimension="bar-8.3.0")
        bar_ = context_cls(dimension="bar")  # missing major
        bar_8 = context_cls(dimension="bar-8")  # so essentially bar-8.0.0

        # these are equal
        for value in "bar bar-8 bar-8.3 bar-8.3.0".split():
            for op in "~= ~<= ~>=".split():
                assert bar_830.matches('dimension {0} {1}'.format(op, value))
            for op in "~< ~> ~!=".split():
                if value == 'bar' and op != '~!=':
                    continue
                assert not bar_830.matches(
                    'dimension {0} {1}'.format(op, value))
            # value prefixed so name doesn't match -> not equal
            assert not bar_830.matches('dimension ~= prefix_{0}'.format(value))
            assert bar_830.matches('dimension ~!= prefix_{0}'.format(value))
            # value prefix so name doesn't match -> cannot be compared
            for op in "~<= ~>=".split():
                with pytest.raises(CannotDecide):
                    bar_830.matches(
                        'dimension {0} prefix_{1}'.format(op, value))

        # different major with minor comparison
        for value in "bar-7.2 bar-7.2.0".split():
            for op in "~< ~<= ~> ~>=".split():
                with pytest.raises(CannotDecide):
                    bar_830.matches("dimension {0} {1}".format(op, value))
        # no minor compare required, so major comparison is allowed
        for op in "~< ~<=".split():
            assert not bar_830.matches("dimension {0} bar-7".format(op))
        for op in "~> ~>=".split():
            assert bar_830.matches("dimension {0} bar-7".format(op))

        # these are newer
        for value in "bar-8.4 bar-8.4.0".split():
            for op in "~> ~>= ~=".split():
                assert not bar_830.matches(
                    'dimension {0} {1}'.format(op, value))
            for op in "~< ~<= ~!=".split():
                assert bar_830.matches('dimension {0} {1}'.format(op, value))

        # missing enough data to decide
        for value in "bar-8 bar-8.3 bar-8.3.0".split():
            for op in "~= ~<= ~>= ~< ~> ~!=".split():
                with pytest.raises(CannotDecide):
                    bar_.matches("dimension {0} {1}".format(op, value))
                if value != "bar-8":
                    with pytest.raises(CannotDecide):
                        bar_8.matches("dimension {0} {1}".format(op, value))

    def test_module_streams(self, context_cls: type[Context]):
        """
        How you can use context_cls for modules
        """

        perl = context_cls("module = perl:5.28")

        assert perl.matches("module >= perl:5")
        assert not perl.matches("module > perl:5")

        assert perl.matches("module > perl:5.7")
        assert perl.matches("module >= perl:5.28")

        assert not perl.matches("module > perl:6")
        assert not perl.matches("module > perl:6.2")
        assert not perl.matches("module >= perl:6.2")

        # Using ~ to compare only within same minor
        # e.g feature in 5.28+ but dropped in perl6
        assert perl.matches("module ~>= perl:5.28")
        with pytest.raises(CannotDecide):
            context_cls("module = perl:6.28").matches("module ~>= perl:5.28")

    def test_comma(self, context_cls: type[Context]):
        """
        Comma is sugar for OR
        """

        con = context_cls(single="foo", multi=["first", "second"])
        # First as longer line, then using comma
        assert con.matches("single == foo or single == bar")
        assert con.matches("single == foo, bar")

        assert not con.matches("single == baz or single == bar")
        assert not con.matches("single == baz, bar")

        assert con.matches("single != foo or single != bar")
        assert con.matches("single != foo, bar")

        # And now with multiple values in the dimension
        assert con.matches("multi == first, value")
        assert con.matches("multi == second, value")
        assert con.matches("multi != third, value")

        # True because each first vs second value compare is false
        assert con.matches("multi != first, second")
        assert con.matches("multi != first or multi != second")

        # More real-life example
        distro = context_cls(distro="centos-stream-8")
        assert distro.matches("distro < centos-stream-9, fedora-34")
        assert not distro.matches("distro < fedora-34, centos-stream-8")

    @pytest.mark.parametrize("case_sensitive", [True, False, pytest.param(None, id="default")])
    def test_case_sensitive(self, custom_context_cls: type[Context], case_sensitive):
        """
        Test for case-insensitive matching
        """
        if case_sensitive is not None:
            # Set the value for `DefaultContextDimension.case_sensitive`
            custom_context_cls._context_dimensions._default_dimension_cls.case_sensitive = (
                case_sensitive)

        python = custom_context_cls(component="python3-3.8.5-5.fc32")

        assert python.matches("component == python3")
        assert not python.matches("component == invalid")
        assert python.matches("component > python3-3.7")
        if case_sensitive or case_sensitive is None:
            assert not python.matches("component == PYTHON3,INVALID")
            assert not python.matches("component == Python3")
            assert not python.matches("component == PyTHon3-3.8.5-5.FC32")
            with pytest.raises(CannotDecide):
                python.matches("component < PYTHON3-3.9")
        else:
            assert python.matches("component == PYTHON3,INVALID")
            assert python.matches("component == Python3")
            assert python.matches("component == PyTHon3-3.8.5-5.FC32")
            assert python.matches("component < PYTHON3-3.9")

    def test_regular_expression_matching(self, context_cls: type[Context]):
        """
        Matching regular expressions
        """

        assert context_cls(distro="fedora-42").matches("distro ~ ^fedora-42$")
        assert context_cls(distro="fedora-42").matches("distro ~ fedora")
        assert context_cls(distro="fedora-42").matches("distro ~ fedora|rhel")
        assert context_cls(distro="fedora-42").matches("distro ~ fedora-4.*")
        assert not context_cls(distro="fedora-42").matches("distro ~ fedora-3.*")
        assert not context_cls(distro="fedora-42").matches("distro ~ ubuntu")

        assert context_cls(arch="ppc64").matches("arch ~ ppc64.*")
        assert context_cls(arch="ppc64le").matches("arch ~ ppc64.*")
        assert not context_cls(arch="ppc64le").matches("arch ~ ppc64$")

        assert not context_cls(distro="fedora-42").matches("distro !~ ^fedora-42$")
        assert not context_cls(distro="fedora-42").matches("distro !~ fedora")
        assert not context_cls(distro="fedora-42").matches("distro !~ fedora|rhel")
        assert not context_cls(distro="fedora-42").matches("distro !~ fedora-4.*")
        assert context_cls(distro="fedora-42").matches("distro !~ fedora-3.*")
        assert context_cls(distro="fedora-42").matches("distro !~ ubuntu")

        assert not context_cls(arch="ppc64").matches("arch !~ ppc64.*")
        assert not context_cls(arch="ppc64le").matches("arch !~ ppc64.*")
        assert context_cls(arch="ppc64le").matches("arch !~ ppc64$")


class TestContextValue:
    impossible_split = ["x86_64", "ppc64", "fips", "errata"]
    splittable = [
        ("centos-8.3.0", ("centos", "8", "3", "0")),
        ("python3-3.8.5-5.fc32", ("python3", "3", "8", "5", "5", "fc32")),
        ]

    def test_simple_names(self):
        """
        Values with simple name
        """

        for name in self.impossible_split:
            assert ContextValue(name)._to_compare == tuple([name])
        for name, _ in self.splittable:
            assert ContextValue([name])._to_compare == tuple([name])

    def test_split_to_version(self):
        """
        Possible/impossible splitting to version
        """

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

    def test_version_cmp(self, context_cls: type[Context]):
        first = ContextValue("name")
        assert first.version_cmp(ContextValue("name")) == 0
        assert first.version_cmp(ContextValue("name"), minor_mode=True) == 0
        assert first.version_cmp(ContextValue("name"), ordered=True) == 0
        assert first.version_cmp(ContextValue("name"), ordered=False) == 0
        assert first.version_cmp(ContextValue("NAME"), ordered=True, case_sensitive=False) == 0
        assert first.version_cmp(ContextValue("NAME"), ordered=False, case_sensitive=False) == 0
        assert first.version_cmp(ContextValue("NAME"), ordered=False, case_sensitive=True) == 1

        assert first.version_cmp(ContextValue("name-1"), ordered=False) == 1
        with pytest.raises(CannotDecide):
            first.version_cmp(
                ContextValue("name-1"),
                minor_mode=True,
                ordered=False)
        with pytest.raises(CannotDecide):
            # name missing at least on version part
            first.version_cmp(ContextValue("name-1"), ordered=True) == -1
        with pytest.raises(CannotDecide):
            first.version_cmp(
                ContextValue("name-1"),
                minor_mode=True,
                ordered=True)

        assert first.version_cmp(
            ContextValue("name-1-2"),
            ordered=False) == 1  # name-0.0 != name-1-2

        with pytest.raises(CannotDecide):
            first.version_cmp(
                ContextValue("name-1-2"),
                minor_mode=True,
                ordered=False)
        with pytest.raises(CannotDecide):
            first.version_cmp(
                ContextValue("NAME"),
                ordered=True,
                case_sensitive=True)

        second = ContextValue("name-1-2-3")
        assert second.version_cmp(ContextValue("name"), ordered=False) == 0
        assert second.version_cmp(ContextValue("name"), ordered=True) == 0
        assert second.version_cmp(
            ContextValue("name"), minor_mode=True, ordered=False) == 0
        assert second.version_cmp(
            ContextValue("name"), minor_mode=True, ordered=True) == 0
        assert second.version_cmp(ContextValue("name-1")) == 0
        assert second.version_cmp(ContextValue("name-1"), minor_mode=True) == 0
        # Same minor
        assert second.version_cmp(ContextValue("name-1-2")) == 0
        assert (
            second.version_cmp(ContextValue("name-1-2"), minor_mode=True) == 0)

        third = ContextValue("name-1-2-3")
        with pytest.raises(CannotDecide):
            third.version_cmp(ContextValue("aaa"))
        with pytest.raises(CannotDecide):
            third.version_cmp(ContextValue("zzz"))
        with pytest.raises(CannotDecide):
            third.version_cmp(ContextValue("aaa"), minor_mode=True)

        # Minor mode should care only about minor, aka Y presence
        # so name-1 vs name-2 is defined, but name-1-1 vs name-2-1 is not
        fourth = ContextValue("name-2")
        assert fourth.version_cmp(ContextValue("name-2")) == 0
        assert fourth.version_cmp(ContextValue("name-2"), minor_mode=True) == 0
        assert fourth.version_cmp(ContextValue("name-3")) < 0
        assert fourth.version_cmp(
            ContextValue("name-3"), minor_mode=True) == -1
        assert fourth.version_cmp(ContextValue("name-1")) > 0
        assert fourth.version_cmp(ContextValue("name-1"), minor_mode=True) == 1
        with pytest.raises(CannotDecide):
            assert fourth.version_cmp(
                ContextValue("name-1-1"), minor_mode=True)

        fifth = ContextValue("name-2-1")
        for undecidable in ["name-1-1", ""]:
            with pytest.raises(CannotDecide):
                fifth.version_cmp(ContextValue(undecidable), minor_mode=True)

        # More error states
        with pytest.raises(CannotDecide):
            first.version_cmp(context_cls())  # different object classes

        sixth = ContextValue([])
        with pytest.raises(CannotDecide):
            sixth.version_cmp(first, minor_mode=True)
        with pytest.raises(CannotDecide):
            sixth.version_cmp(first)
        assert sixth != context_cls()

    def test_version_cmp_fedora(self):
        """
        Fedora comparison
        """

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

    def test_compare(self):
        assert ContextValue.compare("1", "1") == 0
        assert ContextValue.compare("a", "a") == 0
        assert ContextValue.compare("1", "1", case_sensitive=False) == 0
        assert ContextValue.compare("A", "a", case_sensitive=False) == 0

        assert ContextValue.compare("rawhide", "aaa") == 1
        assert ContextValue.compare("rawhide", "9999") == 1

        assert ContextValue.compare("8", "19") == -1

    def test_compare_with_case(self):
        assert ContextValue._compare_with_case("1", "1", case_sensitive=True)
        assert ContextValue._compare_with_case("name_1", "name_1", case_sensitive=True)
        assert not ContextValue._compare_with_case("NAME", "name", case_sensitive=True)
        assert not ContextValue._compare_with_case("name_1", "NAME_1", case_sensitive=True)

        assert ContextValue._compare_with_case("1", "1", case_sensitive=False)
        assert ContextValue._compare_with_case("name_1", "name_1", case_sensitive=False)
        assert ContextValue._compare_with_case("NAME", "name", case_sensitive=False)
        assert ContextValue._compare_with_case("name_1", "NAME_1", case_sensitive=False)


class TestParser:
    # Missing expression
    rule_groups_invalid = ["foo<bar and ", "foo<bar and defined bar or "]

    invalid_expressions = [
        "bar",
        "bar |",
        "bar or",
        "& baz",
        "and baz",
        "dim !! value",
        "is defined dim",  # should be different order
        "defined dim",
        ]

    def test_split_rule_to_groups(self, context_cls: type[Context]):
        """
        Split to lists
        """

        for invalid_rule in self.rule_groups_invalid:
            with pytest.raises(InvalidRule):
                context_cls.split_rule_to_groups(invalid_rule)

        # Valid wrt to group splitter
        assert context_cls.split_rule_to_groups("bar") == [["bar"]]
        assert context_cls.split_rule_to_groups(" bar   ") == [["bar"]]
        assert context_cls.split_rule_to_groups("foo = bar") == [["foo = bar"]]
        assert context_cls.split_rule_to_groups(
            "foo = bar and baz") == [["foo = bar", "baz"]]
        assert context_cls.split_rule_to_groups(
            "foo = bar and is defined baz or is not defined foo") == [
                ["foo = bar", "is defined baz"],
                ["is not defined foo"],
                ]
        assert context_cls.split_rule_to_groups("a ~= b or c>d or is defined x") == [
            ["a ~= b"],
            ["c>d"],
            ["is defined x"],
            ]

        assert context_cls.split_rule_to_groups("a == b or true") == [
            ["a == b"],
            ["true"]
            ]

    def test_split_expression(self, context_cls: type[Context]):
        """
        Split to dimension/operator/value tuple
        """

        for invalid in self.invalid_expressions:
            with pytest.raises(InvalidRule):
                context_cls.split_expression(invalid)
        assert context_cls.split_expression("dim is defined") == (
            "dim", "is defined", None)
        assert context_cls.split_expression("dim is not defined") == (
            "dim", "is not defined", None)
        assert context_cls.split_expression("dim < value") == (
            "dim", "<", ["value"])
        assert context_cls.split_expression("dim < value-123") == (
            "dim", "<", ["value-123"])
        assert context_cls.split_expression("dim<value") == (
            "dim", "<", ["value"])
        assert context_cls.split_expression("dim < value,second") == (
            "dim", "<", ["value", "second"])
        assert context_cls.split_expression("dim < value , second") == (
            "dim", "<", ["value", "second"])
        assert context_cls.split_expression("true") == (None, True, None)
        assert context_cls.split_expression("provision-method == local") == (
            "provision-method", "==", ["local"])
        assert context_cls.split_expression("provision-method is defined") == (
            "provision-method", "is defined", None)

    def test_parse_rule(self, context_cls: type[Context]):
        """
        Rule parsing
        """

        for invalid in self.rule_groups_invalid + self.invalid_expressions:
            with pytest.raises(InvalidRule):
                context_cls.parse_rule(invalid)

        assert context_cls.parse_rule("dim is defined") == [
            [("dim", "is defined", None)]]
        assert context_cls.parse_rule("dim < value") == [
            [("dim", "<", ["value"])]]
        assert context_cls.parse_rule("dim < value-123") == [
            [("dim", "<", ["value-123"])]]
        assert context_cls.parse_rule("dim ~< value, second") == [
            [("dim", "~<", ["value", "second"])]]
        assert context_cls.parse_rule(
            "dim < value and dim > valueB or dim != valueC") == [
            [
                ("dim", "<", ["value"]),
                ("dim", ">", ["valueB"])],
            [
                ("dim", "!=", ["valueC"])]]


class TestContext:
    def test_creation(self, context_cls: type[Context]):
        for created in [
                context_cls(dim_a="value", dim_b=["val"], dim_c=["foo", "bar"]),
                context_cls("dim_a=value and dim_b=val and dim_c == foo,bar")]:
            assert created._dimensions["dim_a"] == {
                context_cls._context_dimensions.create("dim_a", "value")}
            assert created._dimensions["dim_b"] == {
                context_cls._context_dimensions.create("dim_b", "val")}
            assert created._dimensions["dim_c"] == {
                context_cls._context_dimensions.create(
                    "dim_c", "foo"), context_cls._context_dimensions.create(
                    "dim_c", "bar")}
        # Invalid ways to create context_cls
        with pytest.raises(InvalidContext):
            context_cls("a=b", "c=d")  # Just argument
        with pytest.raises(InvalidContext):
            context_cls("a=b or c=d")  # Can't use OR
        with pytest.raises(InvalidContext):
            context_cls("a < d")  # Operator other than =/==

    def test_prints(self, context_cls: type[Context]):
        c = context_cls()
        str(c)
        repr(c)

    def test_matches_groups(self, context_cls: type[Context]):
        """
        and/or in rules with yes/no/cannotdecide outcome
        """

        context = context_cls(distro="centos-8.2.0")

        # Clear outcome
        assert context.matches("distro = centos-8.2.0 or distro = fedora")
        assert context.matches("distro = fedora or distro = centos-8.2.0")
        assert not context.matches("distro != centos-8.2.0 or distro = fedora")
        assert context.matches("distro = centos-8 and distro = centos-8.2")
        assert not context.matches("distro = centos-8 and distro = centos-8.6")

        # Some operators cannot be decided
        assert context.matches("distro = centos-8.2.0 or foo=bar")
        assert context.matches("foo=bar or distro = centos-8.2.0")
        assert not context.matches("foo=bar and distro = rhel")
        # Whole rule cannot be decided
        for undecidable in [
                "foo = baz",
                "foo = baz and distro ~<= centos-7.2",  # both are CannotDecide
                "foo = baz and distro ~<= fedora-32 or do=done",
                "foo = bar and distro = centos-8.2.0",  # CannotDecide and True
                "foo = bar or distro = centos-8.9.0",  # CannotDecide or False
                ]:
            with pytest.raises(CannotDecide):
                context.matches(undecidable)

    def test_matches(self, context_cls: type[Context]):
        """
        yes/no/skip test per operator for matches
        """

        context = context_cls(
            distro="fedora-32",
            arch=["x86_64", "ppc64le"],
            component="bash-5.0.17-1.fc32",
            )

        # defined
        assert context.matches("distro is defined")
        assert not context.matches("FOOBAR is defined")
        # skip not possible for this operator

        # !defined
        assert context.matches("FOOBAR is not defined")
        assert not context.matches("distro is not defined")
        # skip not possible for this operator

        # ==
        assert context.matches("distro == fedora-32")
        assert context.matches("distro == fedora")
        assert not context.matches("distro == centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product == fedora-32")

        # !=
        assert not context.matches("distro != fedora-32")
        assert not context.matches("distro != fedora")
        assert context.matches("distro != centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product != fedora-32")

        # ~= aka major/minor mode
        assert context.matches("distro ~= fedora")
        assert context.matches("distro ~= fedora-32")
        assert not context.matches("distro ~= fedora-45")
        assert not context.matches(
            "distro ~= centos-8")  # fedora is not centos
        with pytest.raises(CannotDecide):  # dimension product is not defined
            context.matches("product ~= fedora-32")

        # '<'
        assert context.matches("distro < fedora-33")
        assert not context.matches("distro < fedora-32")
        with pytest.raises(CannotDecide):
            context.matches("product < centos-8")
        # missing version parts are allowed but at least one needs to be
        # defined
        with pytest.raises(CannotDecide):
            context_cls(distro='fedora').matches("distro < fedora-33")
        assert context_cls(distro='foo-1').matches("distro < foo-1.1")

        # '~<':
        assert context_cls(distro='centos-8.3').matches("distro ~< centos-8.4")
        assert context.matches("distro ~< fedora-33")
        with pytest.raises(CannotDecide):
            context.matches("distro ~< centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~< centos-8")
        # right side ignores major
        assert not context.matches("distro ~< fedora")
        assert not context.matches("distro ~> fedora")

        # '<=':
        assert context.matches("distro <= fedora-32")
        assert context.matches("distro <= fedora")
        assert not context.matches("distro <= fedora-30")
        with pytest.raises(CannotDecide):
            context.matches("product <= centos-8")

        # '~<='
        assert context.matches("distro ~<= fedora-33")
        assert context.matches("distro ~<= fedora")
        with pytest.raises(CannotDecide):
            context.matches("distro ~<= centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~<= centos-8")

        # '~!=':
        assert context.matches("distro ~!= fedora-33")
        assert not context.matches("distro ~!= fedora-32")
        assert not context.matches("distro ~!= fedora")
        assert context.matches("distro ~!= centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~!= centos-8")

        # '>=':
        assert context.matches("distro >= fedora-32")
        assert context.matches("distro >= fedora")
        assert not context.matches("distro >= fedora-40")
        with pytest.raises(CannotDecide):
            context.matches("product >= centos-8")

        # '~>=':
        assert context.matches("distro ~>= fedora-32")
        assert context.matches("distro ~>= fedora")
        assert not context.matches("distro ~>= fedora-33")
        with pytest.raises(CannotDecide):
            context.matches("distro ~>= centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~>= centos-8")

        # '>':
        assert context.matches("distro > fedora-30")
        assert not context.matches("distro > fedora-40")
        assert not context.matches("distro > fedora")
        with pytest.raises(CannotDecide):
            context.matches("product > centos-8")

        # '~>':
        assert context.matches("distro ~> fedora-30")
        assert not context.matches("distro ~> fedora-42")
        with pytest.raises(CannotDecide):
            context.matches("distro ~> centos-8")
        with pytest.raises(CannotDecide):
            context.matches("product ~> centos-8")
        assert not context.matches("distro ~> fedora")

    def test_known_troublemakers(self, context_cls: type[Context]):
        """
        Do not regress on these expressions
        """

        # From fmf/issues/89:
        # following is true (missing left values are treated as lower)
        assert context_cls(distro='foo-1').matches('distro < foo-1.1')
        # but only if at least one version part is defined
        with pytest.raises(CannotDecide):
            context_cls(distro='fedora').matches('distro < fedora-33')
        # so use ~ if you need an explict Major check
        with pytest.raises(CannotDecide):
            context_cls(distro='fedora').matches('distro ~< fedora-33')

        assert context_cls(distro='fedora-33').matches('distro == fedora')
        with pytest.raises(CannotDecide):
            context_cls("module = py:5.28").matches("module > perl:5.28")
        with pytest.raises(CannotDecide):
            context_cls("module = py:5").matches("module > perl:5.28")
        with pytest.raises(CannotDecide):
            context_cls("module = py:5").matches("module >= perl:5.28")
        with pytest.raises(CannotDecide):
            context_cls("distro = centos").matches("distro >= fedora")

        assert context_cls("distro = centos").matches("distro != fedora")
        assert not context_cls("distro = centos").matches("distro == fedora")

        rhel7 = context_cls("distro = rhel-7")
        assert rhel7.matches("distro == rhel")
        assert rhel7.matches("distro == rhel-7")
        assert not rhel7.matches("distro == rhel-7.3")
        assert not rhel7.matches("distro == rhel-7.3.eus")
        assert rhel7.matches("distro >= rhel-7")
        assert not rhel7.matches("distro >= rhel-7.3")
        assert not rhel7.matches("distro >= rhel-7.3.eus")
        with pytest.raises(CannotDecide):
            rhel7.matches("distro ~> rhel-7.3")
        assert not rhel7.matches("distro > rhel")

        # https://github.com/psss/fmf/pull/128#pullrequestreview-631589335
        expr = "distro < fedora-33 or distro < centos-6.9"
        # Checking `CannotDecide or False`
        for distro in "fedora-33 fedora-34 centos-7.7".split():
            with pytest.raises(CannotDecide):
                context_cls(distro=distro).matches(expr)
        # Checking `CannotDecide or True`
        assert context_cls(distro="centos-6.5").matches(expr)
        assert context_cls(distro="fedora-32").matches(expr)

    def test_cannotdecides(self, context_cls: type[Context]):
        # https://github.com/psss/fmf/issues/117
        # CannotDecide and True = True and CannotDecide = CannotDecide
        # CannotDecide and False = False and CannotDecide = False
        # CannotDecide or True = True or CannotDecide = True
        # CannotDecide or False = False or CannotDecide = CannotDecide
        _true = "foo == bar"
        _false = "foo != bar"
        _cannot = "baz == bar"
        env = context_cls(foo="bar")
        for a, op, b in [
                (_cannot, 'and', _true),
                (_true, 'and', _cannot),
                (_cannot, 'or', _false),
                (_false, 'or', _cannot),
                ]:
            exp = "{0} {1} {2}".format(a, op, b)
            with pytest.raises(CannotDecide):
                env.matches(exp)
        for outcome, a, op, b in [
                (False, _cannot, 'and', _false),
                (False, _false, 'and', _cannot),
                (True, _cannot, 'or', _true),
                (True, _true, 'or', _cannot),
                ]:
            exp = "{0} {1} {2}".format(a, op, b)
            assert env.matches(exp) == outcome

        assert env.matches("{0} and {1} or {2}".format(_cannot, _false, _true))
        assert not env.matches(
            "{0} or {1} and {2}".format(_false, _cannot, _false))


class TestOperators:
    """
    more thorough testing for operations
    """

    @pytest.fixture()
    def context(self, context_cls: type[Context]) -> Context:
        return context_cls(
            # nvr like single
            distro="fedora-32",
            # raw name  single
            pipeline="ci",
            # raw name list
            arch=["x86_64", "ppc64le"],
            # nvr like list
            components=["bash-5.0.17-1.fc32", "curl-7.69.1-6.fc32"],
            )

    # is (not) defined is too simple and covered by test_matches

    def test_equal(self, context: Context):
        assert context.matches("distro=fedora-32")
        # One of them matches
        assert context.matches("distro=fedora-32,centos-8")
        assert not context.matches("distro=fedora-3")
        # Version-like comparison
        assert context.matches("distro=fedora")

        assert context.matches("pipeline=ci")
        # One of them matches
        assert context.matches("pipeline=ci,devnull")
        assert not context.matches("pipeline=devnull")

        assert context.matches("arch=x86_64")
        # One of them matches
        assert context.matches("arch=x86_64,aarch64")
        assert not context.matches("arch=aarch64")
        assert not context.matches("arch=aarch64,s390x")

    def test_not_equal(self, context: Context):
        assert not context.matches("distro!=fedora-32")
        # One of them not matches
        assert context.matches("distro!=fedora-32,centos-8")
        assert context.matches("distro!=fedora-3")
        # Version-like comparison
        assert not context.matches("distro!=fedora")

        assert not context.matches("pipeline!=ci")
        # One of them matches
        assert context.matches("pipeline!=ci,devnull")
        assert context.matches("pipeline!=devnull")

        # One of them not matches
        assert context.matches("arch!=x86_64")
        # One of them not matches
        assert context.matches("arch!=x86_64,aarch64")
        assert context.matches("arch!=aarch64")
        assert context.matches("arch!=aarch64,s390x")

    def test_minor_eq(self, context_cls: type[Context]):
        centos = context_cls(distro="centos-8.2.0")
        for not_equal in ["fedora", "fedora-3", "centos-7"]:
            assert not centos.matches("distro ~= {}".format(not_equal))
        assert centos.matches("distro ~= centos")
        assert centos.matches("distro ~= centos-8")
        assert centos.matches("distro ~= centos-8.2")
        assert not centos.matches("distro ~= centos-8.3")
        assert centos.matches("distro ~= centos-8.2.0")
        assert not centos.matches("distro ~= centos-8.3.0")
        with pytest.raises(CannotDecide):
            centos.matches("distro ~= centos-8.2.0.0")

        multi = context_cls(distro=["centos-8.2.0", "centos-7.6.0"])
        for not_equal in [
                "fedora",
                "fedora-3",
                "rhel-7",
                "rhel-7.8.0",
                "centos-6",
                "centos-6.5"]:
            assert not multi.matches("distro ~= {}".format(not_equal))
        assert multi.matches("distro ~= centos")
        assert multi.matches("distro ~= centos-8")
        assert not multi.matches("distro ~= centos-8.3")
        assert multi.matches("distro ~= centos-7")
        assert multi.matches("distro ~= centos-7.6")
        assert not multi.matches("distro ~= centos-7.5")

        multi_rh = context_cls(distro=["centos-8.2.0", "rhel-8.2.0", "fedora-40"])
        assert multi_rh.matches("distro ~= centos")
        assert multi_rh.matches("distro ~= rhel")
        assert multi_rh.matches("distro ~= fedora")

        assert multi_rh.matches("distro ~= centos-8")
        assert multi_rh.matches("distro ~= rhel-8")
        assert multi_rh.matches("distro ~= fedora-40")

        assert not multi_rh.matches("distro ~= centos-9")
        assert not multi_rh.matches("distro ~= rhel-9")
        assert not multi_rh.matches("distro ~= fedora-41")


class TestContextDimension:
    @pytest.fixture(scope="function")
    def context(self, custom_context_cls: type[Context]) -> Context:
        class FooContext(custom_context_cls._context_dimensions[str]):
            _dimension_name = "foo"

            # For simplicity, make this just compare string

            @classmethod
            def _make_value(cls, raw_value: str) -> str:
                return raw_value

            def _op_eq(self, other: str) -> bool:
                return self.value == other

            def _op_less(self, other: str) -> bool:
                return self.value < other

            def _op_less_or_equal(self, other: str) -> bool:
                return self.value <= other

            def _op_greater(self, other: str) -> bool:
                return self.value > other

            def _op_greater_or_equal(self, other: str) -> bool:
                return self.value >= other

            def _op_minor_eq(self, other: str) -> bool:
                return self._op_eq(other)

            def _op_minor_less(self, other: str) -> bool:
                return self._op_less(other)

            def _op_minor_less_or_equal(self, other: str) -> bool:
                return self._op_minor_less_or_equal(other)

            def _op_minor_greater(self, other: str) -> bool:
                return self._op_greater(other)

            def _op_minor_greater_or_equal(self, other: str) -> bool:
                return self._op_greater_or_equal(other)

            def _op_match(self, other: str) -> bool:
                return re.search(other, self.raw_value) is not None

        return custom_context_cls(
            foo="foo-10",
            bar="bar-10",
            )

    def test_custom_dimension(self, context: Context):
        # foo is a custom dimension following text comparison ("10" < "2")
        foo_dimensions = list(context._dimensions["foo"])
        foo_class = foo_dimensions[0].__class__
        assert foo_class.__name__ == "FooContext"
        assert context.matches("foo < foo-2")
        assert context.matches("foo > bar-2")

        # bar is a ContextValue, so it should follow test_matches (int(10) > int(2))
        bar_dimensions = list(context._dimensions["bar"])
        assert isinstance(bar_dimensions[0], context._context_dimensions._default_dimension_cls)
        assert context.matches("bar > bar-2")
        with pytest.raises(CannotDecide):
            context.matches("bar < foo-2")
