# coding: utf-8
import re

"""
== Rule Syntax ==

CONDITION ::= expression (bool expression)*
bool ::= '&&' | '||'
expression ::= dimension operator values
dimension ::= [[:alnum:]]+
operator ::= '==' | '!=' | '<' | '<=' | '>' | '>=' | '~==' | '~!=' |
    '~<' | '~<=' | '~>' | '~>=' | 'defined' | '!defined'
values ::= value (',' value)*
value ::= [[:alnum:]]+

Operators 'defined' and '!defined' do not have a right side.

Check tests/unit/test_relevancy for Examples.

== Values treated as version ==

Each value is parsed into name + version parts (dash separated, similar
to rpm nvr). If it isn't possible then the whole value is stored as name
part.

Example:
centos-8.3.0 -> name centos, version parts are 8, 3, 0
python3-3.8.5-5.fc32 -> name  python3, version parts are 3.8.5, 5.fc32

== Missing dimension in expression ==

Expression can use dimension which is not defined. Return values of
operations other than `(!)defined` are not specified and thus such
expression is ignored.

Condition with unspecified outcome (where none of expression can be
evaluated) is marked as such and it is up to the caller to provide
default behaviour.
"""


class CannotDecide(Exception):
    pass


class InvalidRule(Exception):
    pass


class InvalidContext(Exception):
    pass


class ContextValue(object):
    """ Value for dimension """

    def __init__(self, origin):
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

    def version_cmp(self, other, minor_mode=False):

        if not isinstance(other, self.__class__):
            raise CannotDecide("Invalid types")

        if len(self._to_compare) == 0 or len(other._to_compare) == 0:
            raise CannotDecide("Empty name part")

        if minor_mode:
            if self._to_compare[0] != other._to_compare[0]:
                raise CannotDecide("Name parts differ")
            # When both have major and at least one has minor version we treat
            # that differently
            if (
                len(self._to_compare) > 1
                and len(other._to_compare) > 1
                and (len(self._to_compare) > 2 or len(other._to_compare) > 2)
            ):
                if self._to_compare[1] != other._to_compare[1]:
                    raise CannotDecide("Major versions differ")

        # Name parts are same and we can compare
        compared = 0
        for first, second in zip(self._to_compare, other._to_compare):
            compared = (first > second) - (first < second)
            if compared != 0:
                return compared
        return compared

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


