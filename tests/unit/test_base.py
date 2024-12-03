import os
import queue
import tempfile
import threading
import time
from shutil import rmtree

import pytest
from ruamel.yaml import YAML

import fmf.cli
import fmf.utils as utils
from fmf.base import ADJUST_CONTROL_KEYS, Tree
from fmf.context import Context

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLES = PATH + "/../../examples/"
SELECT_SOURCE = os.path.join(PATH, "data/select_source")
FMF_REPO = 'https://github.com/psss/fmf.git'


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Tree
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class TestTree:
    """ Tree class """

    def setup_method(self, method):
        """ Load examples """
        self.wget = Tree(EXAMPLES + "wget")
        self.merge = Tree(EXAMPLES + "merge")

    def test_basic(self):
        """ No directory path given """
        with pytest.raises(utils.GeneralError):
            Tree("")
        with pytest.raises(utils.GeneralError):
            Tree(None)
        with pytest.raises(utils.RootError):
            Tree("/")

    def test_hidden(self):
        """ Hidden files and directories """
        assert ".hidden" not in self.wget.children
        hidden = Tree(EXAMPLES + "hidden")
        plan = hidden.find("/.plans/basic")
        assert plan.get("discover") == {"how": "fmf"}

    def test_inheritance(self):
        """ Inheritance and data types """
        deep = self.wget.find('/recursion/deep')
        assert deep.data['depth'] == 1000
        assert deep.data['description'] == 'Check recursive download options'
        assert deep.data['tags'] == ['Tier2']

    def test_scatter(self):
        """ Scattered files """
        scatter = Tree(EXAMPLES + "scatter").find("/object")
        assert len(list(scatter.climb())) == 1
        assert scatter.data['one'] == 1
        assert scatter.data['two'] == 2
        assert scatter.data['three'] == 3

    def test_scattered_inheritance(self):
        """ Inheritance of scattered files """
        grandson = Tree(EXAMPLES + "child").find("/son/grandson")
        assert grandson.data['name'] == 'Hugo'
        assert grandson.data['eyes'] == 'blue'
        assert grandson.data['nose'] == 'long'
        assert grandson.data['hair'] == 'fair'

    def test_subtrees(self):
        """ Subtrees should be ignored """
        child = Tree(EXAMPLES + "child")
        assert child.find("/nobody") is None

    def test_prune_sources(self):
        """ Pruning by sources """
        original_directory = os.getcwd()
        # Change directory to make relative paths work
        os.chdir(SELECT_SOURCE)
        tree = Tree('.')
        # /foo/special is inherit: false
        found = tree.prune(sources=['main.fmf'])
        assert {node.name for node in found} == set(['/virtual', '/foo/inner'])
        # All three objects are found
        found = tree.prune(sources=['main.fmf', 'foo/special.fmf'])
        assert {node.name for node in found} == set(
            ['/virtual', '/foo/special', '/foo/inner'])
        # Filter by filter (key, condition..) still works
        found = tree.prune(
            filters=['attribute:something'],
            sources=['main.fmf', 'foo/special.fmf'])
        assert [tree.find('/foo/inner')] == list(found)
        os.chdir(original_directory)

    def test_empty(self):
        """ Empty structures should be ignored """
        child = Tree(EXAMPLES + "empty")
        assert child.find("/nothing") is None
        assert child.find("/zero") is not None

    def test_none_key(self):
        """ Handle None keys """
        with pytest.raises(utils.FormatError):
            Tree({None: "weird key"})

    def test_control_keys(self):
        """ No special handling outside adjust """
        child_data = {k: str(v) for v, k in enumerate(ADJUST_CONTROL_KEYS)}
        tree = Tree({
            'key': 'value',
            '/child': child_data
            })
        expected = {'key': 'value'}
        expected.update(child_data)
        assert tree.find('/child').data == expected

    def test_adjust_strips_control_keys(self):
        """ They are not merged during adjust """
        tree = Tree({'adjust': [
            {
                'because': 'reasons',
                'foo': 'bar'
                }
            ],
            '/child': {}
            })
        tree.adjust(context=Context())
        child = tree.find('/child')
        assert 'because' not in child.data
        assert 'foo' in child.data

    def test_deep_hierarchy(self):
        """ Deep hierarchy on one line """
        deep = Tree(EXAMPLES + "deep")
        assert len(deep.children) == 3

    def test_deep_dictionary(self):
        """ Get value from a deep dictionary """
        deep = Tree(EXAMPLES + "deep")
        assert deep.data['hardware']['memory']['size'] == 8
        assert deep.get(['hardware', 'memory', 'size']) == 8
        assert deep.get(['hardware', 'bad', 'size'], 12) == 12
        assert deep.get('nonexistent', default=3) == 3

    def test_deep_dictionary_undefined_keys(self):
        """ Extending undefined keys using '+' should work """
        deep = Tree(EXAMPLES + "deep")
        single = deep.find("/single")
        assert single.get(["undefined", "deeper", "key"]) == "value"
        child = deep.find("/parent/child")
        assert child.get("one") == 2
        assert child.get("two") == 4
        assert child.get("three") == 3
        assert child.get(["undefined", "deeper", "key"]) == "value"

    def test_merge_plus(self):
        """ Extending attributes using the '+' suffix """
        child = self.merge.find('/parent/extended')
        assert 'General' in child.data['description']
        assert 'Specific' in child.data['description']
        assert child.data['tags'] == ['Tier0', 'Tier1', 'Tier2', 'Tier3']
        assert child.data['time'] == 15
        assert child.data['vars'] == dict(x=1, y=2, z=3)
        assert child.data['disabled'] is True
        assert 'time+' not in child.data
        with pytest.raises(utils.MergeError):
            child.data["time+"] = "string"
            child.inherit()

    def test_merge_plus_parent_dict(self):
        """ Merging parent dict with child list """
        child = self.merge.find('/parent-dict/path')
        assert len(child.data['discover']) == 2
        assert child.data['discover'][0]['how'] == 'fmf'
        assert child.data['discover'][0]['name'] == 'upstream'
        assert child.data['discover'][0]['url'] == 'https://some.url'
        assert child.data['discover'][0]['summary'] == 'test.upstream'
        assert child.data['discover'][1]['how'] == 'fmf'
        assert child.data['discover'][1]['name'] == 'downstream'
        assert child.data['discover'][1]['url'] == 'https://other.url'
        assert child.data['discover'][1]['summary'] == 'test.downstream'

    def test_merge_plus_parent_list(self):
        """ Merging parent list with child dict """
        for i in [1, 2]:
            child = self.merge.find(f'/parent-list/tier{i}')
            assert child.data['summary'] == 'basic tests' if i == 1 else 'detailed tests'
            assert len(child.data['discover']) == 2
            assert child.data['discover'][0]['filter'] == f'tier: {i}'
            assert child.data['discover'][0]['url'] == 'https://github.com/project1'
            assert child.data['discover'][0]['summary'] == f'project1.tier{i}'
            assert child.data['discover'][1]['filter'] == f'tier: {i}'
            assert child.data['discover'][1]['url'] == 'https://github.com/project2'
            assert child.data['discover'][1]['summary'] == f'project2.tier{i}'

    def test_merge_minus(self):
        """ Reducing attributes using the '-' suffix """
        child = self.merge.find('/parent/reduced')
        assert 'General' in child.data['description']
        assert 'description' not in child.data['description']
        assert child.data['tags'] == ['Tier1']
        assert child.data['time'] == 5
        assert child.data['vars'] == dict(x=1)
        assert 'time+' not in child.data
        # Do not raise MergeError if key is missing
        child.data["pkgs-"] = 'foo'
        child.inherit()
        assert 'pkgs-' not in child.data
        with pytest.raises(utils.MergeError):
            child.data["time-"] = "bad"
            child.inherit()

    def test_merge_regexp(self):
        """ Do re.sub during the merge """
        child = self.merge.find('/parent/regexp')
        assert 'general' == child.data['description']
        # First rule changes the Tier2 into t2,
        # thus /Tier2/t3/ no longer matches.
        assert ['t1', 't2'] == child.data['tags']

    def test_merge_minus_regexp(self):
        """ Merging with '-~' operation """
        child = self.merge.find('/parent/minus-regexp')
        assert '' == child.data['description']
        assert ['Tier2'] == child.data['tags']
        assert {'x': 1} == child.data['vars']

    def test_merge_deep(self):
        """ Merging a deeply nested dictionary """
        child = self.merge.find('/parent/buried')
        assert child.data['very']['deep']['dict'] == dict(x=2, y=1, z=0)

    def test_merge_order(self):
        """ Inheritance should be applied in the given order """
        child = self.merge.find('/parent/order/add-first')
        assert child.data['tag'] == ['one', 'four']
        child = self.merge.find('/parent/order/remove-first')
        assert child.data['tag'] == ['one', 'three', 'four']

    def test_get(self):
        """ Get attributes """
        assert isinstance(self.wget.get(), dict)
        assert 'Petr' in self.wget.get('tester')

    def test_show(self):
        """ Show metadata """
        assert isinstance(self.wget.show(brief=True), str)
        assert self.wget.show(brief=True).endswith("\n")
        assert isinstance(self.wget.show(), str)
        assert self.wget.show().endswith("\n")
        assert 'tester' in self.wget.show()

    def test_update(self):
        """ Update data """
        data = self.wget.get()
        self.wget.update(None)
        assert self.wget.data == data

    def test_find_node(self):
        """ Find node by name """
        assert self.wget.find("non-existent") is None
        protocols = self.wget.find('/protocols')
        assert isinstance(protocols, Tree)

    def test_find_root(self):
        """ Find metadata tree root """
        tree = Tree(os.path.join(EXAMPLES, "wget", "protocols"))
        assert tree.find("/download/test")

    def test_yaml_syntax_errors(self):
        """ Handle YAML syntax errors """
        path = tempfile.mkdtemp()
        fmf.cli.main("fmf init", path)
        with open(os.path.join(path, "main.fmf"), "w") as main:
            main.write("missing\ncolon:")
        with pytest.raises(utils.FileError):
            fmf.Tree(path)
        rmtree(path)

    def test_yaml_duplicate_keys(self):
        """ Handle YAML duplicate keys """
        path = tempfile.mkdtemp()
        fmf.cli.main("fmf init", path)

        # Simple test
        with open(os.path.join(path, "main.fmf"), "w") as main:
            main.write("a: b\na: c\n")
        with pytest.raises(utils.FileError):
            fmf.Tree(path)

        # Add some hierarchy
        subdir = os.path.join(path, "dir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "a.fmf"), "w") as new_file:
            new_file.write("a: d\n")
        with pytest.raises(utils.FileError):
            fmf.Tree(path)

        # Remove duplicate key, check that inheritance doesn't
        # raise an exception
        with open(os.path.join(path, "main.fmf"), "w") as main:
            main.write("a: b\n")
        fmf.Tree(path)

        rmtree(path)

    def test_inaccessible_directories(self):
        """ Inaccessible directories should be silently ignored """
        directory = tempfile.mkdtemp()
        accessible = os.path.join(directory, 'accessible')
        inaccessible = os.path.join(directory, 'inaccessible')
        os.mkdir(accessible, 511)
        os.mkdir(inaccessible, 000)
        with open(os.path.join(accessible, 'main.fmf'), 'w') as main:
            main.write('key: value\n')
        Tree.init(directory)
        tree = Tree(directory)
        assert tree.find('/accessible').get('key') == 'value'
        assert tree.find('/inaccessible') is None
        os.chmod(inaccessible, 511)
        rmtree(directory)

    def test_node_copy_complete(self):
        """ Create deep copy of the whole tree """
        original = self.merge
        duplicate = original.copy()
        duplicate.data['x'] = 1
        assert original.parent is None
        assert duplicate.parent is None
        assert original.get('x') is None
        assert duplicate.get('x') == 1

    def test_node_copy_child(self):
        """ Duplicate child changes do not affect original """
        original = self.merge
        duplicate = original.copy()
        original_child = original.find('/parent/extended')
        duplicate_child = duplicate.find('/parent/extended')
        original_child.data['original'] = True
        duplicate_child.data['duplicate'] = True
        assert original_child.get('original') is True
        assert duplicate_child.get('original') is None
        assert original_child.get('duplicate') is None
        assert duplicate_child.get('duplicate') is True

    def test_node_copy_subtree(self):
        """ Create deep copy of a subtree """
        original = self.merge.find('/parent/extended')
        duplicate = original.copy()
        duplicate.data['x'] = 1
        assert original.parent == duplicate.parent
        assert duplicate.parent.name == '/parent'
        assert duplicate.get('x') == 1
        assert original.get('x') is None

    def test_validation(self):
        """ Test JSON Schema validation """
        test_schema_path = os.path.join(PATH, 'assets', 'schema_test.yaml')
        plan_schema_path = os.path.join(PATH, 'assets', 'schema_plan.yaml')

        with open(test_schema_path, encoding='utf-8') as schemafile:
            test_schema = YAML(typ="safe").load(schemafile)

        with open(plan_schema_path, encoding='utf-8') as schemafile:
            plan_schema = YAML(typ="safe").load(schemafile)

        test = self.wget.find('/recursion/deep')

        # valid schema
        expected = utils.JsonSchemaValidationResult(True, [])
        assert test.validate(test_schema) == expected

        # invalid schema
        assert not test.validate(plan_schema).result

    def test_validation_with_store(self):
        """ Test JSON Schema validation with schema store """

        base_schema_path = os.path.join(PATH, 'assets', 'schema_base.yaml')
        test_schema_ref_path = os.path.join(
            PATH, 'assets', 'schema_test_ref.yaml')

        with open(test_schema_ref_path, encoding='utf-8') as schemafile:
            test_schema_ref = YAML(typ="safe").load(schemafile)

        with open(base_schema_path, encoding='utf-8') as schemafile:
            base_schema = YAML(typ="safe").load(schemafile)

        test = self.wget.find('/recursion/deep')

        schema_store = {}
        schema_store[base_schema['$id']] = base_schema

        # valid schema
        expected = utils.JsonSchemaValidationResult(True, [])
        assert test.validate(
            test_schema_ref,
            schema_store=schema_store) == expected

    def test_validation_invalid_schema(self):
        """ Test invalid JSON Schema handling """
        with pytest.raises(fmf.utils.JsonSchemaError):
            self.wget.find('/recursion/deep').validate('invalid')


class TestRemote:
    """ Get tree node data using remote reference """

    @pytest.mark.web
    def test_tree_node_remote(self):
        reference = {
            'url': FMF_REPO,
            'ref': '0.10',
            'path': 'examples/deep',
            'name': '/one/two/three',
            }

        # Values of test in 0.10 tag
        expected_data = {
            'hardware': {
                'memory': {'size': 8},
                'network': {'model': 'e1000'}},
            'key': 'value'}

        # Full identifier
        node = Tree.node(reference)
        assert node.get() == expected_data

        # Default ref
        reference.pop('ref')
        node = Tree.node(reference)
        assert node.get() == expected_data

        # Raise exception for invalid tree nodes
        with pytest.raises(utils.ReferenceError):
            reference['name'] = 'not_existing_name_'
            node = Tree.node(reference)

    def test_tree_node_local(self):
        reference = {
            'path': EXAMPLES + 'wget',
            'name': '/protocols/https',
            }
        node = Tree.node(reference)
        assert node.get('time') == '1 min'

    def test_tree_node_relative_path(self):
        with pytest.raises(utils.ReferenceError):
            Tree.node(dict(path='some/relative/path'))

    @pytest.mark.web
    def test_tree_commit(self, tmpdir):
        # Tag
        node = Tree.node(dict(url=FMF_REPO, ref='0.12'))
        assert node.commit == '6570aa5f10729991625d74036473a71f384d745b'
        # Hash
        node = Tree.node(dict(url=FMF_REPO, ref='fa05dd9'))
        assert 'fa05dd9' in node.commit
        assert 'fa05dd9' in node.commit  # return already detected value
        # Data
        node = Tree(dict(x=1))
        assert node.commit is False
        # No git repository
        tree = Tree(Tree.init(str(tmpdir)))
        assert tree.commit is False

    @pytest.mark.web
    def test_tree_concurrent(self):
        def get_node(ref):
            try:
                Tree.node(dict(url=FMF_REPO, ref=ref))
                q.put(True)
            except Exception as error:
                q.put(error)
        possible_refs = [None, '0.12', 'fa05dd9']
        q = queue.Queue()
        threads = []
        for i in range(10):
            # Arguments vary based on current thread index
            threads.append(threading.Thread(
                target=get_node,
                args=(possible_refs[i % len(possible_refs)],)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # For number of threads check their results
        all_good = True
        for t in threads:
            value = q.get()
            if isinstance(value, Exception):
                print(value)  # so it is visible in the output
                all_good = False
        assert all_good

    def test_tree_concurrent_timeout(self, monkeypatch):
        # Much shorter timeout
        monkeypatch.setattr('fmf.utils.NODE_LOCK_TIMEOUT', 2)

        def long_fetch(*args, **kwargs):
            # Longer than timeout
            time.sleep(7)
            return EXAMPLES

        # Patch fetch to sleep and later return tmpdir path
        monkeypatch.setattr('fmf.utils.fetch_repo', long_fetch)

        # Background thread to get node() acquiring lock
        def target():
            Tree.node({
                'url': 'localhost',
                'name': '/',
                })
        thread = threading.Thread(target=target)
        thread.start()

        # Small sleep to mitigate race
        time.sleep(2)

        # "Real" fetch shouldn't get the lock
        with pytest.raises(utils.GeneralError):
            Tree.node({
                'url': 'localhost',
                'name': '/',
                })

        # Wait on parallel thread to finish
        thread.join()
