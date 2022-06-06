"""
All you need to decide if Context matches

For user documentation (rule syntax, motivation) see
https://fmf.readthedocs.io/en/latest/context.html

Reminder: FMF doesn't know attribute name which holds rules nor
the context used for adjusting.
It is up to caller of fmf.base.Tree.adjust to provide it.

To use it from your code:
1. Load Tree() as before
2. Initialize Context() according your preferences
3. Call tree's .adjust() to process the rules

See https://fmf.readthedocs.io/en/latest/modules.html#fmf.Tree.adjust
"""

import re


class CannotDecide(Exception):
    pass


class InvalidRule(Exception):
    pass


class InvalidContext(Exception):
    pass


class ContextValue:
    """ Value for dimension """

    def __init__(self, origin):
        """
        ContextValue("foo-1.2.3")
        ContextValue(["foo", "1", "2", "3"])
        """
        if isinstance(origin, (tuple, list)):
            self._to_compare = tuple(origin)
        else:
            self._to_compare = self._split_to_version(origin)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._to_compare == other._to_compare
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return str(self._to_compare)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self._to_compare))

    def version_cmp(self, other, minor_mode=False, ordered=True):
        """
        Comparing two ContextValue objects

        other: The right side to compare with. Defines precision.
            E.g. centos -> just compare name
                 centos-7 -> compare name and major version
                 centos-7.4 -> compare name, major and minor version
                 foo-1.2.3.4 -> compare all version parts
            If the left side (self) is missing the version part it is
            treated as if it was lower then matching version part from
            the right side. However the left side needs to contain at
            least one version part.

        minor_mode: If True then 'major' version has to match to allow
            'minor' comparisons. Used with ~ prefixed operations (~< etc.)
            E.g. `centos-6.3 ~< centos-7` is True because the right side
            doesn't care about minor but `centos-6.3 ~< centos-7.2` is
            CannotDecide because the right side wants to compare minor
            versions of different majors.

        ordered:
            False ... return 0 when equal, 1 otherwise
            True ... raise CannotDecide when name differ (and thus
                     cannot be compared), otherwise return
                        -1 when self < other
                         0 when self == other
                         1 when self > other
        """
        if not isinstance(other, self.__class__):
            raise CannotDecide("Invalid types.")

        if len(self._to_compare) == 0 or len(other._to_compare) == 0:
            raise CannotDecide("Empty name part.")

        if self._to_compare[0] != other._to_compare[0]:
            if ordered:
                raise CannotDecide(
                    "Name parts differ, cannot compare for order.")
            return 1  # not equal
        # From here name parts are equal
        if minor_mode and len(other._to_compare) > 1:
            # right side cares about 'major'
            try:
                if self._to_compare[1] != other._to_compare[1]:
                    if ordered:
                        if len(other._to_compare) > 2:
                            # future Y comparison not allowed
                            raise CannotDecide(
                                "Cannot compare minors between "
                                "mismatched majors.")
                    else:  # not equal
                        return 1
            except IndexError:
                raise CannotDecide(
                    "Missing major version in the left (dimension) value.")
        # From here same major version or minor comparison is not requested
        # Now we can compare version parts as long as other needs to
        compared = 0
        for first, second in zip(self._to_compare[1:], other._to_compare[1:]):
            compared = self.compare(first, second)
            if compared != 0:  # not equal - return immediately
                return compared
        leftover_version_parts = len(other._to_compare) - len(self._to_compare)
        if leftover_version_parts <= 0:
            # Everything wanted by right side compared thus they are equal
            return 0
        elif minor_mode:
            # The right side wants to compare more
            # but this is not allowed in minor_mode
            raise CannotDecide("Not enough version parts.")  # FIXME
        elif not ordered:
            return 1  # they are not equal
        elif len(self._to_compare) == 1:
            raise CannotDecide("No version part defined for left side.")
        else:
            return -1  # other is larger (more pars)

    @staticmethod
    def compare(first, second):
        """ compare two version parts """
        # Ideally use `from packaging import version` but we need older
        # python support too so very rough
        try:
            # convert to int
            first_version = int(first)
            second_version = int(second)
        except ValueError:
            # fallback to compare as strings
            first_version = first
            second_version = second
        return (
            (first_version > second_version) -
            (first_version < second_version))

    @staticmethod
    def _split_to_version(text):
        """
        Try to split text into name + version parts

        Examples:
            centos-8.3.0
                name: centos
                version: 8, 3, 0
            python3-3.8.5-5.fc32
                name: python3
                version: 3, 8, 5, 5, fc32
            x86_64
                name: x86_64
                version: no version parts

        :param text: original value

        :return: tuple of name followed by version parts
        :rtype: tuple
        """
        return tuple(re.split(r":|-|\.", text))

    def __hash__(self):
        return hash(self._to_compare)


