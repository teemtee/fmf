"""
Unit tests for the FMF plugin system
"""

import os
import tempfile
from pathlib import Path
from shutil import rmtree

import pytest

from fmf.base import Tree
from fmf.plugin import Plugin
from fmf.utils import FileError


def reset_plugins():
    Plugin._plugins = []
    Plugin._discovered = False


@pytest.fixture
def isolated_plugins(monkeypatch):
    """Isolate test discovery from installed entry points and other tests."""
    reset_plugins()
    monkeypatch.setattr('fmf.plugin.entry_points', lambda **kwargs: [])
    yield
    reset_plugins()


def test_tree_plugin_lifetime(tmp_path, isolated_plugins):
    """Interleaved trees and writes retain their own configured instances."""
    from fmf.plugins.fmf import FmfPlugin

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

    from ruamel.yaml import YAML
    raw = YAML(typ='safe').load((tmp_path / 'a/main.fmf').read_text())
    assert raw['/embedded'] == {'tag+': ['one'], 'tag-': ['two']}
    assert YAML(typ='safe').load((tmp_path / 'a/named.fmf').read_text()) == {
        'summary': 'changed'}


@pytest.mark.parametrize('failure', [NotImplementedError, RuntimeError])
def test_writer_failure_preserves_source(tmp_path, isolated_plugins, failure):
    """Unsupported or broken writers never trigger YAML output to source code."""
    class SourcePlugin(Plugin):
        CONFIG_SECTION = 'source'

        def read_config(self, config):
            pass

        def can_handle(self, filename):
            return filename.endswith('.py')

        def read(self, filename):
            return {'summary': 'source'}

        def write(self, *args):
            raise failure('write unavailable')

    Plugin.register(SourcePlugin)
    Tree.init(str(tmp_path))
    source = tmp_path / 'test.py'
    original = 'print("original source")\n'
    source.write_text(original)
    tree = Tree(str(tmp_path))
    with pytest.raises(FileError, match='write unavailable'):
        with tree.find('/test') as data:
            data['summary'] = 'edited'
    assert source.read_text() == original
    assert not (tmp_path / 'test.fmf').exists()


def test_sidecar_preserves_existing_file(tmp_path):
    from fmf.plugins.fmf import FmfPlugin

    destination = tmp_path / 'test.fmf'
    destination.write_text('summary: existing\n')
    with pytest.raises(FileExistsError):
        FmfPlugin()._write_fmf_fallback(destination, {'summary': 'replacement'})
    assert destination.read_text() == 'summary: existing\n'


def test_discovery_is_once_and_deduplicated(monkeypatch, isolated_plugins):
    from fmf.plugins.fmf import FmfPlugin

    calls = []

    class EntryPoint:
        name = 'fmf'

        def load(self):
            calls.append(self.name)
            return FmfPlugin

    monkeypatch.setattr('fmf.plugin.entry_points', lambda **kwargs: [EntryPoint(), EntryPoint()])
    first = Plugin.for_tree({})
    second = Plugin.for_tree({})
    assert calls == ['fmf', 'fmf']
    assert len(first) == len(second) == 1
    assert first[0] is not second[0]


def test_abstract_plugin_rejected(isolated_plugins):
    class AbstractPlugin(Plugin):
        CONFIG_SECTION = 'abstract'

    with pytest.raises(ValueError, match='abstract'):
        Plugin.register(AbstractPlugin)


