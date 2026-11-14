"""Collectors own traversal and storage; Tree only combines their results."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from fmf import Tree
from fmf.plugins import Merger, Plugin
from fmf.plugins.dictionary import DictionaryPlugin
from fmf.plugins.fmf import FmfPlugin
from fmf.utils import FileError, RootError


class HierarchicalPlugin(Plugin):
    """Opt into dictionary parsing without changing source or merger ownership."""

    def __init__(self):
        super().__init__()
        self.dictionary = DictionaryPlugin()

    def update(self, node, data):
        self.dictionary.update(node, data)


class ItemPlugin(Plugin):
    """Stand-in for a framework collector that returns selected test items."""

    CONFIG_SECTION = 'items'
    writable = True

    def grow(self, tree, path):
        self.visited = getattr(self, 'visited', []) + [path]
        # Selection and hierarchy belong to the collector, not filename rules.
        for item in self.config.get('selected', ['test_one', 'test_two']):
            tree.child('suite', {})
            suite = tree.children['suite']
            suite.child(item, {})
            self.load(suite.children[item], {'tags+': [item], 'duration-': 1},
                      str(Path(path) / 'collected.json'))

    def read(self, node):
        return node._raw_data

    def write(self, node):
        Path(node.sources[-1]).write_text(json.dumps(node._raw_data))


@pytest.fixture
def metadata_root(tmp_path):
    Tree.init(tmp_path)
    (tmp_path / 'main.fmf').write_text('tags: [base]\nduration: 5\n')
    return tmp_path


@pytest.fixture
def collectors(monkeypatch):
    entries = [SimpleNamespace(name='fmf', load=lambda: FmfPlugin)]
    monkeypatch.setattr('fmf.plugins._loader.entry_points', lambda **kwargs: entries)

    def register(plugin):
        entries.append(SimpleNamespace(name=plugin.__name__, load=lambda: plugin))

    return register


def test_independent_collection(metadata_root, collectors):
    collectors(ItemPlugin)
    nested = metadata_root / 'nested'
    nested.mkdir()
    (nested / 'main.fmf').write_text('summary: native\n')
    tree = Tree(str(metadata_root))
    plugin = tree._loader.plugins[0]
    assert plugin.visited == [str(metadata_root)]
    assert tree.find('/nested').get('summary') == 'native'
    assert [node.name for node in tree.prune(keys=['duration'])] == [
        '/nested', '/suite/test_one', '/suite/test_two']
    item = tree.find('/suite/test_one')
    assert item.get('tags') == ['base', 'test_one']
    assert item.get('duration') == 4
    assert isinstance(tree._loader.owner(item), ItemPlugin)
    assert isinstance(tree._loader.owner(tree.find('/nested')), FmfPlugin)


def test_plugin_selects_items_without_shared_walk(metadata_root, collectors, monkeypatch):
    collectors(ItemPlugin)
    (metadata_root / '.fmf/config').write_text('items:\n  selected: [chosen]\n')
    # Native discovery can be disabled without disabling another collector.
    monkeypatch.setattr(FmfPlugin, 'grow', lambda *args: None)
    tree = Tree(str(metadata_root))
    assert [node.name for node in tree.climb()] == ['/suite/chosen']


def test_plugin_instances_and_configuration_are_per_tree(metadata_root, collectors):
    collectors(ItemPlugin)
    config = metadata_root / '.fmf/config'
    config.write_text('items:\n  selected: [first]\n')
    first = Tree(str(metadata_root))
    config.write_text('items:\n  selected: [second]\n')
    second = Tree(str(metadata_root))
    assert first._loader.plugins[0] is not second._loader.plugins[0]
    assert first._loader.plugins[0].config == {'selected': ['first']}
    assert second.find('/suite/second') is not None
    assert second.find('/suite/first') is None


def test_write_uses_collecting_plugin(metadata_root, collectors):
    collectors(ItemPlugin)
    original = (metadata_root / 'main.fmf').read_text()
    tree = Tree(str(metadata_root))
    with tree.find('/suite/test_one') as data:
        data['tags+'] = ['edited']
    assert json.loads((metadata_root / 'collected.json').read_text()) == {
        'tags+': ['edited'], 'duration-': 1}
    assert (metadata_root / 'main.fmf').read_text() == original


@pytest.mark.parametrize('source', ['main.fmf', 'child.fmf'])
def test_native_write_preserves_raw_merge_keys(metadata_root, collectors, source):
    path = metadata_root / source
    path.write_text('tags: [base]\n/virtual:\n  tags+: [child]\n  duration-: 2\n')
    tree = Tree(str(metadata_root))
    prefix = '' if source == 'main.fmf' else '/child'
    with tree.find(prefix + '/virtual') as data:
        data['tags+'].append('edited')
    reloaded = Tree(str(metadata_root)).find(prefix + '/virtual')
    assert reloaded.get('tags') == ['base', 'child', 'edited']
    assert 'tags+:' in path.read_text()
    assert 'duration-: 2' in path.read_text()


@pytest.mark.parametrize('content', ['', '{}', '/virtual:'])
def test_native_empty_source_can_be_edited(metadata_root, collectors, content):
    path = metadata_root / 'empty.fmf'
    path.write_text(content)
    tree = Tree(str(metadata_root))
    name = '/empty/virtual' if content else '/empty'
    if content == '{}':
        name = '/empty'
    with tree.find(name) as data:
        data['summary'] = 'edited'
    assert Tree(str(metadata_root)).find(name).get('summary') == 'edited'
    assert 'summary: edited' in path.read_text()
    assert 'summary' not in (metadata_root / 'main.fmf').read_text()


def test_read_only_plugin_creates_native_sidecar(metadata_root, collectors):
    class ReadOnly(ItemPlugin):
        writable = False
        read = Plugin.read
        write = Plugin.write

    collectors(ReadOnly)
    tree = Tree(str(metadata_root))
    original = (metadata_root / 'main.fmf').read_text()
    with tree.find('/suite/test_one') as data:
        assert data['tags'] == ['base', 'test_one']
        data['tags'] = ['edited']
    assert not (metadata_root / 'collected.json').exists()
    assert (metadata_root / 'suite/test_one.fmf').exists()
    assert (metadata_root / 'main.fmf').read_text() == original
    reloaded = Tree(str(metadata_root))
    assert reloaded.find('/suite/test_one').get('tags') == ['edited']
    assert reloaded.find('/suite/test_one').get('duration') == 4
    # A subsequent edit reuses the sidecar through the normal FMF writer.
    with reloaded.find('/suite/test_one') as data:
        data['summary'] = 'updated again'
    assert Tree(str(metadata_root)).find('/suite/test_one').get('summary') == 'updated again'


def test_native_entry_point_is_not_loaded_twice(metadata_root, collectors):
    collectors(FmfPlugin)
    tree = Tree(str(metadata_root))
    assert len(tree._loader.plugins) == 1
    assert tree.sources == [str(metadata_root / 'main.fmf')]


def test_invalid_entry_point(metadata_root, collectors):
    collectors(dict)
    with pytest.raises(FileError, match='Plugin subclass'):
        Tree(str(metadata_root))


@pytest.mark.parametrize('config', ['[]', 'items: []'])
def test_invalid_config(metadata_root, collectors, config):
    collectors(ItemPlugin)
    (metadata_root / '.fmf/config').write_text(config)
    with pytest.raises(FileError, match='mapping'):
        Tree(str(metadata_root))


def test_dictionary_tree_needs_no_collectors(collectors):
    collectors(dict)  # Discovery would fail if it were attempted.
    tree = Tree({'tags': ['base'], '/child': {'tags+': ['child']}})
    assert tree.find('/child').get('tags') == ['base', 'child']
    assert isinstance(tree._plugin, DictionaryPlugin)
    with tree.find('/child') as data:
        data['tags+'] = ['edited']
    assert Tree(tree._raw_data).find('/child').get('tags') == ['base', 'edited']
    assert tree.sources == []


def test_dictionary_tree_can_grow_from_files(metadata_root, collectors):
    tree = Tree({'summary': 'existing'})
    tree.grow(str(metadata_root))
    assert tree.get('tags') == ['base']
    assert tree.get('summary') == 'existing'


def test_abstract_entry_point(metadata_root, collectors):
    collectors(Plugin)
    with pytest.raises(FileError, match='concrete Plugin subclass'):
        Tree(str(metadata_root))


def test_native_discovery_boundaries(metadata_root, collectors):
    (metadata_root / '.hidden.fmf').write_text('summary: hidden\n')
    (metadata_root / 'empty').mkdir()
    nested = metadata_root / 'nested'
    nested.mkdir()
    Tree.init(nested)
    (nested / 'main.fmf').write_text('summary: separate tree\n')
    branch = metadata_root / 'branch'
    branch.mkdir()
    (branch / 'main.fmf').write_text('summary: branch\n')
    (branch / 'loop').symlink_to(branch, target_is_directory=True)
    tree = Tree(str(metadata_root))
    assert tree.find('/.hidden') is None
    assert tree.find('/empty') is None
    assert tree.find('/nested') is None
    assert tree.find('/branch/loop') is not None
    assert tree.find('/branch/loop/loop') is None


def test_native_overlay_owns_overlapping_source(metadata_root, collectors):
    class Override(Plugin):
        def grow(self, tree, path):
            self.load(tree, {'summary': 'override'}, Path(path) / 'other.json')

        def read(self, node):
            return node._raw_data

        def write(self, node):
            Path(node.sources[-1]).write_text(json.dumps(node._raw_data))

    collectors(Override)
    tree = Tree(str(metadata_root))
    assert tree.get('tags') == ['base']
    assert tree.get('summary') == 'override'
    with tree as data:
        data['summary'] = 'edited'
    assert not (metadata_root / 'other.json').exists()
    assert Tree(str(metadata_root)).get('summary') == 'edited'
    assert 'summary: edited' in (metadata_root / 'main.fmf').read_text()


@pytest.mark.parametrize(('first', 'second', 'native', 'expected'), [
    ({'tags+': ['a']}, {'tags+': ['b']}, {'tags+': ['c']}, ['base', 'a', 'b', 'c']),
    ({'tags+': ['a']}, {'tags+<': ['b']}, {'tags-': ['base']}, ['b', 'a']),
    ({'tags+': ['a']}, {'tags-': ['a']}, {'tags+': ['c']}, ['base', 'c']),
    ])
def test_raw_merge_keys_survive_independent_collection(
        metadata_root, collectors, first, second, native, expected):
    from fmf.utils import dict_to_yaml

    observations = []

    class First(HierarchicalPlugin):
        def grow(self, tree, path):
            observations.append(tree.find('/shared'))
            self.load(tree, {'/shared': first}, 'first-source')

    class Second(HierarchicalPlugin):
        def grow(self, tree, path):
            observations.append(tree.find('/shared'))
            self.load(tree, {'/shared': second}, 'second-source')

    collectors(First)
    collectors(Second)
    (metadata_root / 'shared.fmf').write_text(dict_to_yaml(native))
    node = Tree(str(metadata_root)).find('/shared')
    assert observations == [None, None]  # Collectors cannot see each other's trees.
    assert node.get('tags') == expected
    # Preserve all raw layers even when the same operator key occurs twice.
    assert [data for _, data in node._layers] == [first, second, native]


def test_cross_plugin_numeric_and_nested_merges(metadata_root, collectors):
    (metadata_root / 'main.fmf').write_text(
        'duration: 10\noptions: {list: [base], value: 3}\n')
    (metadata_root / 'shared.fmf').write_text('duration-: 2\noptions+: {list-: [base]}\n')

    class First(HierarchicalPlugin):
        def grow(self, tree, path):
            self.load(tree, {'/shared': {'duration+': 5, 'options+': {'list+': ['a']}}})

    class Second(HierarchicalPlugin):
        def grow(self, tree, path):
            self.load(tree, {'/shared': {'duration-': 3, 'options+': {'list+': ['b']}}})

    collectors(First)
    collectors(Second)
    node = Tree(str(metadata_root)).find('/shared')
    assert node.get('duration') == 10
    assert node.get('options') == {'list': ['a', 'b'], 'value': 3}
    assert node._layers[0][1]['options+'] == {'list+': ['a']}


def test_plugin_controls_its_own_merger(metadata_root, collectors):
    class LiteralMerger(Merger):
        def merge(self, node, data, source):
            data.update(source)

    class Literal(HierarchicalPlugin):
        merger_class = LiteralMerger

        def grow(self, tree, path):
            self.load(tree, {'/shared': {'tags+': ['literal']}})

    collectors(Literal)
    (metadata_root / 'shared.fmf').write_text('tags+: [native]\n')
    tree = Tree(str(metadata_root))
    node = tree.find('/shared')
    assert node.get('tags') == ['base', 'native']
    assert node.get('tags+') == ['literal']
    assert isinstance(tree._loader.plugins[0].merger, LiteralMerger)
    assert tree._loader.plugins[0].merger is not tree._loader.plugins[1].merger


@pytest.mark.parametrize('data', [
    {'/one/two/one': {'summary': 'before'}},
    {'/one/two': {'/one': {'summary': 'before'}}},
    {'/one': {'/two': {'/one': {'summary': 'before'}}}},
    ])
def test_virtual_dictionary_edit_preserves_hierarchy(data):
    tree = Tree(data)
    with tree.find('/one/two/one') as raw:
        raw['summary'] = 'after'
    assert Tree(tree._raw_data).find('/one/two/one').get('summary') == 'after'


def test_native_backend_requires_entry_point(metadata_root, monkeypatch):
    monkeypatch.setattr('fmf.plugins._loader.entry_points', lambda **kwargs: [])
    with pytest.raises(RootError, match='No installed metadata plugin recognizes'):
        Tree(str(metadata_root))
    # Dictionary construction does not require package discovery.
    assert Tree({'summary': 'virtual'}).get('summary') == 'virtual'


def test_non_native_backend_can_initialize_tree(tmp_path, collectors, monkeypatch):
    class Other(ItemPlugin):
        def initialize(self, tree, path):
            tree.root = str(path)
            tree.config = {'items': {'selected': ['chosen']}}
            return True

    monkeypatch.setattr('fmf.plugins._loader.entry_points', lambda **kwargs: [
        SimpleNamespace(name='other', load=lambda: Other)])
    tree = Tree(str(tmp_path))
    assert tree.find('/suite/chosen') is not None
    assert not (tmp_path / '.fmf').exists()


def test_no_writer_reports_clear_error(tmp_path, monkeypatch):
    class ReadOnly(ItemPlugin):
        writable = False

        def initialize(self, tree, path):
            tree.root = str(path)
            return True

    monkeypatch.setattr('fmf.plugins._loader.entry_points', lambda **kwargs: [
        SimpleNamespace(name='readonly', load=lambda: ReadOnly)])
    tree = Tree(str(tmp_path))
    with pytest.raises(FileError, match='No installed plugin can store edits'):
        with tree.find('/suite/test_one'):
            pass


def test_virtual_source_keeps_collecting_ancestry(metadata_root, collectors):
    class Virtual(HierarchicalPlugin):
        writable = True

        def grow(self, tree, path):
            self.load(tree, {'/virtual': {'summary': 'original'}}, str(Path(path) / 'items.json'))

        def read(self, node):
            return DictionaryPlugin().read(node)

        def write(self, node):
            _, data, owner = DictionaryPlugin().locate(node)
            Path(owner.sources[-1]).write_text(json.dumps(data))

    collectors(Virtual)
    tree = Tree(str(metadata_root))
    # The combined root comes from main.fmf, while this virtual node's raw
    # ancestor comes from items.json. Editing must retain that provenance.
    assert isinstance(tree._loader.owner(tree), FmfPlugin)
    with tree.find('/virtual') as data:
        assert data['summary'] == 'original'
        data['summary'] = 'edited'
    assert json.loads((metadata_root / 'items.json').read_text()) == {
        '/virtual': {'summary': 'edited'}}
    assert 'summary' not in (metadata_root / 'main.fmf').read_text()


def test_fallback_refuses_to_reinterpret_another_plugins_operator_keys(metadata_root, collectors):
    class LiteralMerger(Merger):
        def merge(self, node, data, source):
            data.update(source)

    class Literal(HierarchicalPlugin):
        merger_class = LiteralMerger

        def grow(self, tree, path):
            self.load(tree, {'/literal': {'tags+': ['literal-key']}})

    collectors(Literal)
    tree = Tree(str(metadata_root))
    with pytest.raises(FileError, match='without reinterpreting merge keys'):
        with tree.find('/literal'):
            pass
    assert not (metadata_root / 'literal.fmf').exists()


def test_flat_plugin_does_not_interpret_dictionary_hierarchy(metadata_root, collectors):
    class Flat(Plugin):
        def grow(self, tree, path):
            self.load(tree, {'/': {'custom': True}, '/literal': {'value': 1}})

    collectors(Flat)
    tree = Tree(str(metadata_root))
    assert tree.get('/') == {'custom': True}
    assert tree.get('/literal') == {'value': 1}
    assert tree.find('/literal') is None
    assert tree._directives == {}


def test_fmf_dictionary_delegation_preserves_nested_ownership(metadata_root, collectors):
    source = metadata_root / 'main.fmf'
    source.write_text(
        'tags: [base]\n'
        '/one/two:\n'
        '  tags+: [two]\n'
        '  /three:\n'
        '    /: {inherit: false}\n'
        '    tags+: [three]\n')
    original = YAML(typ="safe").load(source.read_text())
    tree = Tree(str(metadata_root))
    assert tree._raw_data == original
    two = tree.find('/one/two')
    three = tree.find('/one/two/three')
    plugin = tree._loader.owner(tree)
    assert isinstance(plugin, FmfPlugin)
    assert isinstance(plugin.dictionary, DictionaryPlugin)
    assert two._plugin is three._plugin is plugin
    assert tree._loader.owner(three) is plugin
    assert two.get('tags') == ['base', 'two']
    assert three.get('tags') == ['three']
    assert three._layers[0][1] == {'tags+': ['three']}
    with three as data:
        assert data['/'] == {'inherit': False}
        data['tags+'].append('edited')
    reloaded = Tree(str(metadata_root)).find('/one/two/three')
    assert reloaded.get('tags') == ['three', 'edited']
    assert source.read_text().count('tags+:') == 2
    original['/one/two']['/three']['tags+'].append('edited')
    assert YAML(typ="safe").load(source.read_text()) == original


def test_dictionary_parsing_preserves_supplied_structure():
    data = {
        '/': {'select': False},
        'tags': ['base'],
        '/one/two': {'/': {'inherit': False}, 'tags+': ['child']},
        }
    original = copy.deepcopy(data)
    tree = Tree(data)
    assert data == original
    assert tree._raw_data == original
    assert tree.find('/one/two').get('tags') == ['child']
