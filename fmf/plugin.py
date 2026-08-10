"""
Abstract Plugin Base Class for FMF Metadata Loaders
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Plugin(ABC):
    """
    Abstract base class for FMF metadata loaders.

    Each plugin handles one or more file extensions and provides
    methods to read and write metadata in those formats.

    Subclasses must define:
        - extensions: List of file extensions (e.g., [".fmf", ".sh"])
        - file_patterns: List of regex patterns to match filenames
        - priority: Integer 0-200, higher values preferred for conflicts
        - can_handle(): Method to determine if plugin can handle a file
        - read(): Method to extract metadata from a file

    Optional:
        - write(): Method to write metadata back (default: fallback to .fmf)
        - CONFIG_SECTION: Name of config section in .fmf/config
    """

    # Class attributes to be defined by subclasses
    extensions: List[str] = []  # File extensions, e.g., [".fmf"]
    file_patterns: List[str] = []  # Regex patterns for filenames
    priority: int = 50  # 0-200, higher = preferred when conflicts occur
    CONFIG_SECTION: Optional[str] = None  # Config section name

    @abstractmethod
    def can_handle(self, filename: str) -> bool:
        """
        Determine if this plugin can handle the given file.

        Args:
            filename: Absolute or relative path to file

        Returns:
            True if plugin can read this file, False otherwise
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

        Args:
            filename: Original file path
            hierarchy: Path components from tree root (e.g., ["/parent", "/child"])
            data: Complete node data dictionary
            append_dict: Keys with + suffix (merge operations)
            modified_dict: Modified keys
            deleted_items: List of removed keys

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
        import os

        from ruamel.yaml import YAML

        # Build hierarchical dictionary from hierarchy path
        output = {}
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

        # Generate .fmf filename from original file
        path = os.path.dirname(filename)
        basename = os.path.basename(filename)

        # Remove original extension
        for ext in self.extensions:
            if basename.endswith(ext):
                basename = basename[:-len(ext)]
                break

        fmf_file = os.path.join(path, basename + ".fmf")

        # Write YAML to .fmf file
        yaml = YAML()
        yaml.default_flow_style = False

        with open(fmf_file, 'w', encoding='utf-8') as f:
            yaml.dump(output, f)
