"""Collectors own traversal and storage; Tree only combines their results."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fmf import Tree
from fmf.plugin import Plugin
from fmf.plugins.fmf import FmfPlugin
from fmf.utils import FileError, GeneralError


class ItemPlugin(Plugin):
    """Stand-in for a framework collector that returns selected test items."""

    CONFIG_SECTION = 'items'

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
    entries = []
    monkeypatch.setattr('fmf.plugin.entry_points', lambda **kwargs: entries)

    def register(plugin):
        entries.append(SimpleNamespace(name=plugin.__name__, load=lambda: plugin))

    return register


def test_independent_collection(metadata_root, collectors):
    collectors(ItemPlugin)
    nested = metadata_root / 'nested'
    nested.mkdir()
    (nested / 'main.fmf').write_text('summary: native\n')
    tree = Tree(str(metadata_root))
    plugin = tree._plugins[1]
    assert plugin.visited == [str(metadata_root)]
    assert tree.find('/nested').get('summary') == 'native'
    assert [node.name for node in tree.prune(keys=['duration'])] == [
        '/nested', '/suite/test_one', '/suite/test_two']
    item = tree.find('/suite/test_one')
    assert item.get('tags') == ['base', 'test_one']
    assert item.get('duration') == 4
    assert isinstance(Plugin.for_node(item), ItemPlugin)
    assert isinstance(Plugin.for_node(tree.find('/nested')), FmfPlugin)


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
    assert first._plugins[1] is not second._plugins[1]
    assert first._plugins[1].config == {'selected': ['first']}
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


def test_read_only_plugin_does_not_write_native_source(metadata_root, collectors):
    class ReadOnly(ItemPlugin):
        read = Plugin.read
        write = Plugin.write

    collectors(ReadOnly)
    tree = Tree(str(metadata_root))
    with pytest.raises(NotImplementedError, match='does not support editing'):
        with tree.find('/suite/test_one'):
            pass
    assert not (metadata_root / 'collected.json').exists()


def test_native_entry_point_is_not_loaded_twice(metadata_root, collectors):
    collectors(FmfPlugin)
    tree = Tree(str(metadata_root))
    assert len(tree._plugins) == 1
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
    with pytest.raises(GeneralError, match='No raw data'):
        with tree:
            pass


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


def test_later_collector_owns_overlapping_source(metadata_root, collectors):
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
    assert json.loads((metadata_root / 'other.json').read_text()) == {'summary': 'edited'}
    assert 'summary' not in (metadata_root / 'main.fmf').read_text()
