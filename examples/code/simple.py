#!/usr/bin/python

import fmf

# Browse directory with wget example metadata
for node in fmf.Tree("../wget").climb():
    try:
        # List nodes with "test" attribute defined and "Tier2" in tags
        if "test" in node.data and "Tier2" in node.data["tags"]:
            print(node.show())
    except KeyError:
        pass
