import os
import re

from fmf.plugin_loader import Plugin
from fmf.utils import log


class Bash(Plugin):
    extensions = [".sh"]
    file_patters = ["test.*"]

    @staticmethod
    def update_data(filename, pattern="^#.*:FMF:"):
        out = dict(test="./" + os.path.basename(filename))
        with open(filename) as fd:
            for line in fd.readlines():
                if re.match(pattern, line):
                    item = re.match(
                        r"{}\s*(.*)".format(pattern),
                        line).groups()[0]
                    identifier, value = item.split(":", 1)
                    out[identifier] = value.lstrip(" ")
        return out

    def read(self, file_name):
        log.info("Processing Item: {}".format(file_name))
        return self.update_data(file_name)
