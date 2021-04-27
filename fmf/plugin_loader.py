import importlib
import inspect
import os
import re
from functools import lru_cache

import yaml

from fmf.constants import PLUGIN_ENV, SUFFIX
from fmf.utils import log


class Plugin:
    """
    Main abstact class for FMF plugins
    """
    # you have to define extension list as class attribute e.g. [".py"]
    extensions = list()
    file_patters = list()

    def read(self, filename):
        """
        return python dictionary representation of metadata inside file (FMF structure)
        """
        raise NotImplementedError("Define own impementation")

    @staticmethod
    def __define_undefined(hierarchy, modified, append):
        output = dict()
        current = output
        for key in hierarchy:
            if key not in current or current[key] is None:
                current[key] = dict()
            current = current[key]
        for k, v in modified.items():
            current[k] = v
        for k, v in append.items():
            current[k] = v
        return output

    def write(
            self, filename, hierarchy, data, append_dict, modified_dict,
            deleted_items):
        """
        Write data in dictionary representation back to file, if not defined, create new fmf file with same name.
        When created, nodes will not use plugin method anyway
        """
        path = os.path.dirname(filename)
        basename = os.path.basename(filename)
        current_extension = list(
            filter(
                lambda x: basename.endswith(x),
                self.extensions))[0]
        without_extension = basename[0:-len(list(current_extension))]
        fmf_file = os.path.join(path, without_extension + ".fmf")
        with open(fmf_file, "w") as fd:
            yaml.safe_dump(
                self.__define_undefined(
                    hierarchy,
                    modified_dict,
                    append_dict),
                stream=fd)


@lru_cache(maxsize=None)
def enabled_plugins(*plugins):
    plugins = os.getenv(PLUGIN_ENV).split(
        ",") if os.getenv(PLUGIN_ENV) else plugins
    plugin_list = list()
    for item in plugins:
        if os.path.exists(item):
            loader = importlib.machinery.SourceFileLoader(
                os.path.basename(item), item)
            module = importlib.util.module_from_spec(
                importlib.util.spec_from_loader(loader.name, loader)
                )
            loader.exec_module(module)
        else:
            module = importlib.import_module(item)
        for name, plugin in inspect.getmembers(module):
            if inspect.isclass(plugin) and plugin != Plugin and issubclass(
                    plugin, Plugin):
                plugin_list.append(plugin)
                log.info("Loaded plugin {}".format(plugin))
    return plugin_list


def get_suffixes(*plugins):
    output = [SUFFIX]
    for item in enabled_plugins(*plugins):
        output += item.extensions
    return output


def get_plugin_for_file(filename, *plugins):
    extension = "." + filename.rsplit(".", 1)[1]
    for item in enabled_plugins(*plugins):
        if extension in item.extensions and any(
            filter(
                lambda x: re.search(
                    x,
                    filename),
                item.file_patters)):
            log.debug("File {} parsed by by plugin {}".format(filename, item))
            return item
