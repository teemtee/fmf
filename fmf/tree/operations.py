"""Operations for transforming in-memory metadata trees."""

import copy
import re
from typing import TYPE_CHECKING, Any, List, Optional, Protocol, Union

import fmf.context

if TYPE_CHECKING:
    from fmf.base import Tree
import fmf.utils as utils
from fmf.utils import log

# TODO: Refine the adjust rule type using a TypedDict or a better construct
AdjustRule = dict[str, Any]
# One adjust rule or a list of adjust rules
AdjustRules = Union[AdjustRule, List[AdjustRule]]
# Dictionary with node metadata, arbitrary keys and values
MergeData = dict[str, Any]


class AdjustCallback(Protocol):
    """
    A callback for per-rule notifications made by Tree.adjust()

    Function which will be called for every rule inspected by adjust().
    It will be given three arguments: fmf tree being inspected,
    current adjust rule, and whether the rule was skipped (``None``),
    applied (``True``) or not applied (``False``).
    """

    def __call__(
            self,
            node: 'Tree',
            rule: AdjustRule,
            applied: Optional[bool]) -> None:
        pass


class ApplyRulesCallback(Protocol):
    """
    A callback to decide if rules should be processed in Tree.adjust()

    Function to be called for every node before ``additional_rules``
    are processed. It is called with fmf tree as the parameter.
    It should return ``True`` when additional_rules should be processed
    or ``False`` when they should be ignored.
    """

    def __call__(
            self,
            node: 'Tree') -> bool:
        return True


