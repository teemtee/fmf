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

import functools
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, Generic, Optional, TypeAlias, TypeVar

T = TypeVar("T")


class CannotDecide(Exception):
    pass


class InvalidRule(Exception):
    pass


class InvalidContext(Exception):
    pass


OperatorFunc: TypeAlias = Callable[[str], bool]


@dataclass(frozen=True)
class Operators:
    """
    Decorator for defining a comparison operator.
    """

    #: Registrar of defined operators and the functions associated with them. Negated
    #: operators use the same function, but are marked to be negated in the second term
    #: of the tuple.
    registrar: dict[str, tuple[str, bool]] = field(default_factory=dict)

    def add(self,
            operator: str,
            negated_operator: Optional[str] = None,
            ) -> Callable[[OperatorFunc], OperatorFunc]:
        def decorator(func: OperatorFunc) -> OperatorFunc:
            if operator in self.registrar:
                raise ValueError(f"Operator '{operator}' already defined")
            self.registrar[operator] = (func.__name__, False)
            if negated_operator:
                self.registrar[negated_operator] = (func.__name__, True)
            return func

        assert operator != negated_operator
        return decorator

    def execute(self, operator: str, inst: "ContextDimension[T]", other: str) -> bool:
        operator_func, negate = self.registrar[operator]
        func: OperatorFunc = getattr(inst, operator_func)
        if negate:
            return not func(other)
        return func(other)


