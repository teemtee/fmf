# FMF Plugin System - Future Development Roadmap

This document outlines the future phases of the FMF plugin system development. Phase 1 (the plugin infrastructure) has been completed. The following phases will add concrete plugin implementations.

## Phase 1: Plugin Infrastructure ✅ COMPLETED

**Status**: Implemented on `preparation_pyloader` branch

**What was delivered**:
- Abstract `Plugin` base class with `can_handle()`, `read()`, `write()` methods
- `PluginRegistry` for static plugin registration and management
- `FmfPlugin` - refactored .fmf file loading into the plugin system
- Integration into `Tree` class for seamless file loading
- Configuration support via `.fmf/config`
- Priority system (0-200 scale) with config override support
- Comprehensive unit and integration tests (275 tests)
- Backward compatibility - all existing tests pass
- Security: Only built-in plugins from `fmf/plugins/` can be loaded

**Key files**:
- `fmf/plugin.py` - Plugin ABC (148 lines)
- `fmf/plugin_loader.py` - Registry and loader (73 lines)
- `fmf/plugins/__init__.py` - Static registration (23 lines)
- `fmf/plugins/fmf.py` - FmfPlugin implementation (110 lines)
- `tests/unit/test_plugin.py` - Plugin tests (29 tests)

**Recent improvements**:
- Simplified plugin_loader from 169 to 73 lines
- Priority override via config (e.g., `fmf: { priority: 30 }`)
- Mock plugin tests to verify multi-format support
- Direct `can_handle()` filtering (supports regex patterns)

---

## Phase 2: Bash Plugin Implementation

**Goal**: Enable reading metadata from Bash scripts via specially formatted comments

**Priority**: Medium (useful for simple test scripts)

### Design Overview

Bash scripts can embed FMF metadata in comments using a special marker:

```bash
#!/bin/bash
# fmf-description: Basic wget test
# fmf-tag: [Tier1, TierSecurity]
# fmf-duration: 5m

# Test script content
wget --version
```

**Format**: `# fmf-<key>: <value>`
- Simple to parse with regex
- Non-invasive (just comments)
- Works with existing bash scripts

### Implementation Steps

1. **Create `fmf/plugins/bash.py`**
   - Class: `BashPlugin(Plugin)`
   - Extensions: `[".sh"]`
   - Priority: `50` (lower than FmfPlugin)
   - File patterns: Configurable, default `r".*\.sh$"`

2. **Implement `can_handle()`**
   - Check `.sh` extension
   - Optionally match against regex patterns from config

3. **Implement `read()`**
   - Parse file line by line
   - Look for `# fmf-<key>: <value>` pattern
   - Parse values (detect lists, numbers, booleans, strings)
   - Auto-add `test: ./<script-name>` if not specified
   - Return metadata dict

4. **Implement `write()`**
   - Use `_write_fmf_fallback()` to create `.fmf` file
   - Don't modify original bash script (safety)

5. **Register in `fmf/plugins/__init__.py`**
   ```python
   from fmf.plugins.bash import BashPlugin
   _registry.register(BashPlugin)
   PLUGIN_NAMES['bash'] = BashPlugin
   ```

6. **Configuration support**
   - Allow pattern override: `bash: { file_patterns: ["test_.*\\.sh"] }`
   - Allow priority override: `bash: { priority: 120 }`

7. **Testing**
   - Unit tests for metadata extraction
   - Test value parsing (lists, bools, numbers)
   - Test with Tree integration
   - Test priority vs FmfPlugin
   - Test write fallback creates .fmf

### Example Use Case

**Directory structure**:
```
tests/
  .fmf/
    version: 1
    config:
      plugins:
        - fmf
        - bash
  main.fmf          # Root metadata
  test-basic.sh     # Bash test with fmf comments
  test-wget.sh      # Another bash test
```

**test-basic.sh**:
```bash
#!/bin/bash
# fmf-description: Basic functionality test
# fmf-tag: [Tier1]
# fmf-duration: 2m

wget --version
```

