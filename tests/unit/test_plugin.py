"""
Unit tests for the FMF plugin system
"""

import os
import tempfile
from pathlib import Path
from shutil import rmtree
from typing import Optional

import pytest

from fmf.base import Tree
from fmf.plugin import Plugin
from fmf.plugin_loader import get_registry


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        get_registry().clear()

    def teardown_method(self):
        """Clean up after tests."""
        get_registry().clear()

    def test_fmf_plugin_discovered_via_entry_point(self):
        """Test that FmfPlugin is discovered through the entry point group."""
        from fmf.plugins.fmf import FmfPlugin

        registry = get_registry()
        registry.clear()
        registry.discover()

        # Should be able to handle .fmf files
        plugin = registry.get_plugin_for_file("test.fmf")
        assert plugin is FmfPlugin
        assert plugin.extensions == [".fmf"]

    def test_get_plugin_triggers_discovery(self):
        """Test that discovery happens lazily on first lookup after clear."""
        from fmf.plugins.fmf import FmfPlugin

        registry = get_registry()
        registry.clear()

        # No explicit discover()/register() call - lookup must trigger it
        assert registry.get_plugin_for_file("test.fmf") is FmfPlugin

    def test_plugin_can_handle_fmf_files(self):
        """Test that FmfPlugin handles .fmf files."""
        from fmf.plugins.fmf import FmfPlugin

        registry = get_registry()
        registry.register(FmfPlugin)

        plugin_class = registry.get_plugin_for_file("test.fmf")
        assert plugin_class == FmfPlugin

    def test_no_plugin_for_unknown_extension(self):
        """Test that unknown extensions return None."""
        from fmf.plugins.fmf import FmfPlugin

        registry = get_registry()
        registry.register(FmfPlugin)

        plugin_class = registry.get_plugin_for_file("test.xyz")
        assert plugin_class is None

    def test_plugin_load_order(self):
        """Test that the first plugin in load order wins for a file."""
        from fmf.plugins.fmf import FmfPlugin

        # Another plugin that also handles .fmf files
        class OtherFmfPlugin(Plugin):
            extensions = [".fmf"]
            file_patterns = [r".*\.fmf$"]

            def read_config(self, config):
                pass

            def can_handle(self, filename):
                return filename.endswith(".fmf")

            def read(self, filename):
                return {"from": "OtherFmfPlugin"}

        registry = get_registry()
        registry.register(FmfPlugin)
        registry.register(OtherFmfPlugin)

        # FmfPlugin was registered first, so it wins
        plugin_class = registry.get_plugin_for_file("test.fmf")
        assert plugin_class == FmfPlugin

    def test_register_invalid_plugin_fails(self):
        """Test that registering non-Plugin class raises error."""
        registry = get_registry()

        class NotAPlugin:
            pass

        with pytest.raises(ValueError, match="not a Plugin subclass"):
            registry.register(NotAPlugin)


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

    def _make_plugin(self, section: Optional[str] = "my"):
        """Build a minimal concrete plugin with the given config section."""
        from fmf.plugins.fmf import FmfPlugin

        class MyPlugin(FmfPlugin):
            config_section = section

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
        assert plugin.config_section_data({"my": "not-a-dict"}) == {}

    def test_config_section_data_no_section_defined(self):
        """A plugin without config_section always gets an empty dict."""
        plugin = self._make_plugin(None)
        assert plugin.config_section_data({"anything": {"a": 1}}) == {}

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
        registry = get_registry()
        registry.clear()
        registry.discover()

        self.tmpdir = tempfile.mkdtemp()
        Tree.init(self.tmpdir)

    def teardown_method(self):
        """Clean up."""
        rmtree(self.tmpdir)
        get_registry().clear()

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
        registry = get_registry()
        registry.clear()
        registry.discover()

    def teardown_method(self):
        """Clean up registry."""
        get_registry().clear()

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
        get_registry().clear()

        # Define a simple mock plugin for .txt files
        class MockTxtPlugin(Plugin):
            """Mock plugin for testing - reads .txt files with key=value format."""

            extensions = [".txt"]
            file_patterns = [r".*\.txt$"]

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
                    filename, hierarchy, modified_dict, append_dict)

        self.MockTxtPlugin = MockTxtPlugin

    def teardown_method(self):
        """Clean up."""
        rmtree(self.tmpdir)
        get_registry().clear()

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

        registry = get_registry()
        registry.register(FmfPlugin)
        registry.register(self.MockTxtPlugin)

        # Should find correct plugin for each extension
        assert registry.get_plugin_for_file("test.fmf") == FmfPlugin
        assert registry.get_plugin_for_file("test.txt") == self.MockTxtPlugin
        assert registry.get_plugin_for_file("test.py") is None

    def test_tree_loads_multiple_file_types(self):
        """Test Tree loads both .fmf and .txt files with different plugins."""
        from fmf.plugins.fmf import FmfPlugin

        # Register both plugins
        registry = get_registry()
        registry.register(FmfPlugin)
        registry.register(self.MockTxtPlugin)

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
        plugin.write(txt_file, [], {}, {}, {"new": "data"}, [])

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
            extensions = [".fmf"]
            file_patterns = [r".*\.fmf$"]

            def read_config(self, config):
                pass

            def can_handle(self, filename):
                return filename.endswith(".fmf")

            def read(self, filename):
                return {"source": "other"}

            def write(self, filename, hierarchy, data, append_dict,
                      modified_dict, deleted_items):
                pass

        registry = get_registry()
        registry.register(FmfPlugin)
        registry.register(OtherFmfPlugin)

        # FmfPlugin was registered first, so it wins
        plugin_class = registry.get_plugin_for_file("test.fmf")
        assert plugin_class == FmfPlugin