@dataclass(frozen=True)
class ContextDimension(ABC, Generic[T]):
    """
    Representation of a context dimension with both name and value.

    This defines the operator rules and processing of the raw string values.

    A consumer should subclass this and initialize :py:attr:`_registrar` to define
    their own subset of context dimensions that they process. By default (if this is
    not subclassed and nothing is registered) the dimension values are treated as
    :py:class:`ContextValue`.

    .. code-block:: python

        class TmtContextDimension(fmf.context.ContextDimension):
            _registrar = {}

        class TmtContext(fmf.context.Context):
            _context_dimensions = TmtContextDimension

        class DistroContextDimension(TmtContextDimension[DistroAlias]):
            _dimension_name = "distro"

            @classmethod
            @abstractmethod
            def _make_value(cls, raw_value: str) -> DistroAlias:
                ...

            def operate_value(self, operator: str, other_value: DistroAlias) -> bool:
                ...
    """

    #: Collection of comparison operators defined
    operators: ClassVar[Operators] = Operators()

    #: Collection of known :py:class:`ContextDimension`. The consumer should
    #: initialize
    _registrar: ClassVar[dict[str, type["ContextDimension"]]]

    #: Default :py:class:`ContextDimension` class used in :py:func:`create_default`
    _default_dimension_cls: ClassVar[type["DefaultContextDimension"]]

    #: Static dimension name. Must be defined when subclassing a specific
    #: :py:class:`ContextDimension`
    _dimension_name: ClassVar[str]

    #: The raw value given by the user
    raw_value: str

    @property
    def name(self) -> str:
        """
        The final context dimension name
        """
        return self._dimension_name

    @functools.cached_property
    def value(self) -> T:
        """
        The dimension's processed value
        """
        return self._make_value(self.raw_value)

    @classmethod
    @abstractmethod
    def _make_value(cls, raw_value: str) -> T:
        """
        Convert a ``raw_value`` string into an actual ``T`` type
        """
        raise NotImplementedError

    @classmethod
    def __init_subclass__(cls) -> None:
        # Do nothing if this is a dynamic ContextDimension
        if not hasattr(cls, "_dimension_name"):
            return
        cls._registrar[cls._dimension_name] = cls

    @classmethod
    def create(cls, dimension_name: str, raw_value: str) -> "ContextDimension":
        """
        Main constructor
        """
        # Safely get the registrar if one was initialized
        registrar = getattr(cls, "_registrar", {})
        if dimension_type := registrar.get(dimension_name):
            return dimension_type(raw_value)
        return cls.create_default(raw_value, dimension_name=dimension_name)

    @classmethod
    def create_default(cls, raw_value: str, *, dimension_name: str) -> "ContextDimension":
        """
        The default :py:class:`ContextDimension` if none were found in the :py:attr:`_registrar`.
        """
        return cls._default_dimension_cls(raw_value, dimension_name=dimension_name)

    def operate(self, operator: str, other: str) -> bool:
        if operator not in self.operators.registrar:
            raise NotImplementedError
        return self.operators.execute(operator, self, other)

    @operators.add("==", "!=")
    @abstractmethod
    def _op_eq(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("<")
    @abstractmethod
    def _op_less(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("<=")
    @abstractmethod
    def _op_less_or_equal(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add(">")
    @abstractmethod
    def _op_greater(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add(">=")
    @abstractmethod
    def _op_greater_or_equal(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("~=", "~!=")
    @abstractmethod
    def _op_minor_eq(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("~<")
    @abstractmethod
    def _op_minor_less(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("~<=")
    @abstractmethod
    def _op_minor_less_or_equal(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("~>")
    @abstractmethod
    def _op_minor_greater(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("~>=")
    @abstractmethod
    def _op_minor_greater_or_equal(self, other: str) -> bool:
        raise NotImplementedError

    @operators.add("~", "!~")
    @abstractmethod
    def _op_match(self, other: str) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class DefaultContextDimension(ContextDimension["ContextValue"]):
    #: Whether the context dimensions are compared in a case sensitive way
    case_sensitive: ClassVar[bool] = True

    #: Dynamic dimension name
    dimension_name: str = field(kw_only=True)

    @property
    def name(self) -> str:
        return self.dimension_name

    @classmethod
    def _make_value(cls, raw_value: str) -> "ContextValue":
        return ContextValue(raw_value)

    def _op_eq(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            ordered=False,
            case_sensitive=self.case_sensitive,
            ) == 0

    def _op_less(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) < 0

    def _op_less_or_equal(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) <= 0

    def _op_greater(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) > 0

    def _op_greater_or_equal(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) >= 0

    def _op_minor_eq(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            minor_mode=True,
            ordered=False,
            case_sensitive=self.case_sensitive,
            ) == 0

    def _op_minor_less(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            minor_mode=True,
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) < 0

    def _op_minor_less_or_equal(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            minor_mode=True,
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) <= 0

    def _op_minor_greater(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            minor_mode=True,
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) > 0

    def _op_minor_greater_or_equal(self, other: str) -> bool:
        return self.value.version_cmp(
            self._make_value(other),
            minor_mode=True,
            ordered=True,
            case_sensitive=self.case_sensitive,
            ) >= 0

    def _op_match(self, other: str) -> bool:
        return re.search(other, self.raw_value) is not None


ContextDimension._default_dimension_cls = DefaultContextDimension


class ContextValue:
    """
    Value for dimension
    """

    def __init__(self, raw):
        """
        ContextValue("foo-1.2.3")
        ContextValue(["foo", "1", "2", "3"])
        """
        if isinstance(raw, (tuple, list)):
            self._to_compare = tuple(raw)
        else:
            self._to_compare = self._split_to_version(raw)

        # Store the original string for regexp processing
        self.raw = raw

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

    def version_cmp(self, other, minor_mode=False, ordered=True, case_sensitive=True):
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

        case_sensitive:
            False ... ignore case when comparing
            True ... case matters when comparing
        """
        if not isinstance(other, self.__class__):
            raise CannotDecide("Invalid types.")

        if len(self._to_compare) == 0 or len(other._to_compare) == 0:
            raise CannotDecide("Empty name part.")

        if not self._compare_with_case(
                self._to_compare[0], other._to_compare[0], case_sensitive=case_sensitive):
            if ordered:
                raise CannotDecide(
                    "Name parts differ, cannot compare for order.")
            return 1  # not equal
        # From here name parts are equal
        if minor_mode and len(other._to_compare) > 1:
            # right side cares about 'major'
            try:
                if not self._compare_with_case(
                        self._to_compare[1], other._to_compare[1], case_sensitive=case_sensitive):
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
            compared = self.compare(first, second, case_sensitive=case_sensitive)
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
    def compare(first, second, case_sensitive=True):
        """
        Compare two version parts
        """
        # Ideally use `from packaging import version` but we need older
        # python support too so very rough
        try:
            # convert to int
            first_version = int(first)
            second_version = int(second)
        except ValueError:
            # fallback to compare as strings
            if case_sensitive:
                first_version = first
                second_version = second
            else:
                first_version = first.casefold()
                second_version = second.casefold()
        return (
            (first_version > second_version) -
            (first_version < second_version))

    @staticmethod
    def _compare_with_case(first, second, case_sensitive=True):
        """
        Compare two values based on the case sensitivity setting.

        :param first: first value
        :param second: second value
        :param case_sensitive: If True (default), the comparison is case-sensitive.
                               If False, the comparison is case-insensitive.

        :return: True if the values match, False otherwise.
        :rtype: bool
        """
        if case_sensitive:
            return first == second
        return first.casefold() == second.casefold()

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
    """
    Represents https://fmf.readthedocs.io/en/latest/context.html
    """
    _context_dimensions: ClassVar[type[ContextDimension]] = ContextDimension

    def _op_defined(self, dimension_name, values):
        """
        'is defined' operator
        """
        return dimension_name in self._dimensions

    def _op_not_defined(self, dimension_name, values):
        """
        'is not defined' operator
        """
        return dimension_name not in self._dimensions

    def _op_core(self, dimension_name, values, operator):
        """
        Evaluate value from dimension vs target values combination

        Stop evaluation after first True outcome

        Raises CannotDecide when dimension doesn't exist or no value
        pair could be compared.
        """
        try:
            decided = False
            for dimension_value in self._dimensions[dimension_name]:
                assert isinstance(dimension_value, ContextDimension)
                for it_val in values:
                    try:
                        if dimension_value.operate(operator, it_val):
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

    # TODO: clean this up, not really necessary anymore
    #  Can't use the ContextDimension, but maybe we can use similar decorators.
    operator_map = {
        "is defined": _op_defined,
        "is not defined": _op_not_defined,
        }

    @classmethod
    @functools.cache
    def re_expression_triple(cls) -> re.Pattern[str]:
        # Triple expression: dimension operator values
        # [^=].* is necessary as .+ matches '= something'
        return re.compile(
            r"([\w-]+)"
            + r"\s*("
            + r"|".join(
                [re.escape(op) for op in cls._context_dimensions.operators.registrar])
            + r")\s*"
            + r"([^=].*)")
    # Double expression: dimension operator
    re_expression_double = re.compile(
        r"([\w-]+)" + r"\s*(" + r"|".join(["is defined", "is not defined"]) + r")"
        )

    # Simple boolean value
    re_boolean = re.compile(r"(true|false)")

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
            definition = self.parse_rule(args[0])
            # No ORs and at least one expression in AND
            if len(definition) != 1 or not definition[0]:
                raise InvalidContext()
            for dim, op, values in definition[0]:
                if op != "==":
                    raise InvalidContext()
                self._dimensions[dim] = set(
                    [self._context_dimensions.create(dim, val) for val in values])
        # Initialized with dimension=value(s)
        for dimension_name, values in kwargs.items():
            if not isinstance(values, list):
                values = [values]
            self._dimensions[dimension_name] = set(
                [self._context_dimensions.create(dimension_name, val) for val in values]
                )

    @classmethod
    def parse_rule(cls, rule):
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
        :type rule: str | bool
        :return: nested list of expressions from the rule
        :raises InvalidRule:  Syntax error in the rule
        """
        parsed_rule = []

        # Bool can come from e.g. 'when: true' but we need expression tuple
        if isinstance(rule, bool):
            return [[(None, rule, None)]]

        # Change '=' to '=='
        rule = re.sub(r"(?<!=|!|~|<|>)=(?!=)", "==", rule)
        rule_parts = cls.split_rule_to_groups(rule)
        for and_group in rule_parts:
            parsed_and_group = []
            for part in and_group:
                dimension, operator, values = cls.split_expression(
                    part)
                parsed_and_group.append((dimension, operator, values))
            if parsed_and_group:
                parsed_rule.append(parsed_and_group)
        return parsed_rule

    @classmethod
    def split_rule_to_groups(cls, rule):
        """
        Split rule into nested lists, no real parsing

        expr0 and expr1 or expr2 is split into [[expr0, expr1], [expr2]]

        :param rule: rule to split
        :type rule: str
        :raises InvalidRule: Syntax error in the rule
        """
        rule_parts = []
        for or_group in cls.re_or_split.split(rule):
            if not or_group:
                raise InvalidRule("Empty OR expression in {}.".format(rule))
            and_group = []
            for part in cls.re_and_split.split(or_group):
                part_stripped = part.strip()
                if not part_stripped:
                    raise InvalidRule(
                        "Empty AND expression in {}.".format(rule))
                and_group.append(part_stripped)
            rule_parts.append(and_group)
        return rule_parts

    @classmethod
    def split_expression(cls, expression):
        """
        Split expression to dimension name, operator and values

        When operator doesn't have right side, None is returned instead
        of the list of values.

        :param expression: expression to split
        :type expression: str
        :raises InvalidRule: When expression cannot be split, e.g. syntax error
        :return: tuple(dimension name, operator, list of values)
        :rtype: tuple(str|None, str|bool, list|None)
        """
        # true/false
        match = cls.re_boolean.match(expression)
        if match:
            # convert to bool and return expression tuple
            if match.group(1)[0].lower() == 't':
                return (None, True, None)
            else:
                return (None, False, None)
        # Triple expressions
        match = cls.re_expression_triple().match(expression)
        if match:
            dimension, operator, raw_values = match.groups()
            return (dimension, operator, [
                val.strip() for val in raw_values.split(",")])
        # Double expressions
        match = cls.re_expression_double.match(expression)
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
        :type rule: str | bool
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
        if isinstance(operator, bool):
            return operator
        if operator in self.operator_map:
            # TODO: clean this up, not really necessary anymore
            return self.operator_map[operator](self, dimension_name, values)
        else:
            return self._op_core(dimension_name, values, operator)
