import ast
import importlib
import inspect
import os
import re
import shlex
from multiprocessing import Process, Queue

import pytest
import yaml

from fmf.plugin_loader import Plugin
from fmf.plugins.pytest.constants import (CONFIG_ADDITIONAL_KEY,
                                          CONFIG_MERGE_MINUS,
                                          CONFIG_MERGE_PLUS,
                                          CONFIG_POSTPROCESSING_TEST,
                                          PYTEST_DEFAULT_CONF)
from fmf.plugins.pytest.tmt_semantic import (DESCRIPTION_KEY,
                                             FMF_POSTFIX_MARKS, SUMMARY_KEY,
                                             TMT, TMT_ATTRIBUTES,
                                             fmf_prefixed_name)
from fmf.utils import GeneralError, log

_ = shlex


class _Test:
    def __init__(self, test):
        self.test = test
        if hasattr(test, "_testMethodName"):
            self.name = test._testMethodName
            self.method = getattr(test.__class__, test._testMethodName)
        else:
            self.name = test.function.__name__
            self.method = test.function


class _TestCls:
    def __init__(self, test_class, filename):
        self.file = filename
        self.cls = test_class
        self.name = test_class.__name__ if test_class is not None else None
        self.tests = []


class ItemsCollector:
    # current solution based on
    # https://github.com/pytest-dev/pytest/discussions/8554
    def pytest_collection_modifyitems(self, items):
        self.items = items[:]


def default_key(parent_dict, key, empty_obj):
    if key not in parent_dict:
        output = empty_obj
        parent_dict[key] = output
        return output
    return parent_dict[key]


def __get_fmf_attr_name(method, attribute):
    for current_attr in [fmf_prefixed_name(attribute + x)
                         for x in FMF_POSTFIX_MARKS]:
        if hasattr(method, current_attr):
            return current_attr
    return fmf_prefixed_name(attribute)


def __update_dict_key(method, key, fmf_key, dictionary, override_postfix=""):
    """
    This function have to ensure that there is righ one of attribute type extension
    and removes all others
    """
    value = None
    current_postfix = ""
    # find if item is defined inside method
    for attribute in dir(method):
        stripped = attribute.rstrip("".join(FMF_POSTFIX_MARKS))
        if key == stripped:
            value = getattr(method, attribute)
            strip_len = len(stripped)
            current_postfix = attribute[strip_len:]
    # delete all keys in dictionary started with fmf_key
    for item in dictionary.copy():
        stripped = item.rstrip("".join(FMF_POSTFIX_MARKS))
        if stripped == fmf_key:
            dictionary.pop(item)
    out_key = (
        fmf_key + override_postfix
        if override_postfix else fmf_key + current_postfix)
    if value is not None:
        dictionary[out_key] = value


def multiline_eval(expr, context, type_ignores=None):
    """Evaluate several lines of input, returning the result of the last line
    https://stackoverflow.com/questions/12698028/why-is-pythons-eval-rejecting-this-multiline-string-and-how-can-i-fix-it
    """
    tree = ast.parse(expr)
    eval_expr = ast.Expression(tree.body[-1].value)
    exec_expr = ast.Module(tree.body[:-1], type_ignores=type_ignores or [])
    exec(compile(exec_expr, "file", "exec"), context)
    return eval(compile(eval_expr, "file", "eval"), context)


def __post_processing(input_dict, config_dict, cls, test, filename):
    if isinstance(config_dict, dict):
        for k, v in config_dict.items():
            if isinstance(v, dict):
                if k not in input_dict:
                    input_dict[k] = dict()
                __post_processing(input_dict[k], v, cls, test, filename)
            else:
                input_dict[k] = multiline_eval(v, dict(locals(), **globals()))


def read_config(config_file):
    if not os.path.exists(config_file):
        raise GeneralError(
            f"configuration files does not exists {config_file}")
    log.info(f"Read config file: {config_file}")
    with open(config_file) as fd:
        return yaml.safe_load(fd)


def test_data_dict(test_dict, config, filename, cls, test,
                   merge_plus_list=None, merge_minus_list=None):
    merge_plus_list = merge_plus_list or config.get(CONFIG_MERGE_PLUS, [])
    merge_minus_list = merge_minus_list or config.get(CONFIG_MERGE_MINUS, [])
    doc_str = (test.method.__doc__ or "").strip("\n")
    # set summary attribute if not given by decorator
    current_name = __get_fmf_attr_name(test.method, SUMMARY_KEY)
    if not hasattr(test.method, current_name):
        # try to use first line of docstring if given
        if doc_str:
            summary = doc_str.split("\n")[0].strip()
        else:
            summary = (
                (f"{os.path.basename(filename)} " if filename else "")
                + (f"{cls.name} " if cls.name else "")
                + test.name
                )
        setattr(test.method, current_name, summary)

    # set description attribute by docstring if not given by decorator
    current_name = __get_fmf_attr_name(test.method, DESCRIPTION_KEY)
    if not hasattr(test.method, current_name):
        # try to use first line of docstring if given
        if doc_str:
            description = doc_str
            setattr(test.method, current_name, description)
    # generic FMF attributes set by decorators
    for key in TMT_ATTRIBUTES:
        # Allow to override key storing with merging postfixes
        override_postfix = ""
        if key in merge_plus_list:
            override_postfix = "+"
        elif key in merge_minus_list:
            override_postfix = "-"
        __update_dict_key(
            test.method,
            fmf_prefixed_name(key),
            key,
            test_dict,
            override_postfix,
            )

    # special config items
    if CONFIG_ADDITIONAL_KEY in config:
        for key, fmf_key in config[CONFIG_ADDITIONAL_KEY].items():
            __update_dict_key(test.method, key, fmf_key, test_dict)
    if CONFIG_POSTPROCESSING_TEST in config:
        __post_processing(
            test_dict, config[CONFIG_POSTPROCESSING_TEST], cls, test, filename
            )
    return test_dict