class Merger:
    """Merge metadata dictionaries."""

    def merge(self, node: 'Tree', parent: Optional['Tree'] = None) -> None:
        """
        Merge parent data into node

        :param node: the node to merge data into, updated in-place;
            its raw data are merged on top of the parent data
        :param parent: the parent node to inherit data from,
            defaults to ``node.parent`` when not provided
        """
        if parent is None:
            parent = node.parent
        if node._directives.get("inherit") is False or parent is None:
            data = {}
        else:
            node.sources = parent.sources + node.sources
            data = copy.deepcopy(parent.data)
        self._merge_special(data, node.data, node.name)
        node.data = data

    def _merge_plus(self, data: MergeData, key: str, value: Any, name: str,
                    prepend: bool = False) -> None:
        """
        Handle extending attributes using the '+' suffix
        """

        # Set the value if key is not present
        if key not in data:
            data[key] = value
            return

        # Parent is a list of dict and child is a dict
        # (just update every parent list item using the special merge)
        if isinstance(data[key], list) and isinstance(value, dict):
            for list_item in data[key]:
                if not isinstance(list_item, dict):
                    raise utils.MergeError(
                        "MergeError: Item '{0}' in {1} must be a dictionary.".format(
                            list_item, name))
                self._merge_special(list_item, value, name)
            return

        # Parent is a dict and child is a list of dict
        # (replace parent dict with the list of its special-merged copies)
        if isinstance(data[key], dict) and isinstance(value, list):
            result_list = []
            for list_item in value:
                if not isinstance(list_item, dict):
                    raise utils.MergeError(
                        "MergeError: Item '{0}' in {1} must be a dictionary.".format(
                            list_item, name))
                result_dict = copy.deepcopy(data[key])
                self._merge_special(result_dict, list_item, name)
                result_list.append(result_dict)
            data[key] = result_list
            return

        # Use the special merge for merging dictionaries
        if isinstance(data[key], dict) and isinstance(value, dict):
            self._merge_special(data[key], value, name)
            return

        # Attempt to apply the plus operator
        try:
            if prepend:
                data[key] = value + data[key]
            else:
                data[key] = data[key] + value
        except TypeError as error:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} ({2}).".format(
                    key, name, str(error)))

    def _merge_regexp(self, data: MergeData, key: str, value: Any, name: str) -> None:
        """
        Handle substitution of current values
        """

        # Nothing to substitute if the key is not present in parent
        if key not in data:
            return
        if isinstance(value, str):
            value = [value]
        for pattern, replacement in [utils.split_pattern_replacement(v) for v in value]:
            if isinstance(data[key], list):
                try:
                    data[key] = [re.sub(pattern, replacement, original) for original in data[key]]
                except TypeError:
                    raise utils.MergeError(
                        "MergeError: Key '{0}' in {1} (not a string).".format(
                            key, name))
            elif isinstance(data[key], str):
                data[key] = re.sub(pattern, replacement, data[key])
            else:
                raise utils.MergeError(
                    "MergeError: Key '{0}' in {1} (wrong type).".format(
                        key, name))

    def _merge_minus_regexp(self, data: MergeData, key: str, value: Any, name: str) -> None:
        """
        Handle removing current values if they match regexp
        """

        # A bit faster but essentially `any`
        def lazy_any_search(item, patterns):
            for p in patterns:
                if re.search(p, str(item)):
                    return True
            return False
        # Nothing to remove if the key is not present in parent
        if key not in data:
            return
        if isinstance(value, str):
            value = [value]
        if isinstance(data[key], list):
            data[key] = [item for item in data[key] if not lazy_any_search(item, value)]
        elif isinstance(data[key], str):
            if lazy_any_search(data[key], value):
                data[key] = ''
        elif isinstance(data[key], dict):
            for k in list(data[key].keys()):
                if lazy_any_search(k, value):
                    data[key].pop(k)
        else:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} (wrong type).".format(
                    key, name))

    def _merge_minus(self, data: MergeData, key: str, value: Any, name: str) -> None:
        """
        Handle reducing attributes using the '-' suffix
        """

        # Cannot reduce attribute if key is not present in parent
        if key not in data:
            return
        # Subtract numbers
        if isinstance(data[key], (int, float)) and isinstance(value, (int, float)):
            data[key] = data[key] - value
        # Replace matching regular expression with empty string
        elif isinstance(data[key], str) and isinstance(value, str):
            data[key] = re.sub(value, '', data[key])
        # Remove given values from the parent list
        elif isinstance(data[key], list) and isinstance(value, list):
            data[key] = [item for item in data[key] if item not in value]
        # Remove given key from the parent dictionary
        elif isinstance(data[key], dict) and isinstance(value, list):
            for item in value:
                data[key].pop(item, None)
        else:
            raise utils.MergeError(
                "MergeError: Key '{0}' in {1} (wrong type).".format(
                    key, name))

    def _merge_special(self, data: MergeData, source: MergeData, name: str) -> None:
        """
        Merge source dict into data, handle special suffixes

        :param data: the result dictionary accumulated so far
            (based on the parent data), mutated in-place
        :param source: the raw data being merged in
        :param name: node name, used in error messages only
        """

        for key, value in source.items():
            # Handle special attribute merging
            if key.endswith('+'):
                self._merge_plus(data, key.rstrip('+'), value, name)
            elif key.endswith('+<'):
                self._merge_plus(data, key.rstrip('+<'), value, name, prepend=True)
            elif key.endswith('-~'):
                self._merge_minus_regexp(data, key.rstrip('-~'), value, name)
            elif key.endswith('-'):
                self._merge_minus(data, key.rstrip('-'), value, name)
            elif key.endswith('~'):
                self._merge_regexp(data, key.rstrip('~'), value, name)
            # Otherwise just update the value
            else:
                data[key] = value


