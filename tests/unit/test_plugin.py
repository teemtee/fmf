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
from fmf.plugin_loader import get_registry


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        get_registry().clear()

    def teardown_method(self):
        """Clean up after tests."""
        get_registry().clear()

    def test_fmf_plugin_auto_registered(self):
        """Test that FmfPlugin is auto-registered on import."""
        # Clear and re-import to trigger registration
        get_registry().clear()
        import importlib

        import fmf.plugins.fmf
        importlib.reload(fmf.plugins.fmf)

        registry = get_registry()
        # Should be able to handle .fmf files
        plugin = registry.get_plugin_for_file("test.fmf")
        assert plugin is not None
        assert plugin.extensions == [".fmf"]

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

    def test_plugin_priority_system(self):
        """Test that higher priority plugins are preferred."""
        from fmf.plugins.fmf import FmfPlugin

        # Create a mock plugin with lower priority
        class LowPriorityPlugin(Plugin):
            extensions = [".fmf"]
            file_patterns = [r".*\.fmf$"]
            priority = 10  # Lower than FmfPlugin (100)

            def can_handle(self, filename):
                return filename.endswith(".fmf")

            def read(self, filename):
                return {"from": "LowPriorityPlugin"}

        registry = get_registry()
        registry.register(FmfPlugin)
        registry.register(LowPriorityPlugin)

        # FmfPlugin should win due to higher priority
        plugin_class = registry.get_plugin_for_file("test.fmf")
        assert plugin_class == FmfPlugin

    def test_load_builtin_plugin_by_short_name(self):
        """Test loading built-in plugin by short name."""
        registry = get_registry()

        # Load by short name (just validates, doesn't actually load)
        config = {"plugins": ["fmf"]}
        registry.load_from_config(config)

        # Should not raise an error (plugin name is valid)
        # Note: load_from_config now just validates, doesn't load

    def test_load_non_builtin_plugin_warns(self):
        """Test that non-built-in plugin names generate warnings."""
        registry = get_registry()

        # Try to load unknown plugin
        config = {"plugins": ["some.arbitrary.module"]}

        # Should log a warning but not raise
        registry.load_from_config(config)

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


class TestTreeWithPlugins:
    """Test Tree integration with plugin system."""

    def setup_method(self):
        """Create temporary directory and initialize fmf."""
        # Clear registry first to ensure clean state
        get_registry().clear()
        # Re-import to trigger FmfPlugin auto-registration
        import importlib

        import fmf.plugins.fmf
        importlib.reload(fmf.plugins.fmf)

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

    def test_tree_with_plugin_config(self):
        """Test Tree with explicit plugin configuration."""
        # Create config
        config_dir = os.path.join(self.tmpdir, ".fmf")
        with open(os.path.join(config_dir, "config"), "w") as f:
            f.write("plugins:\n  - fmf.plugins.fmf.FmfPlugin\n")

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


class TestPluginConfigurationOverride:
    """Test plugin configuration override features."""

    def setup_method(self):
        """Clear registry before tests."""
        get_registry().clear()

    def teardown_method(self):
        """Clean up."""
        get_registry().clear()

    def test_priority_override_from_config(self):
        """Test that plugin priority can be overridden in config."""
        from fmf.plugins.fmf import FmfPlugin

        # Register plugin with default priority
        registry = get_registry()
        registry.register(FmfPlugin)

        # Check default priority
        assert FmfPlugin.priority == 100

        # Override priority via config
        config = {
            "plugins": ["fmf"],
            "fmf": {
                "priority": 150
                }
            }
        registry.load_from_config(config)

        # Priority should be changed
        assert FmfPlugin.priority == 150

    def test_priority_override_invalid_value(self):
        """Test that invalid priority values are rejected."""
        from fmf.plugins.fmf import FmfPlugin

        registry = get_registry()
        registry.register(FmfPlugin)
        original_priority = FmfPlugin.priority

        # Try invalid priority (too high)
        config = {
            "plugins": ["fmf"],
            "fmf": {"priority": 300}
            }
        registry.load_from_config(config)

        # Priority should not change
        assert FmfPlugin.priority == original_priority

        # Try invalid priority (negative)
        config["fmf"]["priority"] = -10
        registry.load_from_config(config)
        assert FmfPlugin.priority == original_priority

        # Try invalid type
        config["fmf"]["priority"] = "high"
        registry.load_from_config(config)
        assert FmfPlugin.priority == original_priority

    def test_plugin_file_pattern_override_placeholder(self):
        """
        Placeholder test for file pattern override (Phase 2/3).

        In future phases, plugins should support configuration like:

        plugins:
          - fmf.plugins.python.PythonPlugin

        python:
          file_patterns:
            - "^check-.*\\.py$"
            - "^test_.*$"

        This would override the default plugin.file_patterns.
        """
        # This test is a placeholder for Phase 2/3
        # When implemented, it should:
        # 1. Load plugin with custom file_patterns from config
        # 2. Verify only matching files are processed
        # 3. Verify default patterns are overridden, not merged
        pass


# Integration test with real examples
class TestRealWorldExamples:
    """Test plugin system with real fmf examples."""

    def setup_method(self):
        """Ensure FmfPlugin is loaded for examples."""
        get_registry().clear()
        import importlib

        import fmf.plugins.fmf
        importlib.reload(fmf.plugins.fmf)

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
            priority = 50

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

    def test_plugin_priority_resolution(self):
        """Test that higher priority plugin wins when both can handle."""
        from fmf.plugins.fmf import FmfPlugin

        # Create another .fmf handler with lower priority
        class LowPriorityFmfPlugin(Plugin):
            extensions = [".fmf"]
            file_patterns = [r".*\.fmf$"]
            priority = 10  # Lower than FmfPlugin (100)

            def can_handle(self, filename):
                return filename.endswith(".fmf")

            def read(self, filename):
                return {"source": "low-priority"}

            def write(self, filename, hierarchy, data, append_dict,
                      modified_dict, deleted_items):
                pass

        registry = get_registry()
        registry.register(FmfPlugin)
        registry.register(LowPriorityFmfPlugin)

        # FmfPlugin should win due to higher priority
        plugin_class = registry.get_plugin_for_file("test.fmf")
        assert plugin_class == FmfPlugin
        assert plugin_class.priority == 100