def matching_class(filename):
    plugin = Plugin.for_file(filename, Plugin.for_tree({}))
    return type(plugin) if plugin else None


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        reset_plugins()

    def teardown_method(self):
        """Clean up after tests."""
        reset_plugins()

    def test_fmf_plugin_discovered_via_entry_point(self):
        """Test that FmfPlugin is discovered through the entry point group."""
        from fmf.plugins.fmf import FmfPlugin

        reset_plugins()
        Plugin.discover()

        # Should be able to handle .fmf files
        plugin = matching_class("test.fmf")
        assert plugin is FmfPlugin
        assert plugin().can_handle("test.fmf")

    def test_get_plugin_triggers_discovery(self):
        """Test that discovery happens lazily on first lookup after clear."""
        from fmf.plugins.fmf import FmfPlugin

        reset_plugins()

        # No explicit discover()/register() call - lookup must trigger it
        assert matching_class("test.fmf") is FmfPlugin

    def test_plugin_can_handle_fmf_files(self):
        """Test that FmfPlugin handles .fmf files."""
        from fmf.plugins.fmf import FmfPlugin

        Plugin.register(FmfPlugin)

        plugin_class = matching_class("test.fmf")
        assert plugin_class == FmfPlugin

    def test_no_plugin_for_unknown_extension(self):
        """Test that unknown extensions return None."""
        from fmf.plugins.fmf import FmfPlugin

        Plugin.register(FmfPlugin)

        plugin_class = matching_class("test.xyz")
        assert plugin_class is None

    def test_plugin_load_order(self):
        """Test that the first plugin in load order wins for a file."""
        from fmf.plugins.fmf import FmfPlugin

        # Another plugin that also handles .fmf files
        class OtherFmfPlugin(Plugin):
            CONFIG_SECTION = "other"

            def read_config(self, config):
                pass

            def can_handle(self, filename):
                return filename.endswith(".fmf")

            def read(self, filename):
                return {"from": "OtherFmfPlugin"}

        Plugin.register(FmfPlugin)
        Plugin.register(OtherFmfPlugin)

        # FmfPlugin was registered first, so it wins
        plugin_class = matching_class("test.fmf")
        assert plugin_class == FmfPlugin

    def test_register_invalid_plugin_fails(self):
        """Test that registering non-Plugin class raises error."""

        class NotAPlugin:
            pass

        with pytest.raises(ValueError, match="not a Plugin subclass"):
            Plugin.register(NotAPlugin)


class TestFmfPlugin:
    """Test FmfPlugin functionality."""

    def setup_method(self):
        """Create temporary directory."""
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temporary directory."""
        rmtree(self.tmpdir)

    def test_read_simple_fmf_file(self):
        """Test reading a simple .fmf file."""
        from fmf.plugins.fmf import FmfPlugin

        # Create test .fmf file
        fmf_file = os.path.join(self.tmpdir, "test.fmf")
        with open(fmf_file, "w") as f:
            f.write("description: Test\ntag: [Tier1]\n")

        # Read with plugin
        plugin = FmfPlugin()
        data = plugin.read(fmf_file)

        assert data["description"] == "Test"
        assert data["tag"] == ["Tier1"]

    def test_read_empty_fmf_file(self):
        """Test reading an empty .fmf file returns empty dict."""
        from fmf.plugins.fmf import FmfPlugin

        # Create empty .fmf file
        fmf_file = os.path.join(self.tmpdir, "empty.fmf")
        with open(fmf_file, "w") as f:
            f.write("")

        # Read with plugin
        plugin = FmfPlugin()
        data = plugin.read(fmf_file)

        assert data == {}

    def test_read_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises FileError."""
        import fmf.utils as utils
        from fmf.plugins.fmf import FmfPlugin

        # Create invalid YAML
        fmf_file = os.path.join(self.tmpdir, "bad.fmf")
        with open(fmf_file, "w") as f:
            f.write("invalid: yaml: structure:\n  bad indentation")

        plugin = FmfPlugin()
        with pytest.raises(utils.FileError):
            plugin.read(fmf_file)

    def test_can_handle_method(self):
        """Test can_handle returns correct boolean."""
        from fmf.plugins.fmf import FmfPlugin

        plugin = FmfPlugin()

        assert plugin.can_handle("test.fmf") is True
        assert plugin.can_handle("test.py") is False
        assert plugin.can_handle("test.sh") is False

    def test_write_functionality(self):
        """Test that write() works for .fmf files."""
        from fmf.plugins.fmf import FmfPlugin

        # Create test file
        test_file = os.path.join(self.tmpdir, "output.fmf")

        # Test data to write
        data = {
            "description": "Test output",
            "/child": {
                "tag": ["Tier1"]
                }
            }

        # Write using plugin
        plugin = FmfPlugin()
        plugin.write(test_file, [], data, {}, {}, [])

        # Verify file was written
        assert os.path.exists(test_file)

        # Read it back and verify content
        with open(test_file, 'r') as f:
            content = f.read()
            assert "description: Test output" in content
            assert "/child:" in content
            assert "tag:" in content