class Adjuster:
    """Transform an already loaded tree for a particular context."""

    CONTROL_KEYS: List[str] = ['because', 'continue', 'when']

    # TODO: The adjust options (key, undecided, case_sensitive,
    # decision_callback, additional_rules and additional_rules_callback)
    # could be stored as Adjuster attributes instead of being passed
    # on every call
    def adjust(
            self,
            node: 'Tree',
            context: 'fmf.context.Context',
            key: str = 'adjust',
            undecided: str = 'skip',
            case_sensitive: Optional[bool] = None,
            decision_callback: Optional[AdjustCallback] = None,
            additional_rules: Optional[AdjustRules] = None,
            additional_rules_callback: Optional[ApplyRulesCallback] = None) -> None:
        """
        Adjust tree data based on provided context and rules

        The 'context' should be an instance of the fmf.context.Context
        class describing the environment context. By default, the key
        'adjust' of each node is inspected for possible rules that
        should be applied. Provide 'key' to use a custom key instead.

        Optional 'undecided' parameter can be used to specify what
        should happen when a rule condition cannot be decided because
        context dimension is not defined. By default, such rules are
        skipped. In order to raise the fmf.context.CannotDecide
        exception in such cases use undecided='raise'.

        Optional 'decision_callback' callback would be called for every adjust
        rule inspected, with three arguments: current fmf node, current
        adjust rule, and whether it was applied or not.

        Optional 'additional_rules' parameter can be used to specify rules
        that should be applied after those from the node itself.
        These additional rules are processed even when an applied
        rule defined in the node has ``continue: false`` set.

        Optional 'additional_rules_callback' callback could be set to
        limit nodes for which 'additional_rules' are processed. This
        callback is called with the current fmf node as an argument and
        should return 'True' to process 'additional_rules' or 'False' to
        skip them.
        """

        # Check context sanity
        if not isinstance(context, fmf.context.Context):
            raise utils.GeneralError(
                "Invalid adjust context: '{}'.".format(type(context).__name__))

        # TODO: Remove this in next release
        if case_sensitive is not None:
            context._context_dimensions._default_dimension_cls.case_sensitive = case_sensitive

        # Adjust rules should be a dictionary or a list of dictionaries
        try:
            rules = node.data[key]
            log.debug("Applying adjust rules for '{}'.".format(node))
            log.data(rules)
            if isinstance(rules, dict):
                rules = [rules]
            if not isinstance(rules, list):
                raise utils.FormatError(
                    "Invalid adjust rule format in '{}'. "
                    "Should be a dictionary or a list of dictionaries, "
                    "got '{}'.".format(node.name, type(rules).__name__))
        except KeyError:
            rules = []

        # Accept same type as rules from data
        if additional_rules is None:
            additional_rules = []
        elif isinstance(additional_rules, dict):
            additional_rules = [additional_rules]

        # Always process rules from 'key' (adjust)
        self._apply_rules(rules, node, context, undecided, decision_callback)
        # Additional rules might be skipped depending on the callback
        if additional_rules_callback is None or additional_rules_callback(node):
            self._apply_rules(
                additional_rules, node, context, undecided, decision_callback)

        # Adjust all child nodes as well
        for child in node.children.values():
            self.adjust(child, context, key, undecided,
                        case_sensitive=case_sensitive,
                        decision_callback=decision_callback,
                        additional_rules=additional_rules,
                        additional_rules_callback=additional_rules_callback)

    def _apply_rules(
            self,
            rule_set: List[AdjustRule],
            node: 'Tree',
            context: 'fmf.context.Context',
            undecided: str,
            decision_callback: Optional[AdjustCallback]) -> None:
        """
        Apply a set of adjust rules to node.
        """
        # 'continue' has to affect only its rule_set
        for rule in rule_set:
            # Rule must be a dictionary
            if not isinstance(rule, dict):
                raise utils.FormatError("Adjust rule should be a dictionary.")

            # Missing 'when' means always enabled rule
            try:
                condition = rule['when']
            except KeyError:
                condition = True

            # The optional 'continue' key should be a bool
            continue_ = rule.get('continue', True)
            if not isinstance(continue_, bool):
                raise utils.FormatError(
                    "The 'continue' value should be bool, "
                    "got '{}'.".format(continue_))

            # Apply remaining rule attributes if context matches
            try:
                if context.matches(condition):
                    if decision_callback:
                        decision_callback(node, rule, True)

                    # Remove special keys (when, because...) from the rule
                    apply_rule = {
                        key: value
                        for key, value in rule.items()
                        if key not in self.CONTROL_KEYS
                        }
                    node._merger._merge_special(node.data, apply_rule, node.name)

                    # First matching rule wins, skip the rest of this set unless continue
                    if not continue_:
                        break
                else:
                    if decision_callback:
                        decision_callback(node, rule, False)
            # Handle undecided rules as requested
            except fmf.context.CannotDecide:
                if decision_callback:
                    decision_callback(node, rule, None)

                if undecided == 'skip':
                    continue
                elif undecided == 'raise':
                    raise
                else:
                    raise utils.GeneralError(
                        "Invalid value for the 'undecided' parameter. Should "
                        "be 'skip' or 'raise', got '{}'.".format(undecided))
