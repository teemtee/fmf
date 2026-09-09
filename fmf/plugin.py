"""
Abstract Plugin Base Class for FMF Metadata Loaders
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern


class Plugin(ABC):
    """
    Abstract base class for FMF metadata loaders.

    Each plugin handles one or more file extensions and provides
    methods to read and write metadata in those formats.

    Subclasses must define:
        - extensions: List of file extensions (e.g., [".fmf", ".sh"])
        - read(): Method to extract metadata from a file
        - read_config(): Method to read the plugin's own config section

    Optional:
        - file_patterns: List of regex patterns to match filenames
        - can_handle(): Override only for matching that neither ``extensions``
          nor ``file_patterns`` can express
        - write(): Method to write metadata back (default: fallback to .fmf)
        - config_section: Name of the plugin's section in ``.fmf/config``
    """

    # Class attributes to be defined by subclasses
    extensions: List[str] = []  # File extensions, e.g., [".fmf"]
    file_patterns: List[str] = []  # Regex patterns for filenames
    # Name of this plugin's section in the .fmf/config file (None = no section)
    config_section: Optional[str] = None

    @classmethod
    def _compiled_patterns(cls) -> List[Pattern[str]]:
        """
        Return this plugin's :attr:`file_patterns` compiled to regex objects.

        The patterns are compiled once and cached on the class. can_handle()
        is called for every file in a tree, so compiling on each call (or
        relying on the standard library's evictable regex cache) would add an
        avoidable per-file cost on large trees.
        """
        # Use the class' own __dict__ so subclasses do not reuse a parent cache
        cache = cls.__dict__.get("_file_patterns_re")
        if cache is None:
            cache = [re.compile(pattern) for pattern in cls.file_patterns]
            cls._file_patterns_re = cache  # type: ignore[attr-defined]
        return cache

    def can_handle(self, filename: str) -> bool:
        """
        Determine if this plugin can handle the given file.

        The default checks the cheap :attr:`extensions` first (a plain suffix
        test) and only then the precompiled :attr:`file_patterns`. Override
        this only when matching needs logic those two cannot express.

        Args:
            filename: Absolute or relative path to file

        Returns:
            True if plugin can read this file, False otherwise
        """
        if any(filename.endswith(extension) for extension in self.extensions):
            return True
        return any(pattern.search(filename) for pattern in self._compiled_patterns())

    def config_section_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return this plugin's own section from the parsed ``.fmf/config``.

        Args:
            config: The parsed ``.fmf/config`` dictionary (may be empty).

        Returns:
            The mapping stored under :attr:`config_section`, or an empty
            dict when the plugin has no section or the section is missing
            or not a mapping.
        """
        if not self.config_section:
            return {}
        section = config.get(self.config_section, {})
        return section if isinstance(section, dict) else {}

    @abstractmethod
    def read_config(self, config: Dict[str, Any]) -> None:
        """
        Read this plugin's own section from the ``.fmf/config`` data.

        Called with the whole parsed config so the plugin can pick up its
        own :attr:`config_section` (use :meth:`config_section_data`) and
        apply the settings to itself.

        Called once per tree (the config is identical for every node), so
        implementations should store what they need on the instance rather
        than re-reading the config for each file.

        Args:
            config: The parsed ``.fmf/config`` dictionary (may be empty).
        """
        pass

    @abstractmethod
    def read(self, filename: str) -> Dict[str, Any]:
        """
        Read metadata from file and return as dictionary.

        Args:
            filename: Path to file to read

        Returns:
            Dictionary with fmf metadata structure. Can be nested
            for hierarchical metadata (e.g., test classes with methods).

        Raises:
            FileError: If file cannot be read or parsed
        """
        pass

    @abstractmethod
    def write(
            self,
            filename: str,
            hierarchy: List[str],
            data: Dict[str, Any],
            append_dict: Dict[str, Any],
            modified_dict: Dict[str, Any],
            deleted_items: List[str]) -> None:
        """
        Write modified metadata back to file.

        Why the rich signature: fmf raw data encodes merge semantics as
        literal keys -- ``tier``, ``tier+`` (append) and ``tier-`` (delete)
        all sit in ``data`` as ordinary keys. A YAML/.fmf writer therefore
        round-trips them for free by simply dumping ``data``. Other formats
        (bash comments, pytest sources) have no native way to express
        append/delete or nesting, so they need this information handed to
        them decomposed: ``hierarchy`` for the location, and
        ``append_dict`` / ``modified_dict`` / ``deleted_items`` for the
        per-key operations. Keeping the parameters lets those plugins be
        written without re-deriving merge semantics from suffixed keys.

        Args:
            filename: Original file path
            hierarchy: Virtual node names from the source node down to this
                node (e.g. ["/parent", "/child"]); empty when the node is
                itself file-backed.
            data: Complete raw data structure of the source file, with all
                in-place modifications and ``key+`` / ``key-`` merge keys
                already present. Sufficient on its own for round-trip
                (YAML) writers.
            append_dict: Keys with ``+`` suffix (merge operations).
            modified_dict: Modified keys (plain replacements).
            deleted_items: Keys with ``-`` suffix (removals).

        Note:
            The current experimental store passes ``data`` fully populated
            but does not yet track the decomposed ``append_dict`` /
            ``modified_dict`` / ``deleted_items`` (they arrive empty); only
            ``hierarchy`` and ``data`` are populated so far. Non-round-trip
            plugins should therefore treat those as a forward-looking
            contract for now.

        Raises:
            NotImplementedError: If plugin doesn't support writing

        Note:
            If your plugin cannot write back to the original format,
            you can use self._write_fmf_fallback() to create a .fmf file
            with the same base name instead.
        """
        pass

    def _write_fmf_fallback(
            self,
            filename: str,
            hierarchy: List[str],
            modified_dict: Dict[str, Any],
            append_dict: Dict[str, Any]) -> None:
        """
        Create a .fmf file as fallback for plugins that can't write.

        This method constructs the hierarchical structure based on
        the hierarchy path and writes it to a .fmf file alongside
        the original file.

        Args:
            filename: Original file path
            hierarchy: Path components from tree root
            modified_dict: Modified keys to write
            append_dict: Append operations (keys with +)
        """
        from ruamel.yaml import YAML

        # Build hierarchical dictionary from hierarchy path
        output: Dict[str, Any] = {}
        current = output

        for key in hierarchy:
            if key not in current or current[key] is None:
                current[key] = {}
            current = current[key]

        # Add modified data to the leaf node
        current.update(modified_dict)

        # Add append operations
        for key, value in append_dict.items():
            # Use key+ notation for append operations
            current[key + '+'] = value

        # Generate .fmf filename from original file, replacing the plugin's
        # extension (if any) with the .fmf suffix.
        source = Path(filename)
        for ext in self.extensions:
            if source.name.endswith(ext):
                source = source.with_name(source.name[:-len(ext)])
                break
        fmf_file = source.with_name(source.name + ".fmf")

        # Write YAML to .fmf file
        yaml = YAML()
        yaml.default_flow_style = False

        with fmf_file.open('w', encoding='utf-8') as f:
            yaml.dump(output, f)
