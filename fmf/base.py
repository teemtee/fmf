"""
Base Metadata Classes
"""

import copy
import os
import re
import subprocess
from pprint import pformat as pretty
from typing import Any, Dict, Optional, Protocol

import fmf.context
import fmf.utils as utils
from fmf.plugins._loader import Loader
from fmf.utils import log

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ADJUST_CONTROL_KEYS = ['because', 'continue', 'when']


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Metadata
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


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
            rule: Dict[str, Any],
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


class Tree:
    """
    Metadata Tree
    """

    def __init__(self, data, name=None, parent=None, *,
                 _loader=None, _plugin=None, _inherit=True):
        """
        Initialize metadata tree from directory path or data dictionary

        Data parameter can be either a string with directory path to be
        explored or a dictionary with the values already prepared.
        """

        # Bail out if no data and no parent given
        if not data and not parent and _loader is None:
            raise utils.GeneralError(
                "No data or parent provided to initialize the tree.")

        # Initialize family relations, object data and source files
        self.parent = parent
        self.children = dict()
        self.data = dict()
        self.sources = list()
        self.root = None
        self.config = {}
        self.version = utils.VERSION
        self.original_data = dict()
        self._commit = None
        self._raw_data = dict()
        self._source_plugin = None
        self._source_node = None
        self._loader = _loader or (parent._loader if parent else Loader())
        self._plugin = _plugin or (parent._plugin if parent else self._loader.dictionary)
        self._layers = []
        self._pending_layers = False
        # Track whether the data dictionary has been updated
        # (needed to prevent removing nodes with an empty dict).
        self._updated = False

        # Special directives
        self._directives = dict()

        if self.parent is None:
            self.name = "/"
        else:
            self.root = self.parent.root
            self.config = self.parent.config
            self.name = self.parent.name.rstrip('/') + '/' + name

        self._loader.load(self, data)

        # Apply inheritance when all scattered data are gathered.
        # This is done only once, from the top parent object.
        if self.parent is None and _inherit:
            self.inherit()

        log.debug("New tree '{0}' created.".format(self))

    @property
    def commit(self):
        """
        Commit hash if tree grows under a git repo, False otherwise

        Return current commit hash if the metadata tree root is located
        under a git repository. For metadata initialized from a dict or
        local directory with no git repo 'False' is returned instead.
        """
        if self._commit is not None:
            return self._commit

        # No root, no commit (tree parsed from a dictionary)
        if self.root is None:
            self._commit = False
            return self._commit

        # Check root directory for current commit
        try:
            output, _ = utils.run(
                ['git', 'rev-parse', '--verify', 'HEAD'], cwd=self.root)
            self._commit = output.strip()
        except subprocess.CalledProcessError:
            self._commit = False
        return self._commit

    def __str__(self):
        """
        Use tree name as identifier
        """

        return self.name

    def _initialize(self, path):
        self._loader.initialize(self, path)

    def _merge_special(self, data, source):
        self._plugin.merge(self, data, source)

    def _process_directives(self, directives):
        """
        Check and process special fmf directives
        """

        def check(value, type_, name=None):
            """
            Check for correct type
            """

            if not isinstance(value, type_):
                name = f" '{name}'" if name else ""
                raise fmf.utils.FormatError(
                    f"Invalid fmf directive{name} in '{self.name}': "
                    f"Should be a '{type_.__name__}', "
                    f"got a '{type(value).__name__}' instead.")

        # Directives should be a directory
        check(directives, dict)

        # Check for proper values
        for key, value in directives.items():
            if key == "inherit":
                check(value, bool, name="inherit")
            elif key == "select":
                check(value, bool, name="select")
            else:
                # No other directive supported
                raise fmf.utils.FormatError(
                    f"Unknown fmf directive '{key}' in '{self.name}'.")

        # Everything ok, store the directives
        self._directives.update(directives)

    @staticmethod
    def init(path):
        """Create metadata tree root under given path."""
        return Loader().init(path)

    def merge(self, parent=None):
        """
        Merge parent data
        """

        # Check parent
        if parent is None:
            parent = self.parent
        if self._directives.get("inherit") is False or parent is None:
            # Nothing to inherit
            data = {}
        else:
            self.sources = parent.sources + self.sources
            data = copy.deepcopy(parent.data)
        self._loader.merge(self, data)
        self.data = data

    def inherit(self):
        """
        Apply inheritance
        """

        # Preserve original data and merge parent
        # (original data needed for custom inheritance extensions)
        self.original_data = self.data
        self.merge()
        log.debug("Data for '{0}' inherited.".format(self))
        log.data(pretty(self.data))
        # Apply inheritance to all children
        for child in self.children.values():
            child.inherit()

    def update(self, data):
        """Update raw metadata using this node's backend."""
        self._plugin.update(self, data)

    def adjust(
            self,
            context,
            key='adjust',
            undecided='skip',
            case_sensitive: Optional[bool] = None,
            decision_callback: Optional[AdjustCallback] = None,
            additional_rules=None,
            additional_rules_callback: Optional[ApplyRulesCallback] = None):
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
            rules = self.data[key]
            log.debug("Applying adjust rules for '{}'.".format(self))
            log.data(rules)
            if isinstance(rules, dict):
                rules = [rules]
            if not isinstance(rules, list):
                raise utils.FormatError(
                    "Invalid adjust rule format in '{}'. "
                    "Should be a dictionary or a list of dictionaries, "
                    "got '{}'.".format(self.name, type(rules).__name__))
        except KeyError:
            rules = []

        # Accept same type as rules from data
        if additional_rules is None:
            additional_rules = []
        elif isinstance(additional_rules, dict):
            additional_rules = [additional_rules]

        def apply_rules(rule_set):
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
                            decision_callback(self, rule, True)

                        # Remove special keys (when, because...) from the rule
                        apply_rule = {
                            key: value
                            for key, value in rule.items()
                            if key not in ADJUST_CONTROL_KEYS
                            }
                        self._merge_special(self.data, apply_rule)

                        # First matching rule wins, skip the rest of this set unless continue
                        if not continue_:
                            break
                    else:
                        if decision_callback:
                            decision_callback(self, rule, False)
                # Handle undecided rules as requested
                except fmf.context.CannotDecide:
                    if decision_callback:
                        decision_callback(self, rule, None)

                    if undecided == 'skip':
                        continue
                    elif undecided == 'raise':
                        raise
                    else:
                        raise utils.GeneralError(
                            "Invalid value for the 'undecided' parameter. Should "
                            "be 'skip' or 'raise', got '{}'.".format(undecided))

        # Always process rules from 'key' (adjust)
        apply_rules(rules)
        # Additional rules might be skipped depending on the callback
        if additional_rules_callback is None or additional_rules_callback(self):
            apply_rules(additional_rules)

        # Adjust all child nodes as well
        for child in self.children.values():
            child.adjust(context, key, undecided,
                         case_sensitive=case_sensitive,
                         decision_callback=decision_callback,
                         additional_rules=additional_rules,
                         additional_rules_callback=additional_rules_callback)

    def get(self, name=None, default=None):
        """
        Get attribute value or return default

        Whole data dictionary is returned when no attribute provided.
        Supports direct values retrieval from deep dictionaries as well.
        Dictionary path should be provided as list. The following two
        examples are equal:

        tree.data['hardware']['memory']['size']
        tree.get(['hardware', 'memory', 'size'])

        However the latter approach will also correctly handle providing
        default value when any of the dictionary keys does not exist.

        """

        # Return the whole dictionary if no attribute specified
        if name is None:
            return self.data
        if not isinstance(name, list):
            name = [name]
        data = self.data
        try:
            for key in name:
                data = data[key]
        except KeyError:
            return default
        return data

    def child(self, name, data, source=None):
        """Create or update a child through the input backend."""
        self._loader.child(self, name, data, source)

    @property
    def explore_include(self):
        """Additional hidden sources included by the tree's root backend."""
        return self._loader.explore_include(self)

    def grow(self, path):
        """Collect raw hierarchies, retaining merge operations until inheritance."""
        self._loader.grow(self, path)

    def climb(self, whole: bool = False, sort: bool = True):
        """
        Climb through the tree (iterate over nodes)

        :param whole: By default only leaf nodes are considered. When
            set to ``True`` all nodes are iterated, including parent
            branches.

        :param sort: When iterating, child nodes are sorted by name by
            default. Set to ``False`` if you prefer to keep the order in
            which the child nodes were inserted into the tree.
        """

        # Include branches when `whole` is enabled or the `select`
        # directive has been used to pick this node.
        if whole or self.select:
            yield self

        # Sort child nodes by name only if requested
        if sort:
            children = [child for _, child in sorted(self.children.items())]
        else:
            children = self.children.values()

        # Iterate through each child node
        for child in children:
            for node in child.climb(whole=whole, sort=sort):
                yield node

    @property
    def select(self):
        """
        Respect directive, otherwise by being leaf/branch node
        """

        try:
            return self._directives["select"]
        except KeyError:
            return not self.children

    def find(self, name):
        """
        Find node with given name
        """

        for node in self.climb(whole=True):
            if node.name == name:
                return node
        return None

    def prune(
            self,
            whole: bool = False,
            keys: Optional[list[str]] = None,
            names: Optional[list[str]] = None,
            filters: Optional[list[str]] = None,
            conditions: Optional[list[str]] = None,
            sources: Optional[list[str]] = None,
            sort: bool = True):
        """
        Filter tree nodes based on given criteria

        :param whole: By default only leaf nodes are considered. When
            set to ``True`` all nodes are iterated, including parent
            branches.

        :param keys: Include only nodes containing given keys.

        :param names: Include only nodes matching provided names.

        :param filters: Include only nodes matching given filters.

        :param conditions: Include only nodes satisfying the conditions.

        :param sources: Filter by source fmf file names on disk.

        :param sort: When iterating, child nodes are sorted by name by
            default. Set to ``False`` if you prefer to keep the order in
            which the child nodes were inserted into the tree.
        """

        keys = keys or []
        names = names or []
        filters = filters or []
        conditions = conditions or []

        # Expand paths to absolute
        if sources:
            sources = {os.path.abspath(src) for src in sources}

        for node in self.climb(whole, sort=sort):
            # Select only nodes with key content
            if not all([key in node.data for key in keys]):
                continue
            # Select nodes with name matching regular expression
            if names and not any(
                    [re.search(name, node.name) for name in names]):
                continue
            # Select nodes defined by any of the source files
            if sources and not sources.intersection(node.sources):
                continue
            # Apply filters and conditions if given
            try:
                if not all([utils.filter(filter, node.data, regexp=True, name=node.name)
                            for filter in filters]):
                    continue
                if not all([utils.evaluate(condition, node.data, node)
                            for condition in conditions]):
                    continue
            # Handle missing attribute as if filter failed
            except utils.FilterError:
                continue
            # All criteria met, thus yield the node
            yield node

    def show(self, brief=False, formatting=None, values=None):
        """
        Show metadata
        """

        values = values or []

        # Custom formatting
        if formatting is not None:
            formatting = re.sub("\\\\n", "\n", formatting)
            name = self.name        # noqa: F841
            data = self.data        # noqa: F841
            root = self.root        # noqa: F841
            sources = self.sources  # noqa: F841
            evaluated = []
            for value in values:
                evaluated.append(eval(value))
            return formatting.format(*evaluated)

        # Show the name
        output = utils.color(self.name, 'red')
        if brief or not self.data:
            return output + "\n"
        # List available attributes
        for key, value in sorted(self.data.items()):
            output += "\n{0}: ".format(utils.color(key, 'green'))
            if isinstance(value, str):
                output += value.rstrip("\n")
            elif isinstance(value, list) and all(
                    [isinstance(item, str) for item in value]):
                output += utils.listed(value)
            else:
                output += pretty(value)
            output
        return output + "\n"

    @staticmethod
    def node(reference):
        """
        Return Tree node referenced by the fmf identifier

        Keys supported in the reference:

        url .... git repository url (optional)
        ref .... branch, tag or commit (default branch if not provided)
        path ... metadata tree root ('.' by default)
        name ... tree node name ('/' by default)

        See the documentation for the full fmf id specification:
        https://fmf.readthedocs.io/en/latest/concept.html#identifiers
        Raises ReferenceError if referenced node does not exist.
        """

        # Fetch remote git repository
        if 'url' in reference:
            tree = utils.fetch_tree(
                reference.get('url'),
                reference.get('ref'),
                reference.get('path', '.').lstrip('/'))
        # Use local files
        else:
            root = reference.get('path', '.')
            if not root.startswith('/') and root != '.':
                raise utils.ReferenceError(
                    'Relative path "%s" specified.' % root)
            tree = Tree(root)
        found_node = tree.find(reference.get('name', '/'))
        if found_node is None:
            raise utils.ReferenceError(
                "No tree node found for '{0}' reference".format(reference))
        return found_node

    def copy(self):
        """
        Create and return a deep copy of the node and its subtree

        It is possible to call copy() on any node in the tree, not
        only on the tree root node. Note that in that case, parent
        node and the rest of the tree attached to it is not copied
        in order to save memory.
        """

        original_parent = self.parent
        self.parent = None
        duplicate = copy.deepcopy(self)
        self.parent = duplicate.parent = original_parent
        return duplicate

    def validate(self, schema, schema_store=None):
        """
        Validate node data with given JSON Schema and schema references.

        schema_store is a dict of schema references and their content.

        Return a named tuple utils.JsonSchemaValidationResult
        with the following two items:

          result ... boolean representing the validation result
          errors ... A list of validation errors

        Raises utils.JsonSchemaError if the supplied schema was invalid.
        """

        return utils.validate_data(self.data, schema, schema_store=schema_store)

    def __enter__(self):
        """
        Experimental: Modify metadata and store changes to disk

        The source-owning backend supplies editable raw data and stores
        changes on exit. A read-only backend can delegate storage to an
        overlay backend. Dictionary trees retain edits in memory.

        Direct source editing exposes raw data without inheritance or
        elasticity. An overlay backend may instead materialize effective
        metadata; see its storage documentation. For example, if you
        have defined "key+: value" in the file for node and you will add
        "key: other" it will result into "othervalue".

        Example usage:

            with Tree('.').find('/tests/core/smoke') as test:
                test['tier'] = 0

        Native FMF writes strip white space and comments as YAML export
        does not preserve this information. The feature
        is experimental and can be later modified, use at your own risk.
        """

        self._editor, self._edit_node = self._loader.edit(self)
        return self._editor.read(self._edit_node)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Experimental: Store modified metadata to disk
        """

        self._editor.write(self._edit_node)

    def __getitem__(self, key):
        """
        Dictionary method to get child node or data item

        To get a child the key has to start with a '/'.
        as identification of child item string
        """

        if key.startswith("/"):
            return self.children[key[1:]]
        else:
            return self.data[key]
