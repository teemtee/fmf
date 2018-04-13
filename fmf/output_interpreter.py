# coding: utf-8

"""
Command line interface for Flexible Metadata Format

This module takes care of processing command line options
and providing requested output.
"""

import os
import utils
import base
import re
from cli import Options


# set  of functions to use for evaluation
from os.path import basename, dirname, curdir
from os import getcwd


class ExtendOptions(Options):
    def __init__(self):
        super(ExtendOptions, self).__init__()
        group = self.parser.add_argument_group("Output Formatter")
        group.add_argument(
            "--value", dest="values", action="append", default=[],
            help="""value to formatting string, position dependent, symbol {} in string,
(possible functions: basename, dirname, curdir, getcwd)"
usages --value name    , --value 'dirname(data["path"])'""")
        group.add_argument(
            "--formatstring", dest="formatstring", action="store", required=True,
            help="Basic formatting string, use python syntax like {} or {1} to replacements")


def prune(tree, whole, keys, names, filters):
    #TODO: if accepted, replace also this in cli.py or to utils and then use it also in cli
    output = []
    for node in tree.climb(whole):
        # Select only nodes with key content
        if not all([key in node.data for key in keys]):
            continue
        # Select nodes with name matching regular expression
        if names and not any(
                [re.search(name, node.name) for name in names]):
            continue
        # Apply advanced filters if given
        try:
            if not all([utils.filter(filter, node.data)
                        for filter in filters]):
                continue
        # Handle missing attribute as if filter failed
        except utils.FilterError:
            continue
        output.append(node)
    return output


def formatstring(nodes, formatstring, values):
    output = []
    for node in nodes:
        evaluated = []
        # used internally to avoid using long syntax like name -> node.name data[key] -> node.data[key]
        name = node.name
        data = node.data
        for value in values:
            evaluated.append(eval(value))
        output.append(formatstring.format(*evaluated))
    return output


def inspect_dirs(directories=None):
    # TODO: replace this also in cli.py, it is very common case
    if not directories:
        directories = ["."]
    output = list()
    for one_dir in directories:
        output.append(base.Tree(one_dir))
    return output


def main(cmdline=None):
    """ Parse options, gather metadata, print requested data """
    output = []
    # Parse command line arguments
    options, arguments = ExtendOptions().parse(cmdline)
    tree_object_list = inspect_dirs(directories=arguments)
    for tree_object in tree_object_list:
        filtered = prune(tree_object,
                          whole=options.whole,
                          keys=options.keys,
                          names=options.names,
                          filters=options.filters)
        formatted = formatstring(filtered, options.formatstring, options.values)
        output += formatted
    print(os.linesep.join(output))
    return output
