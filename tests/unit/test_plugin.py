"""Plugin discovery, configuration, tree integration, and write safety."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from ruamel.yaml import YAML

from fmf.base import MAIN, SUFFIX, Tree
from fmf.plugin import Plugin
from fmf.plugins.fmf import FmfPlugin
from fmf.utils import FileError


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    monkeypatch.setattr(Plugin, '_plugins', [])
    monkeypatch.setattr(Plugin, '_discovered', False)


@pytest.fixture
def root(tmp_path):
    Tree.init(str(tmp_path))
    return tmp_path


class TextPlugin(Plugin):
    """A non-YAML reader exercising the same interface as installed plugins."""

    CONFIG_SECTION = 'text'

    def read_config(self, config):
        self.settings = self.config_section_data(config)

    def can_handle(self, filename):
        return filename.endswith('.txt')

    def read(self, filename):
        return dict(line.split('=', 1) for line in Path(filename).read_text().splitlines())


def test_installed_entry_point(root):
    """Real package metadata must discover the built-in plugin."""
    (root / MAIN).write_text('summary: root\n')
    tree = Tree(str(root))
    assert tree.get('summary') == 'root'
    assert any(type(plugin) is FmfPlugin for plugin in tree._plugins)
    assert MAIN == 'main.fmf' and SUFFIX == '.fmf'


def test_discovery_is_once_and_deduplicated(monkeypatch):
    entry_point = Mock()
    entry_point.load.return_value = FmfPlugin
    discover = Mock(return_value=[entry_point, entry_point])
    monkeypatch.setattr('fmf.plugin.entry_points', discover)
    first, second = Plugin.for_tree({}), Plugin.for_tree({})
    discover.assert_called_once_with(group='fmf.plugins')
    assert len(first) == len(second) == 1
    assert isinstance(first[0], FmfPlugin)
    assert first[0] is not second[0]


def test_discovery_failure(monkeypatch):
    entry_point = Mock(name='broken')
    entry_point.load.side_effect = ImportError('missing dependency')
    monkeypatch.setattr('fmf.plugin.entry_points', lambda **kwargs: [entry_point])
    with pytest.raises(FileError, match='missing dependency'):
        Plugin.discover()
    assert not Plugin._discovered


@pytest.mark.parametrize('kind, message', [
    ('unrelated', 'not a Plugin subclass'),
    ('abstract', 'abstract'),
    ('missing_section', 'CONFIG_SECTION'),
    ])
def test_invalid_registration(kind, message):
    if kind == 'unrelated':
        candidate = object
    elif kind == 'abstract':
        candidate = Plugin
    else:
        class MissingSection(TextPlugin):
            CONFIG_SECTION = None
        candidate = MissingSection
    with pytest.raises(ValueError, match=message):
        Plugin.register(candidate)


@pytest.mark.parametrize('filename, expected', [
    ('main.fmf', FmfPlugin), ('test.txt', TextPlugin), ('test.py', None),
    ])
def test_dispatch(filename, expected):
    # Overlapping handlers exercise first-match selection without duplicate tests.
    class OtherFmfPlugin(FmfPlugin):
        pass
    plugins = [FmfPlugin(), TextPlugin(), OtherFmfPlugin()]
    selected = Plugin.for_file(filename, plugins)
    assert (type(selected) if selected else None) is expected


@pytest.mark.parametrize('section', ['fmf', 'text'])
@pytest.mark.parametrize('settings', [{}, {'option': 'value'}, 'invalid'])
def test_configuration(section, settings):
    plugin = FmfPlugin() if section == 'fmf' else TextPlugin()
    config = {section: settings, 'unrelated': {'option': 'ignore'}}
    if isinstance(settings, dict):
        plugin.read_config(config)
        assert plugin.settings == settings
        plugin.read_config({'unrelated': {'option': 'ignore'}})
        assert plugin.settings == {}
    else:
        with pytest.raises(FileError, match='must be a mapping'):
            plugin.read_config(config)


@pytest.mark.parametrize('content, expected', [
    ('', {}),
    ('summary: test\ntag: [Tier1]\n', {'summary': 'test', 'tag': ['Tier1']}),
    ])
def test_fmf_read_write(tmp_path, content, expected):
    source = tmp_path / 'test.fmf'
    source.write_text(content)
    plugin = FmfPlugin()
    assert plugin.read(str(source)) == expected
    plugin.write(str(source), [], expected, {}, {}, [])
    assert YAML(typ='safe').load(source.read_text()) == expected


@pytest.mark.parametrize('content', [None, 'invalid: yaml: structure:', 'key: 1\nkey: 2\n'])
def test_reader_error_and_recovery(tmp_path, content):
    source = tmp_path / 'test.fmf'
    if content is not None:
        source.write_text(content)
    plugin = FmfPlugin()
    with pytest.raises(FileError):
        plugin.read(str(source))
    source.write_text('summary: recovered\n')
    assert plugin.read(str(source)) == {'summary': 'recovered'}


def test_mixed_tree(root):
    Plugin.register(TextPlugin)
    (root / '.fmf/config').write_text('unrelated: value\n')
    (root / MAIN).write_text('summary: root\ntag: [inherited]\n')
    (root / 'named.fmf').write_text('summary: yaml\n')
    (root / 'source.txt').write_text('summary=text\nformat=txt\n')
    (root / 'ignored.py').write_text('not metadata')
    (root / 'child').mkdir()
    (root / 'child/main.fmf').write_text('summary: directory\n')
    tree = Tree(str(root))
    assert tree.get('summary') == 'root'
    assert set(tree.children) == {'named', 'source', 'child'}
    for name, summary in [('named', 'yaml'), ('source', 'text'), ('child', 'directory')]:
        assert tree.find('/' + name).get('summary') == summary
        assert tree.find('/' + name).get('tag') == ['inherited']


def test_tree_plugin_lifetime(tmp_path, monkeypatch):
    """Interleaved trees and writes retain their own configured instances."""
    class RecordingPlugin(FmfPlugin):
        instances = []

        def __init__(self):
            super().__init__()
            self.config_calls = 0
            self.writes = []
            self.instances.append(self)

        def read_config(self, config):
            self.config_calls += 1
            super().read_config(config)

        def write(self, filename, hierarchy, data, *args):
            self.writes.append((Path(filename).name, hierarchy, self.settings['marker']))
            super().write(filename, hierarchy, data, *args)

    monkeypatch.setattr('fmf.plugin.entry_points', lambda **kwargs: [])
    Plugin.register(RecordingPlugin)
    trees = []
    for marker in ('a', 'b'):
        root = tmp_path / marker
        root.mkdir()
        Tree.init(str(root))
        (root / '.fmf/config').write_text(f'fmf:\n  marker: {marker}\n')
        (root / 'main.fmf').write_text('summary: root\n/embedded:\n  tag+: [one]\n')
        (root / 'named.fmf').write_text('summary: named\n')
        trees.append(Tree(str(root)))

    a, b = trees
    first, second = RecordingPlugin.instances
    assert first is not second
    assert a.find('/embedded')._plugins is a._plugins
    with a.find('/embedded') as data:
        data['tag-'] = ['two']
    with a.find('/named') as data:
        data['summary'] = 'changed'
    with b.find('/embedded') as data:
        data['summary'] = 'other tree'
    assert first.config_calls == second.config_calls == 1
    assert first.writes == [('main.fmf', ['/embedded'], 'a'), ('named.fmf', [], 'a')]
    assert second.writes == [('main.fmf', ['/embedded'], 'b')]

    duplicate = a.copy()
    assert duplicate._plugins[0] is not first
    assert duplicate.find('/embedded')._plugins is duplicate._plugins
    assert duplicate._plugins[0].settings == first.settings
    duplicate._plugins[0].settings['marker'] = 'copy'
    assert first.settings['marker'] == 'a'

    raw = YAML(typ='safe').load((tmp_path / 'a/main.fmf').read_text())
    assert raw['/embedded'] == {'tag+': ['one'], 'tag-': ['two']}
    assert YAML(typ='safe').load((tmp_path / 'a/named.fmf').read_text()) == {
        'summary': 'changed'}


@pytest.mark.parametrize('broken', [False, True], ids=['unsupported', 'broken'])
def test_writer_failure_preserves_source(root, monkeypatch, broken):
    # The unsupported case exercises Plugin.write's default implementation.
    if broken:
        def fail(*args):
            raise RuntimeError('write unavailable')
        monkeypatch.setattr(TextPlugin, 'write', fail)
    Plugin.register(TextPlugin)
    source = root / 'source.txt'
    original = 'summary=original\n'
    source.write_text(original)
    tree = Tree(str(root))
    with pytest.raises(FileError, match='Failed to write'):
        with tree.find('/source') as data:
            data['summary'] = 'edited'
    assert source.read_text() == original
    assert not source.with_suffix('.fmf').exists()


def test_explicit_sidecar(root, monkeypatch):
    def write_sidecar(self, filename, hierarchy, data, *args):
        self._write_fmf_fallback(Path(filename).with_suffix('.fmf'), data)
    monkeypatch.setattr(TextPlugin, 'write', write_sidecar)
    Plugin.register(TextPlugin)
    source = root / 'source.txt'
    source.write_text('summary=original\n')
    tree = Tree(str(root))
    with tree.find('/source') as data:
        data['tag+'] = ['added']
    sidecar = source.with_suffix('.fmf')
    expected = {'summary': 'original', 'tag+': ['added']}
    assert YAML(typ='safe').load(sidecar.read_text()) == expected
    assert source.read_text() == 'summary=original\n'
    with pytest.raises(FileError, match='Failed to write'):
        with tree.find('/source') as data:
            data['summary'] = 'another edit'
    assert YAML(typ='safe').load(sidecar.read_text()) == expected


def test_sidecar_requires_fmf_path(tmp_path):
    destination = tmp_path / 'source.txt'
    with pytest.raises(FileError, match='must end in .fmf'):
        TextPlugin()._write_fmf_fallback(destination, {'summary': 'test'})
    assert not destination.exists()
