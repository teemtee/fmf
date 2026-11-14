"""Backend for raw dictionaries and virtual in-memory trees."""

import re
from pprint import pformat as pretty

import fmf.utils as utils
from fmf.plugins._base import Plugin
from fmf.utils import log


class DictionaryPlugin(Plugin):
    """Use FMF dictionary semantics without a filesystem source."""

    writable = True

    def grow(self, tree, data):
        self.load(tree, data)

    def update(self, node, data):
        """
        Interpret dictionary metadata, virtual paths and FMF directives.

        Only update the hierarchy: the calling plugin keeps ownership of
        source data, merge semantics and storage, including for children.
        """

        # Make a note that the data dictionary has been updated
        # None is handled in the same way as an empty dictionary
        node._updated = True
        # Nothing to do if no data
        if data is None:
            return

        # Interpret directives without modifying the supplied source mapping.
        if "/" in data:
            node._process_directives(data["/"])

        # Process the metadata
        for key, value in data.items():
            if key == "/":
                continue
            # Ensure there are no 'None' keys
            if key is None:
                raise utils.FormatError("Invalid key 'None'.")
            # Handle child attributes
            if key.startswith('/'):
                name = key.lstrip('/')
                # Handle deeper nesting (e.g. keys like /one/two/three) by
                # extracting only the first level of the hierarchy as name
                match = re.search("([^/]+)(/.*)", name)
                if match:
                    name = match.groups()[0]
                    value = {match.groups()[1]: value}
                # Update existing child or create a new one
                node.child(name, value)
            # Update regular attributes
            else:
                node.data[key] = value
        log.debug("Data for '{0}' updated.".format(node))
        log.data(pretty(node.data))

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
