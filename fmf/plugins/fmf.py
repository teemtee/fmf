"""
FMF Plugin - YAML-based metadata loader
"""

from typing import Any, Dict

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

import fmf.utils as utils
from fmf.plugin import Plugin
from fmf.utils import dict_to_yaml, log

# Constants for .fmf files (moved from base.py)
SUFFIX = ".fmf"
MAIN = "main" + SUFFIX


class FmfPlugin(Plugin):
    """
    Plugin for reading .fmf (YAML) files.

    This is the default built-in plugin that handles traditional fmf metadata.
    Uses ruamel.yaml for better round-trip support and consistency with master.
    """

    extensions = [SUFFIX]
    file_patterns = [r".*\.fmf$"]
    priority = 100  # Default format priority (0-200 scale, overridable in config)
    CONFIG_SECTION = "fmf"

    def __init__(self):
        """Initialize FmfPlugin with YAML loader."""
        # Use ruamel.yaml for consistency with master branch
        # typ="safe" provides safe loading without code execution
        self._yaml = YAML(typ="safe")

    def can_handle(self, filename: str) -> bool:
        """
        Check if file has .fmf extension.

        Args:
            filename: Name or path of file to check

        Returns:
            True if filename ends with .fmf
        """
        return filename.endswith(SUFFIX)

    def read(self, filename: str) -> Dict[str, Any]:
        """
        Read YAML content from .fmf file.

        This is extracted from the original Tree.grow() method (lines 734-742).
        Uses ruamel.yaml for better compatibility and round-trip support.

        Args:
            filename: Path to .fmf file

        Returns:
            Dictionary with metadata, or empty dict if file is empty

        Raises:
            FileError: If file cannot be parsed or contains duplicate keys
        """
        try:
            with open(filename, encoding='utf-8') as datafile:
                content = datafile.read()
                data = self._yaml.load(content)
                log.debug(f"Loaded .fmf file: {filename}")
                # YAML loader returns None for empty files
                return data if data is not None else {}

        except YAMLError as error:
            raise utils.FileError(
                f"Failed to parse '{filename}'.\n{error}")
        except Exception as error:
            raise utils.FileError(
                f"Error reading '{filename}'.\n{error}")

    def write(
            self,
            filename: str,
            hierarchy,  # noqa: ARG002
            data,
            append_dict,  # noqa: ARG002
            modified_dict,  # noqa: ARG002
            deleted_items) -> None:  # noqa: ARG002
        """
        Write metadata back to .fmf file.

        This uses the existing fmf write functionality which stores
        the complete raw data structure to the source file.

        Args:
            filename: Path to .fmf file
            hierarchy: Hierarchy path (not used - data already structured)
            data: Complete data structure to write (already includes hierarchy)
            append_dict: Append operations (not used - already merged in data)
            modified_dict: Modified data (not used - already merged in data)
            deleted_items: Deleted keys (not used - already removed from data)

        Note:
            The data parameter already contains the full hierarchical structure
            as prepared by Tree._locate_raw_data(). We just need to write it
            to the YAML file.
        """
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(dict_to_yaml(data))