class TestPluginConfigSection:
    """Test that plugins can read their own section from .fmf/config."""

    def _make_plugin(self, section: str = "my"):
        """Build a minimal concrete plugin with the given config section."""
        from fmf.plugins.fmf import FmfPlugin

        class MyPlugin(FmfPlugin):
            CONFIG_SECTION = section

            def read_config(self, config):
                self.settings = self.config_section_data(config)

        return MyPlugin()

    def test_config_section_data_returns_own_section(self):
        """Plugin gets only its own section from the config."""
        plugin = self._make_plugin("my")
        config = {"my": {"option": 1}, "other": {"option": 2}}
        assert plugin.config_section_data(config) == {"option": 1}

    def test_config_section_data_missing_section(self):
        """Missing or non-mapping sections yield an empty dict."""
        plugin = self._make_plugin("my")
        assert plugin.config_section_data({}) == {}
        with pytest.raises(FileError, match="must be a mapping"):
            plugin.config_section_data({"my": "not-a-dict"})

    def test_config_section_required(self):
        """Concrete plugins must declare a configuration section."""
        class MissingSection(Plugin):
            def read_config(self, config):
                pass

            def can_handle(self, filename):
                return False

            def read(self, filename):
                return {}

        with pytest.raises(ValueError, match="CONFIG_SECTION"):
            Plugin.register(MissingSection)

    def test_read_config_receives_section(self):
        """read_config() is passed the whole config and can pick its section."""
        plugin = self._make_plugin("my")
        plugin.read_config({"my": {"greeting": "hello"}})
        assert plugin.settings == {"greeting": "hello"}

    def test_fmf_plugin_reads_its_section(self):
        """FmfPlugin stores its own 'fmf' config section in settings."""
        from fmf.plugins.fmf import FmfPlugin

        plugin = FmfPlugin()
        plugin.read_config({"fmf": {"future_option": True}, "other": {}})
        assert plugin.settings == {"future_option": True}


class TestTreeWithPlugins:
    """Test Tree integration with plugin system."""

    def setup_method(self):
        """Create temporary directory and initialize fmf."""
        # Reset registry and rediscover plugins from entry points
        reset_plugins()
        Plugin.discover()

        self.tmpdir = tempfile.mkdtemp()
        Tree.init(self.tmpdir)

    def teardown_method(self):
        """Clean up."""
        rmtree(self.tmpdir)
        reset_plugins()

    def test_tree_loads_with_default_fmf_plugin(self):
        """Test that Tree works without explicit plugin config."""
        # Create main.fmf
        with open(os.path.join(self.tmpdir, "main.fmf"), "w") as f:
            f.write("description: Test\n")

        # Load tree (should auto-load FmfPlugin)
        tree = Tree(self.tmpdir)
        assert tree.data["description"] == "Test"

    def test_tree_ignores_unrelated_config(self):
        """Test Tree loads fine with unrelated keys in .fmf/config."""
        # Plugins are discovered via entry points, not config; any extra
        # config keys must be tolerated without affecting loading.
        config_dir = os.path.join(self.tmpdir, ".fmf")
        with open(os.path.join(config_dir, "config"), "w") as f:
            f.write("some_other_setting: value\n")

        # Create main.fmf
        with open(os.path.join(self.tmpdir, "main.fmf"), "w") as f:
            f.write("description: Test with config\n")

        tree = Tree(self.tmpdir)
        assert tree.data["description"] == "Test with config"

    def test_tree_loads_child_fmf_files(self):
        """Test that child .fmf files are loaded correctly."""
        # Create main.fmf
        with open(os.path.join(self.tmpdir, "main.fmf"), "w") as f:
            f.write("description: Parent\n")

        # Create child.fmf
        with open(os.path.join(self.tmpdir, "child.fmf"), "w") as f:
            f.write("description: Child node\ntag: [Tier1]\n")

        tree = Tree(self.tmpdir)

        # Check parent data
        assert tree.data["description"] == "Parent"

        # Check child node
        assert "child" in tree.children
        child = tree.children["child"]
        assert child.data["description"] == "Child node"
        assert child.data["tag"] == ["Tier1"]

    def test_tree_hierarchical_structure(self):
        """Test that directory hierarchy is preserved."""
        # Create subdirectory (don't init - it's a child of root tree)
        subdir = os.path.join(self.tmpdir, "tests")
        os.makedirs(subdir)

        # Create main.fmf in root
        with open(os.path.join(self.tmpdir, "main.fmf"), "w") as f:
            f.write("description: Root\n")

        # Create main.fmf in subdirectory
        with open(os.path.join(subdir, "main.fmf"), "w") as f:
            f.write("description: Subdir test\n")

        tree = Tree(self.tmpdir)

        # Check root
        assert tree.data["description"] == "Root"

        # Check subdirectory
        assert "tests" in tree.children
        tests_node = tree.children["tests"]
        assert tests_node.data["description"] == "Subdir test"

    def test_backward_compatibility_with_suffix_constant(self):
        """Test that SUFFIX constant is still available."""
        from fmf.base import MAIN, SUFFIX

        # Constants should be re-exported from fmf.plugins.fmf
        assert SUFFIX == ".fmf"
        assert MAIN == "main.fmf"

    def test_tree_write_with_context_manager(self):
        """Test that Tree context manager write uses plugins."""
        # Create main.fmf
        main_fmf = os.path.join(self.tmpdir, "main.fmf")
        with open(main_fmf, "w") as f:
            f.write("description: Original\ntier: 1\n")

        # Load tree
        tree = Tree(self.tmpdir)
        assert tree.data["description"] == "Original"
        assert tree.data["tier"] == 1

        # Modify using context manager (should use plugin write)
        with tree as data:
            data["tier"] = 2
            data["added"] = "new value"

        # Reload and verify changes were written
        tree2 = Tree(self.tmpdir)
        assert tree2.data["tier"] == 2
        assert tree2.data["added"] == "new value"
        assert tree2.data["description"] == "Original"