class Context(object):
    # Operators' definitions
    def _op_defined(self, dimension_name, values):
        """ 'defined' operand """
        return dimension_name in self._dimensions

    def _op_not_defined(self, dimension_name, values):
        """ '!defined' operand """
        return dimension_name not in self._dimensions

    def _op_eq(self, dimension_name, values):
        """ '=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val) == 0

        return self._op_core(dimension_name, values, func)

    def _op_not_eq(self, dimension_name, values):
        """ '!=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val) != 0

        return self._op_core(dimension_name, values, func)

    def _op_minor_eq(self, dimension_name, values):
        """ '~=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, minor_mode=True) == 0

        return self._op_core(dimension_name, values, func)

    def _op_minor_not_eq(self, dimension_name, values):
        """ '~!=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, minor_mode=True) != 0

        return self._op_core(dimension_name, values, func)

    def _op_minor_less_or_eq(self, dimension_name, values):
        """ '~<=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, minor_mode=True) <= 0

        return self._op_core(dimension_name, values, func)

    def _op_minor_less(self, dimension_name, values):
        """ '~<' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, minor_mode=True) < 0

        return self._op_core(dimension_name, values, func)

    def _op_less(self, dimension_name, values):
        """ '<' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val) < 0

        return self._op_core(dimension_name, values, func)

    def _op_less_or_equal(self, dimension_name, values):
        """ '<=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val) <= 0

        return self._op_core(dimension_name, values, func)

    def _op_greater_or_equal(self, dimension_name, values):
        """ '>=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val) >= 0

        return self._op_core(dimension_name, values, func)

    def _op_minor_greater_or_equal(self, dimension_name, values):
        """ '~>=' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, minor_mode=True) >= 0

        return self._op_core(dimension_name, values, func)

    def _op_greater(self, dimension_name, values):
        """ '>' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val) > 0

        return self._op_core(dimension_name, values, func)

    def _op_minor_greater(self, dimension_name, values):
        """ '~>' operand """

        def func(dimension_value, it_val):
            return dimension_value.version_cmp(it_val, minor_mode=True) > 0

        return self._op_core(dimension_name, values, func)

    def _op_core(self, dimension_name, values, func):
        """ Evaluate values from dimension vs expected values combinations """
        try:
            decided = False
            for dimension_value in self._dimensions[dimension_name]:
                for it_val in values:
                    try:
                        if func(dimension_value, it_val):
                            return True
                        else:
                            decided = True
                    except CannotDecide:
                        pass
            if decided:
                return False
            raise CannotDecide("All operations where not defined")
        except KeyError:
            raise CannotDecide(
                "Dimension {} is not defined".format(dimension_name))

    operand_map = {
        "defined": _op_defined,
        "!defined": _op_not_defined,
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

    # Triple expression: dimension operand values
    # [^=].* is necessary as .+ was able to match '= something'
    re_expression_triple = re.compile(
        r"(\w+)"
        + r"\s*("
        + r"|".join(set(operand_map.keys()) - {"defined", "!defined"})
        + r")\s*"
        + r"([^=].*)"
    )
    # Double expression: dimension operand
    re_expression_double = re.compile(
        r"(\w+)" + r"\s*(" + r"|".join(["defined", "!defined"]) + r")"
    )

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

        Expression is a tuple of dimension_name, operand_str, list of
        value objects. Parsed rule is nested list of expression from OR
        and AND operands. Items of the first dimension are in OR
        relation. Items in the second dimension are in AND relation.

        expr_1 && expr_2 || expr_3 is returned as [[expr_1, expr_2], expr_3]
        expr_4 || expr_5 is returned as [[expr_4], [expr_5]]
        expr_6 && expr_7 is returned as [[expr_6, expr_7]]

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
                dimension, operand, raw_values = Context.split_expression(part)
                if raw_values is not None:
                    values = [
                        Context.parse_value(value) for value in raw_values]
                else:
                    values = None
                parsed_and_group.append((dimension, operand, values))
            if parsed_and_group:
                parsed_rule.append(parsed_and_group)
        return parsed_rule

    @staticmethod
    def parse_value(value):
        return ContextValue(value)

    @staticmethod
    def split_rule_to_groups(rule):
        """
        Split rule into nested lists, no real parsing

        expr0 && expr1 || expr2 is split into [[expr0, expr1], [expr2]]

        :param rule: rule to split
        :type rule: str
        :raises InvalidRule: Syntax error in the rule
        """
        rule_parts = []
        for or_group in rule.split("||"):
            if not or_group:
                raise InvalidRule("empty OR expression in {}".format(rule))
            and_group = []
            for part in or_group.split("&&"):
                part_stripped = part.strip()
                if not part_stripped:
                    raise InvalidRule(
                        "empty AND expression in {}".format(rule))
                and_group.append(part_stripped)
            rule_parts.append(and_group)
        return rule_parts

    @staticmethod
    def split_expression(expression):
        """
        Split expression to dimension name, operand and values

        When operand doesn't have right side, None is returned instead
        of the list of values.

        :param expression: expression to split
        :type expression: str
        :raises InvalidRule: When expression cannot be split, e.g. syntax error
        :return: tuple(dimension name, operand, list of values)
        :rtype: tuple(str, str, list|None)
        """
        # Triple expressions
        match = Context.re_expression_triple.match(expression)
        if match:
            dimension, operand, raw_values = match.groups()
            return (dimension, operand, [
                val.strip() for val in raw_values.split(",")])
        # Double expressions
        match = Context.re_expression_double.match(expression)
        if match:
            return (match.group(1), match.group(2), None)
        raise InvalidRule("Cannot parse expression '{}'.".format(expression))

    # FIXME - WIP
    def matches(self, rule):
        """
        Does the rule match the current Context?

        We have three outcomes: Yes, No and can't say

        :param rule: Single rule to decide
        :type rule: str
        :rtype: bool
        :raises CannotDecide: Impossible to decide the rule wrt current
            Context, e.g. dimension is missing
        :raises InvalidRule:  Syntax error in the rule
        """
        decided_whole = False  # At least one outcome overall
        for and_group in self.parse_rule(rule):
            decided_group = False
            outcome = None  # At least one outcome within AND relation
            for expression in and_group:
                # Skip over CannotDecide expressions
                try:
                    if outcome is None:
                        outcome = self.evaluate(expression)
                    else:
                        outcome = outcome and self.evaluate(expression)
                    decided_group = True
                    decided_whole = True
                    if not outcome:
                        break  # No need to check the rest
                except CannotDecide:
                    pass
            # If we could decide at least one expression and outcome is
            # True -> return it
            if decided_group and outcome:
                return True
            # Otherwise process next OR sections
        if decided_whole:
            return False  # True would have returned already
        else:
            raise CannotDecide()  # It's up to callee how to treat this

    def evaluate(self, expression):
        dimension_name, operand, values = expression
        return self.operand_map[operand](self, dimension_name, values)