class Context:
    """ Represents https://fmf.readthedocs.io/en/latest/context.html """
    # Operators' definitions

    def _op_defined(self, dimension_name, values):
        """ 'is defined' operator """
        return dimension_name in self._dimensions

    def _op_not_defined(self, dimension_name, values):
        """ 'is not defined' operator """
        return dimension_name not in self._dimensions

    def _op_eq(self, dimension_name, values):
        """ '=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, ordered=False) == 0

        return self._op_core(dimension_name, values, comparator)

    def _op_not_eq(self, dimension_name, values):
        """ '!=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, ordered=False) != 0

        return self._op_core(dimension_name, values, comparator)

    def _op_minor_eq(self, dimension_name, values):
        """ '~=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(
                it_val, minor_mode=True, ordered=False) == 0

        return self._op_core(dimension_name, values, comparator)

    def _op_minor_not_eq(self, dimension_name, values):
        """ '~!=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(
                it_val, minor_mode=True, ordered=False) != 0

        return self._op_core(dimension_name, values, comparator)

    def _op_minor_less_or_eq(self, dimension_name, values):
        """ '~<=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(
                it_val, minor_mode=True, ordered=True) <= 0

        return self._op_core(dimension_name, values, comparator)

    def _op_minor_less(self, dimension_name, values):
        """ '~<' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(
                it_val, minor_mode=True, ordered=True) < 0

        return self._op_core(dimension_name, values, comparator)

    def _op_less(self, dimension_name, values):
        """ '<' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, ordered=True) < 0

        return self._op_core(dimension_name, values, comparator)

    def _op_less_or_equal(self, dimension_name, values):
        """ '<=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, ordered=True) <= 0

        return self._op_core(dimension_name, values, comparator)

    def _op_greater_or_equal(self, dimension_name, values):
        """ '>=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, ordered=True) >= 0

        return self._op_core(dimension_name, values, comparator)

    def _op_minor_greater_or_equal(self, dimension_name, values):
        """ '~>=' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(
                it_val, minor_mode=True, ordered=True) >= 0

        return self._op_core(dimension_name, values, comparator)

    def _op_greater(self, dimension_name, values):
        """ '>' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, ordered=True) > 0

        return self._op_core(dimension_name, values, comparator)

    def _op_minor_greater(self, dimension_name, values):
        """ '~>' operator """

        def comparator(dimension_value, it_val):
            return dimension_value.version_cmp(
                it_val, minor_mode=True, ordered=True) > 0

        return self._op_core(dimension_name, values, comparator)

    def _op_core(self, dimension_name, values, comparator):
        """
        Evaluate value from dimension vs target values combination

        Stop evaluation after first True outcome

        Raises CannotDecide when dimension doesn't exist or no value
        pair could be compared.
        """
        try:
            decided = False
            for dimension_value in self._dimensions[dimension_name]:
                for it_val in values:
                    try:
                        if comparator(dimension_value, it_val):
                            return True
                        else:
                            decided = True
                    except CannotDecide:
                        pass
            if decided:
                return False
            # All comparissons ended as CannotDecide
            raise CannotDecide("No values could be compared.")
        except KeyError:
            raise CannotDecide(
                "Dimension {0} is not defined.".format(dimension_name))

    operator_map = {
        "is defined": _op_defined,
        "is not defined": _op_not_defined,
        "<": _op_less,
        "~<": _op_minor_less,
        "<=": _op_less_or_equal,
        "~<=": _op_minor_less_or_eq,
        "==": _op_eq,
        "~=": _op_minor_eq,
        "!=": _op_not_eq,
        "~!=": _op_minor_not_eq,
        ">=": _op_greater_or_equal,
        "~>=": _op_minor_greater_or_equal,
        ">": _op_greater,
        "~>": _op_minor_greater,
        }

    # Triple expression: dimension operator values
    # [^=].* is necessary as .+ matches '= something'
    re_expression_triple = re.compile(
        r"(\w+)"
        + r"\s*("
        + r"|".join(
            set(operator_map.keys()) - {"is defined", "is not defined"})
        + r")\s*"
        + r"([^=].*)")
    # Double expression: dimension operator
    re_expression_double = re.compile(
        r"(\w+)" + r"\s*(" + r"|".join(["is defined", "is not defined"]) + r")"
        )

    # To split by 'and' operator
    re_and_split = re.compile(r'\band\b')

    # To split by 'or' operator
    re_or_split = re.compile(r'\bor\b')

    def __init__(self, *args, **kwargs):
        """
        Context(rule string)
        Context(dimension=ContextValue())
        Context(dimension=list(ContextValue()))

        :raises InvalidContext
        """
        self._dimensions = {}

        # Initialized with rule
        if args:
            if len(args) != 1:
                raise InvalidContext()
            definition = Context.parse_rule(args[0])
            # No ORs and at least one expression in AND
            if len(definition) != 1 or not definition[0]:
                raise InvalidContext()
            for dim, op, values in definition[0]:
                if op != "==":
                    raise InvalidContext()
                self._dimensions[dim] = set(values)
        # Initialized with dimension=value(s)
        for dimension_name, values in kwargs.items():
            if not isinstance(values, list):
                values = [values]
            self._dimensions[dimension_name] = set(
                [self.parse_value(val) for val in values]
                )

    @staticmethod
    def parse_rule(rule):
        """
        Parses rule into expressions

        Expression is a tuple of dimension_name, operator_str, list of
        value objects. Parsed rule is nested list of expression from OR
        and AND operators. Items of the first dimension are in OR
        relation. Items in the second dimension are in AND relation.

        expr_1 and expr_2 or expr_3 is returned as [[expr_1, expr_2], expr_3]
        expr_4 or expr_5 is returned as [[expr_4], [expr_5]]
        expr_6 and expr_7 is returned as [[expr_6, expr_7]]

        :param rule: rule to parse
        :type rule: str
        :return: nested list of expressions from the rule
        :raises InvalidRule:  Syntax error in the rule
        """
        parsed_rule = []
        # Change '=' to '=='
        rule = re.sub(r"(?<!=|!|~|<|>)=(?!=)", "==", rule)
        rule_parts = Context.split_rule_to_groups(rule)
        for and_group in rule_parts:
            parsed_and_group = []
            for part in and_group:
                dimension, operator, raw_values = Context.split_expression(
                    part)
                if raw_values is not None:
                    values = [
                        Context.parse_value(value) for value in raw_values]
                else:
                    values = None
                parsed_and_group.append((dimension, operator, values))
            if parsed_and_group:
                parsed_rule.append(parsed_and_group)
        return parsed_rule

    @staticmethod
    def parse_value(value):
        """ Single place to convert to ContextValue """
        return ContextValue(str(value))

    @staticmethod
    def split_rule_to_groups(rule):
        """
        Split rule into nested lists, no real parsing

        expr0 and expr1 or expr2 is split into [[expr0, expr1], [expr2]]

        :param rule: rule to split
        :type rule: str
        :raises InvalidRule: Syntax error in the rule
        """
        rule_parts = []
        for or_group in Context.re_or_split.split(rule):
            if not or_group:
                raise InvalidRule("Empty OR expression in {}.".format(rule))
            and_group = []
            for part in Context.re_and_split.split(or_group):
                part_stripped = part.strip()
                if not part_stripped:
                    raise InvalidRule(
                        "Empty AND expression in {}.".format(rule))
                and_group.append(part_stripped)
            rule_parts.append(and_group)
        return rule_parts

    @staticmethod
    def split_expression(expression):
        """
        Split expression to dimension name, operator and values

        When operator doesn't have right side, None is returned instead
        of the list of values.

        :param expression: expression to split
        :type expression: str
        :raises InvalidRule: When expression cannot be split, e.g. syntax error
        :return: tuple(dimension name, operator, list of values)
        :rtype: tuple(str, str, list|None)
        """
        # Triple expressions
        match = Context.re_expression_triple.match(expression)
        if match:
            dimension, operator, raw_values = match.groups()
            return (dimension, operator, [
                val.strip() for val in raw_values.split(",")])
        # Double expressions
        match = Context.re_expression_double.match(expression)
        if match:
            return (match.group(1), match.group(2), None)
        raise InvalidRule("Cannot parse expression '{}'.".format(expression))

    def matches(self, rule):
        """
        Does the rule match the current Context?

        We have three outcomes: Yes, No and CannotDecide

        CannotDecide and True == True and CannotDecide == CannotDecide
        CannotDecide and False == False and CannotDecide == False
        CannotDecide or True == True or CannotDecide == True
        CannotDecide or False == False or CannotDecide == CannotDecide

        :param rule: Single rule to decide
        :type rule: str
        :rtype: bool
        :raises CannotDecide: Impossible to decide the rule wrt current
            Context, e.g. dimension is missing
        :raises InvalidRule:  Syntax error in the rule
        """
        final_outcome = None  # None is CannotDecide
        valid = False  # Is final outcome valid?
        for and_group in self.parse_rule(rule):
            and_outcome = None  # None is CannotDecide
            and_valid = False
            for expression in and_group:
                try:
                    result = self.evaluate(expression)
                except CannotDecide:
                    result = None

                if and_valid:
                    if and_outcome is False or result is False:
                        # False makes CannotDecide False
                        and_outcome = False
                    elif result is True and and_outcome is True:
                        and_outcome = True
                    else:
                        # CannotDecide
                        and_outcome = None
                else:
                    and_valid = True
                    and_outcome = result
                if and_outcome is False:
                    # No need to check the rest of AND group
                    break
            # Just making sure, parse_rule should have raised it already
            assert and_valid, (
                "Malformed expression: Missing AND part in {0}".format(rule))
            # AND group finished as True, no need to process the rest of
            # OR groups
            if and_outcome is True:
                return True
            # Resolve current OR couple
            if valid:
                # True was already returned, it interim outcome can be
                # False or CannotDecide
                if and_outcome is None or final_outcome is None:
                    final_outcome = None  # CannotDecide
                else:
                    final_outcome = False
            else:
                final_outcome = and_outcome
                valid = True
        # Just making sure, parse_rule should have raised it already
        assert valid, (
            "Malformed expression: Missing OR part in {0}".format(rule))
        if final_outcome is False:
            return False
        else:
            raise CannotDecide()  # It's up to callee how to treat this

    def evaluate(self, expression):
        dimension_name, operator, values = expression
        return self.operator_map[operator](self, dimension_name, values)
