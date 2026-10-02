"""fmf plugin handling ``.fmf`` files."""

from copy import deepcopy
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from fmf.plugin import Plugin
from fmf.utils import FileError, dict_to_yaml

SUFFIX = ".fmf"
MAIN = "main" + SUFFIX


class FmfPlugin(Plugin):
    """Read and write YAML metadata."""

    #: Configuration section for the YAML loader.
    CONFIG_SECTION: ClassVar[str] = "fmf"

    def __init__(self):
        self._yaml = YAML(typ="safe")

    def __deepcopy__(self, memo):
        """Copy tree settings while recreating the non-copyable YAML parser."""
        duplicate = type(self).__new__(type(self))
        memo[id(self)] = duplicate
        for key, value in self.__dict__.items():
            if key != '_yaml':
                setattr(duplicate, key, deepcopy(value, memo))
        duplicate._yaml = YAML(typ='safe')
        return duplicate

    def read_config(self, config: Dict[str, Any]) -> None:
        self.settings = self.config_section_data(config)

    def can_handle(self, filename: str) -> bool:
        return filename.endswith(SUFFIX)

    def read(self, filename: str) -> Dict[str, Any]:
        """Read YAML while retaining raw hierarchy and merge keys."""
        try:
            # Read text first for compatibility with ruamel on s390x (#164).
            data = self._yaml.load(Path(filename).read_text(encoding='utf-8'))
            return data if data is not None else {}
        except (YAMLError, OSError) as error:
            # A parser may retain invalid state after an unsuccessful load.
            self._yaml = YAML(typ="safe")
            raise FileError(f"Failed to read '{filename}'.\n{error}") from error

    def write(
            self,
            filename: str,
            hierarchy: List[str],
            data: Dict[str, Any],
            append_dict: Dict[str, Any],
            modified_dict: Dict[str, Any],
            deleted_items: List[str]) -> None:
        """Serialize the complete raw source data, including virtual nodes."""
        Path(filename).write_text(dict_to_yaml(data), encoding='utf-8')
