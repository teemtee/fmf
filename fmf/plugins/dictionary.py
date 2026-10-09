"""Backend for raw dictionaries and virtual in-memory trees."""

import fmf.utils as utils
from fmf.plugins._base import Plugin


class DictionaryPlugin(Plugin):
    """Use FMF dictionary semantics without a filesystem source."""

    writable = True

    def grow(self, tree, data):
        self.load(tree, data)

    def locate(self, tree):
        """Find the raw mapping for a virtual node and its source-owning ancestor."""
        hierarchy = []
        node = tree
        while node._source_plugin is None:
            if node.parent is None:
                raise utils.GeneralError("No raw data found for this node.")
            hierarchy.insert(0, '/' + node.name.rsplit('/')[-1])
            node = node.parent
        if node._raw_data is None:
            node._raw_data = {}
        full_data = node._raw_data
        data = full_data
        while hierarchy:
            # Prefer an existing compact path, including partially compact
            # paths such as /one/two followed by a nested /three mapping.
            for count in range(len(hierarchy), 0, -1):
                key = ''.join(hierarchy[:count])
                if key in data:
                    break
            if data.get(key) is None:
                data[key] = {}
            data = data[key]
            hierarchy = hierarchy[count:]
        return data, full_data, node

    def read(self, node):
        return self.locate(node)[0]

    def write(self, node):
        """Edits already reside in the owned raw mapping; there is no disk I/O."""
        return None