**Result**: Tree has child node `/test-basic` with metadata from comments.

### Migration Notes

- Existing bash scripts work without changes
- Add `# fmf-*` comments to enable metadata extraction
- If both `test.sh` and `test.fmf` exist, FmfPlugin wins (priority 100 > 50)
- Override with `bash: { priority: 120 }` to prefer .sh files

---

## Phase 3: Python/Pytest Plugin Implementation

**Goal**: Extract metadata from Python test files using pytest marks, docstrings, and decorators

**Priority**: High (pytest is widely used in testing)

### Design Overview

Extract metadata from Python tests using existing pytest conventions:

```python
import pytest

@pytest.mark.tier1
@pytest.mark.security
def test_basic_auth():
    """Test basic authentication flow.

    Duration: 5m
    Author: jscotka@redhat.com
    """
    assert authenticate("user", "pass")
```

**Sources of metadata**:
1. **Pytest marks** → `tag` field
2. **Docstrings** → `description` and custom fields
3. **Function name** → node name
4. **Module path** → hierarchy

### Implementation Steps

1. **Create `fmf/plugins/pytest.py`**
   - Class: `PytestPlugin(Plugin)`
   - Extensions: `[".py"]`
   - Priority: `50`
   - File patterns: Default `r"test_.*\.py$|.*_test\.py$"`

2. **Implement `can_handle()`**
   - Check `.py` extension
   - Match against test file patterns
   - Optionally check for pytest imports (AST parsing)

3. **Implement `read()`**
   - Use AST parsing (not execution - security!)
   - Find test functions (`def test_*` or `@pytest.mark.*`)
   - Extract pytest marks → convert to tags
   - Parse docstrings for description and custom fields
   - Build hierarchical dict (module → classes → functions)
   - Return nested metadata structure

4. **Docstring parsing**
   - First paragraph → `description`
   - YAML frontmatter → custom fields
   - Key-value pairs like `Duration: 5m` → custom fields

5. **Pytest mark mapping**
   ```
   @pytest.mark.tier1 → tag: [tier1]
   @pytest.mark.parametrize → note in metadata
   ```