# Integration test with real examples
class TestRealWorldExamples:
    """Test plugin system with real fmf examples."""

    def setup_method(self):
        """Ensure FmfPlugin is loaded for examples."""
        reset_plugins()
        Plugin.discover()

    def teardown_method(self):
        """Clean up registry."""
        reset_plugins()

    def test_wget_example_still_works(self):
        """Test that existing wget example works with plugin system."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        wget_dir = examples_dir / "wget"

        if not wget_dir.exists():
            pytest.skip("Wget example directory not found")

        # Load tree
        tree = Tree(str(wget_dir))

        # Should have children
        assert len(tree.children) > 0

        # Check specific node exists
        download = tree.find("/download")
        assert download is not None

    def test_hidden_example_with_config(self):
        """Test hidden example that uses explore.include config."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        hidden_dir = examples_dir / "hidden"

        if not hidden_dir.exists():
            pytest.skip("Hidden example directory not found")

        # Load tree
        tree = Tree(str(hidden_dir))

        # Should discover .plans due to config
        plans = tree.find("/.plans/basic")
        assert plans is not None
        assert plans.get("discover") == {"how": "fmf"}


class TestMockPlugin:
    """Test plugin system with a mock plugin to verify multi-format support."""

    def setup_method(self):
        """Create temporary directory and mock plugin."""
        self.tmpdir = tempfile.mkdtemp()
        reset_plugins()

        # Define a simple mock plugin for .txt files
        class MockTxtPlugin(Plugin):
            """Mock plugin for testing - reads .txt files with key=value format."""

            CONFIG_SECTION = "txt"

            def read_config(self, config):
                pass

            def can_handle(self, filename):
                return filename.endswith(".txt")

            def read(self, filename):
                """Read key=value pairs from text file."""
                data = {}
                with open(filename) as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            data[key.strip()] = value.strip()
                return data

            def write(self, filename, hierarchy, data, append_dict,
                      modified_dict, deleted_items):
                """Use fallback .fmf writer."""
                self._write_fmf_fallback(
                    Path(filename).with_suffix('.fmf'), data)

        self.MockTxtPlugin = MockTxtPlugin

    def teardown_method(self):
        """Clean up."""
        rmtree(self.tmpdir)
        reset_plugins()

    def test_mock_plugin_can_handle_txt_files(self):
        """Test that mock plugin handles .txt files."""
        plugin = self.MockTxtPlugin()

        assert plugin.can_handle("test.txt") is True
        assert plugin.can_handle("test.fmf") is False
        assert plugin.can_handle("test.sh") is False

    def test_mock_plugin_reads_txt_file(self):
        """Test reading key=value from .txt file."""
        txt_file = os.path.join(self.tmpdir, "test.txt")
        with open(txt_file, "w") as f:
            f.write("description=Mock test\n")
            f.write("tag=Tier1\n")
            f.write("# comment line\n")
            f.write("enabled=true\n")

        plugin = self.MockTxtPlugin()
        data = plugin.read(txt_file)

        assert data["description"] == "Mock test"
        assert data["tag"] == "Tier1"
        assert data["enabled"] == "true"
        assert "#" not in data  # Comments ignored

    def test_registry_with_multiple_plugins(self):
        """Test that registry manages multiple plugins correctly."""
        from fmf.plugins.fmf import FmfPlugin

        Plugin.register(FmfPlugin)
        Plugin.register(self.MockTxtPlugin)

        # Should find correct plugin for each extension
        assert matching_class("test.fmf") == FmfPlugin
        assert matching_class("test.txt") == self.MockTxtPlugin
        assert matching_class("test.py") is None

    def test_tree_loads_multiple_file_types(self):
        """Test Tree loads both .fmf and .txt files with different plugins."""
        from fmf.plugins.fmf import FmfPlugin

        # Register both plugins
        Plugin.register(FmfPlugin)
        Plugin.register(self.MockTxtPlugin)

        # Initialize tree
        Tree.init(self.tmpdir)

        # Create main.fmf
        with open(os.path.join(self.tmpdir, "main.fmf"), "w") as f:
            f.write("description: Root with mixed formats\n")

        # Create .txt file
        with open(os.path.join(self.tmpdir, "metadata.txt"), "w") as f:
            f.write("description=Text metadata\n")
            f.write("format=txt\n")

        # Create another .fmf file
        with open(os.path.join(self.tmpdir, "other.fmf"), "w") as f:
            f.write("description: YAML metadata\nformat: fmf\n")

        # Load tree
        tree = Tree(self.tmpdir)

        # Check root from main.fmf
        assert tree.data["description"] == "Root with mixed formats"

        # Check .txt child loaded
        assert "metadata" in tree.children
        txt_child = tree.children["metadata"]
        assert txt_child.data["description"] == "Text metadata"
        assert txt_child.data["format"] == "txt"

        # Check .fmf child loaded
        assert "other" in tree.children
        fmf_child = tree.children["other"]
        assert fmf_child.data["description"] == "YAML metadata"
        assert fmf_child.data["format"] == "fmf"

    def test_mock_plugin_write_creates_fmf_fallback(self):
        """Test that mock plugin uses .fmf fallback for writing."""
        txt_file = os.path.join(self.tmpdir, "test.txt")
        with open(txt_file, "w") as f:
            f.write("old=value\n")

        plugin = self.MockTxtPlugin()
        plugin.write(txt_file, [], {"new": "data"}, {}, {}, [])

        # Should create test.fmf (fallback)
        expected_fmf = os.path.join(self.tmpdir, "test.fmf")
        assert os.path.exists(expected_fmf)

        # Verify content
        with open(expected_fmf) as f:
            content = f.read()
            assert "new:" in content
            assert "data" in content

    def test_plugin_load_order_resolution(self):
        """Test that the first registered plugin wins when both can handle."""
        from fmf.plugins.fmf import FmfPlugin

        # Another .fmf handler registered after FmfPlugin
        class OtherFmfPlugin(Plugin):
            CONFIG_SECTION = "other"

            def read_config(self, config):
                pass

            def can_handle(self, filename):
                return filename.endswith(".fmf")

            def read(self, filename):
                return {"source": "other"}

            def write(self, filename, hierarchy, data, append_dict,
                      modified_dict, deleted_items):
                pass

        Plugin.register(FmfPlugin)
        Plugin.register(OtherFmfPlugin)

        # FmfPlugin was registered first, so it wins
        plugin_class = matching_class("test.fmf")
        assert plugin_class == FmfPlugin