def define_undefined(input_dict, keys, config, relative_test_path, cls, test):
    for item in keys:
        item_id = f"/{item}"
        default_key(input_dict, item_id, empty_obj={})
        input_dict = input_dict[item_id]
    test_data_dict(
        test_dict=input_dict,
        config=config,
        filename=relative_test_path,
        cls=cls,
        test=test,
        )


def collect(opts):
    plugin_col = ItemsCollector()
    pytest.main(
        ["--collect-only", "-pno:terminal", "-m", ""] + opts,
        plugins=[plugin_col])
    for item in plugin_col.items:
        func = item.function
        for marker in item.iter_markers():
            key = marker.name
            args = marker.args
            kwargs = marker.kwargs

            if key == "skip":
                TMT.enabled(False)(func)
            elif key == "skipif":
                # add skipif as tag as well (possible to use adjust, but
                # conditions are python code)
                arg_string = "SKIP "
                if args:
                    arg_string += " ".join(map(str, args))
                if "reason" in kwargs:
                    arg_string += " " + kwargs["reason"]
                TMT.tag(arg_string)(func)
            elif key == "parametrize":
                # do nothing, parameters are already part of test name
                pass
            else:
                # generic mark store as tag
                TMT.tag(key)(func)
    return plugin_col.items


class Pytest(Plugin):
    extensions = [".py"]
    file_patters = ["test.*"]

    @staticmethod
    def update_data(store_dict, func, config):
        keys = []
        filename = os.path.basename(func.fspath)
        if func.cls:
            cls = _TestCls(func.cls, filename)
            keys.append(cls.name)
        else:
            cls = _TestCls(None, filename)
        test = _Test(func)
        # normalise test name to pytest identifier
        test.name = re.search(
            f".*({os.path.basename(func.function.__name__)}.*)", func.name
            ).group(1)
        # TODO: removed str_normalise(...) will see what happen
        keys.append(test.name)
        define_undefined(store_dict, keys, config, filename, cls, test)
        return store_dict

    def read(self, file_name):
        def call_collect(queue, file_name):
            """
            have to call in separate process, to avoid problems with pytest multiple collectitons
            when called twice on same data test list is empty because already imported
            """
            out = dict()

            for item in collect([file_name]):
                self.update_data(store_dict=out, func=item,
                                 config=PYTEST_DEFAULT_CONF)
                log.info("Processing Item: {}".format(item.function))
            queue.put(out)

        process_queue = Queue()
        process = Process(target=call_collect,
                          args=(process_queue, file_name,))
        process.start()
        out = process_queue.get()
        process.join()
        if out:
            return out
        return None

    @staticmethod
    def import_test_module(filename):
        loader = importlib.machinery.SourceFileLoader(
            os.path.basename(filename), filename)
        module = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(loader.name, loader)
            )
        loader.exec_module(module)
        return module

    def write(
            self, filename, hierarchy, data, append_dict, modified_dict,
            deleted_items):
        module = self.import_test_module(filename)
        where = module
        for item in hierarchy:
            where = getattr(where, item.lstrip("/"))
        lines, start_line = inspect.getsourcelines(where)
        spaces = re.match(r"(^\s*)", lines[0]).groups()[0]
        # try to find if already defined
        with open(filename, "r") as f:
            contents = f.readlines()
        for k in deleted_items:
            for num, line in enumerate(lines):
                if re.match(r"{}.*@TMT\.{}".format(spaces, k), line):
                    contents.pop(start_line + num - 1)
        for k, v in modified_dict.items():
            for num, line in enumerate(lines):
                if re.match(r"{}.*@TMT\.{}".format(spaces, k), line):
                    contents.pop(start_line + num - 1)
            append_dict[k] = v
        for k, v in append_dict.items():
            contents.insert(start_line,
                            """{}@TMT.{}({})\n""".format(spaces,
                                                         k,
                                                         repr(v)[1:-1] if isinstance(v,
                                                                                     list) else repr(v)))
        with open(filename, "w") as f:
            f.writelines(contents)