6. **Implement `write()`**
   - Use `_write_fmf_fallback()` (don't modify Python code)

7. **Register in `fmf/plugins/__init__.py`**
   ```python
   from fmf.plugins.pytest import PytestPlugin
   _registry.register(PytestPlugin)
   PLUGIN_NAMES['pytest'] = PytestPlugin
   ```

8. **Configuration support**
   - Pattern override: `pytest: { file_patterns: ["check_.*\\.py"] }`
   - Mark mapping: Custom mark → tag conversions
   - Priority override: `pytest: { priority: 150 }`

9. **Testing**
   - Test AST parsing of various test patterns
   - Test mark extraction
   - Test docstring parsing
   - Test nested classes
   - Test parametrized tests
   - Tree integration tests

### Example Use Case

**test_auth.py**:
```python
import pytest

@pytest.mark.tier1
class TestAuthentication:
    """Authentication test suite."""

    @pytest.mark.security
    def test_basic_login(self):
        """Test basic login flow.

        Duration: 3m
        """
        assert login("user", "pass")

    def test_logout(self):
        """Test logout functionality."""
        assert logout()
```

**Result hierarchy**:
```
/test_auth
  /TestAuthentication
    /test_basic_login
      description: Test basic login flow.
      tag: [tier1, security]
      duration: 3m
    /test_logout
      description: Test logout functionality.
      tag: [tier1]
```

### Security Considerations

- **Never execute Python code** - use AST parsing only
- **No eval()** - parse docstrings as text/YAML
- **Sandboxing not needed** - static analysis only

### Challenges

1. **Parametrize handling**: Multiple test instances from one function
2. **Fixtures**: How to represent fixture dependencies?
3. **Class hierarchy**: Map to FMF tree structure
4. **Dynamic marks**: Marks applied via `pytestmark` variable

**Solutions**:
- Start with simple cases (function-level marks)
- Document limitations
- Iterate based on user feedback

---

## Phase 4: Write-Back Support

**Goal**: Enable plugins to write modifications back to original file format

**Priority**: Low (most metadata is read-only)

### Current State

- All plugins use `_write_fmf_fallback()`
- Creates `.fmf` file alongside original
- Safe but creates extra files

### Design Options

1. **FmfPlugin**: Full write-back support
   - Already partially implemented in `Tree.__exit__()`
   - Needs proper YAML round-trip preservation
   - Handle merges, deletions, hierarchy

2. **BashPlugin**: Limited write-back
   - Update existing `# fmf-*` comments
   - Add new comments at top of file
   - Preserve script content
   - **Risk**: May break script syntax

3. **PytestPlugin**: No write-back
   - Too risky to modify Python code
   - Keep using `.fmf` fallback

### Implementation Steps (FmfPlugin only)

1. **Enhance `FmfPlugin.write()`**
   - Current: Raises `NotImplementedError`
   - New: Use `dict_to_yaml()` from utils
   - Handle hierarchy paths correctly
   - Preserve comments and formatting (ruamel.yaml)

2. **Handle merge operations**
   - Track `append_dict` (keys with `+`)
   - Merge lists, concatenate values
   - Preserve original + append in output

3. **Handle deletions**
   - Track `deleted_items`
   - Remove from YAML structure
   - Don't write deleted keys

4. **Testing**
   - Round-trip tests (read → modify → write → read)
   - Test hierarchy writes
   - Test merge operations
   - Test deletions
   - Test comment preservation

5. **Tree integration**
   - Current `__exit__()` already calls plugin.write()
   - Ensure correct parameters passed
   - Test with context manager usage

### Example

```python
with Tree("/path/to/metadata") as data:
    data["tier"] = 2
    data["tags+"] = ["NewTag"]  # Append

# Writes back to main.fmf with changes
```

---

## Configuration System (All Phases)

### Current Config Format

```yaml
plugins:
  - fmf
  - bash
  - pytest

# Plugin-specific settings
fmf:
  priority: 100

bash:
  priority: 50
  file_patterns:
    - "test_.*\\.sh$"
    - "runtest\\.sh$"

pytest:
  priority: 50
  file_patterns:
    - "test_.*\\.py$"
    - ".*_test\\.py$"
```

### Features to Add

1. **Include/exclude directories** (per plugin)
   ```yaml
   pytest:
     include_dirs:
       - tests/
       - checks/
     exclude_dirs:
       - tests/integration/  # Too slow
   ```

2. **Pattern overrides** (Phase 2/3)
   - Override default `file_patterns`
   - Per-plugin basis

3. **Mark mappings** (Phase 3)
   ```yaml
   pytest:
     mark_mappings:
       tier1: Tier1
       security: Security
   ```

---

## Testing Strategy

### Per-Plugin Tests

Each plugin needs:
1. **Unit tests**: Parsing, value extraction
2. **Integration tests**: Tree loading
3. **Priority tests**: Conflicts with other plugins
4. **Config tests**: Pattern overrides, priority overrides
5. **Write tests**: Fallback creation

### Cross-Plugin Tests

1. **Mixed format trees**: `.fmf` + `.sh` + `.py` in same tree
2. **Priority resolution**: Multiple plugins for same extension
3. **Config validation**: Invalid plugin names, bad priorities

### Regression Tests

1. **Backward compatibility**: Existing examples still work
2. **No plugin config**: Default FmfPlugin-only mode
3. **Performance**: Plugin overhead is minimal

---

## Documentation Updates

### For Each Phase

1. **docs/concept.rst**: Add plugin to "Available Plugins" section
2. **Examples**: Create example tree in `examples/<plugin-name>/`
3. **README**: Mention new plugin capability
4. **PLUGIN_FUTURE.md**: Mark phase as completed

### User Guide Sections Needed

1. **When to use which plugin**: Decision tree
2. **Migration guide**: Adding plugins to existing trees
3. **Troubleshooting**: Common issues and solutions
4. **Performance tips**: Large trees, many files

---

## Success Criteria

### Phase 2 (Bash)
- [ ] BashPlugin reads metadata from `# fmf-*` comments
- [ ] Configurable file patterns work
- [ ] Priority override works
- [ ] Write fallback creates `.fmf` files
- [ ] Tests: 10+ new tests, all pass
- [ ] Documentation updated
- [ ] Example tree created

### Phase 3 (Pytest)
- [ ] PytestPlugin parses test files with AST
- [ ] Pytest marks → tags conversion works
- [ ] Docstring → description extraction works
- [ ] Hierarchical structure (class/function) works
- [ ] No code execution (security)
- [ ] Tests: 15+ new tests, all pass
- [ ] Documentation updated
- [ ] Example tree created

### Phase 4 (Write-back)
- [ ] FmfPlugin writes back to `.fmf` files
- [ ] Round-trip preserves data
- [ ] Merge operations work
- [ ] Deletions work
- [ ] Comments preserved
- [ ] Tests: 10+ new tests, all pass
- [ ] Documentation updated

---

## Future Enhancements

### Additional Plugins (Beyond Phase 4)

1. **JSON/YAML Plugin**: Read metadata from generic JSON/YAML files
2. **Markdown Plugin**: Extract from frontmatter or special sections
3. **Ansible Plugin**: Read from playbook/role metadata
4. **Beakerlib Plugin**: Parse beakerlib test metadata

### Plugin Discovery

- Auto-detect plugins in user directories?
- Plugin marketplace/registry?
- **Security**: Keep restriction to built-in only

### Performance Optimizations

- Cache plugin.can_handle() results
- Lazy plugin loading
- Parallel file processing

### Advanced Features

- **Validation**: JSON Schema per plugin
- **Linting**: Warn about common metadata issues
- **Migration tools**: Convert between formats
- **Templates**: Generate skeleton files per plugin

---

## Security Model

### Current (Phase 1)

✅ **Only built-in plugins** from `fmf/plugins/` directory
✅ **No dynamic loading** from environment or arbitrary paths
✅ **Static registration** in `fmf/plugins/__init__.py`
✅ **Config validation** against known plugin names

### Future Phases

✅ **No code execution** (especially Python plugin - AST only)
✅ **No eval()** or similar dynamic evaluation
✅ **Safe parsing** only (YAML, regex, AST)
⚠️ **Write operations** are limited to prevent corruption

### Threat Model

**Out of scope**: Malicious .fmf/config files
- User controls config → can break their own tree
- No remote/untrusted trees processed

**In scope**: Prevent arbitrary code execution
- No loading external plugins
- No executing test code during read
- No dangerous YAML tags (use `typ="safe"`)

---

## Migration Guide (for users)

### Adding Bash Plugin to Existing Tree

1. Update `.fmf/config`:
   ```yaml
   plugins:
     - fmf
     - bash
   ```

2. Add metadata to bash scripts:
   ```bash
   # fmf-description: My test
   # fmf-tag: [Tier1]
   ```

3. Verify: `fmf ls` should show both `.fmf` and `.sh` nodes

### Adding Pytest Plugin

1. Update `.fmf/config`:
   ```yaml
   plugins:
     - fmf
     - pytest
   ```

2. Add pytest marks to tests (if not present):
   ```python
   @pytest.mark.tier1
   def test_foo():
       """Test description."""
       pass
   ```

3. Verify: `fmf ls` shows Python test functions as nodes

### Priority Override

If both `.sh` and `.fmf` exist, choose which wins:

```yaml
bash:
  priority: 120  # Bash wins over FmfPlugin (100)
```

---

## References

- **Original issue**: https://github.com/teemtee/fmf/issues/103
- **POC branch**: `py_plugin` (reference implementation)
- **Phase 1 PR**: `preparation_pyloader` branch
- **Plugin ABC**: `fmf/plugin.py`
- **Registry**: `fmf/plugin_loader.py`
