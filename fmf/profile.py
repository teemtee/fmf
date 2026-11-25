from copy import deepcopy
from fmf.context import Context
#from fmf.base import Tree

class ProfileError(Exception):
    pass


class ProfileWithoutWhereStatement(ProfileError):
    pass


class Profile:

    def __init__(self, rule: dict, name = None):
        self._raw_rule = rule
        self.name = name
        if "where" not in self._raw_rule.keys():
            raise ProfileWithoutWhereStatement
        self.where = self._raw_rule.pop("where")
        self.rules = deepcopy(self._raw_rule)

    def _check_if_fmf_node_match(self, node):
        context = Context(**node.data)
        return context.matches(self.where)

    def _apply_rule(self, node):

        if not self._check_if_fmf_node_match(node):
            return
        for rule in self.rules:
            if isinstance(rule, str) and rule.endswith("?"):
                rule_clear = rule[:-1]
                data = {rule_clear : self.rules[rule]}
                if rule_clear in node.data:
                    # do not override if defined
                    continue
            else:
                data = {rule: self.rules[rule]}
            node._merge_special(node.data, data)

    def apply_rule(self, node):
        for item in node.climb():
            self._apply_rule(item)