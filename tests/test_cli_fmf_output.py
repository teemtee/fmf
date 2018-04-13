# coding: utf-8

from __future__ import unicode_literals, absolute_import

import os
import fmf.output_interpreter as cli

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../examples/wget"


class TestCommandLine(object):
    """ Command Line """

    def test_noargs(self):
        """ Smoke test """
        try:
            cli.main("")
        except SystemExit:
            pass
        else:
            raise BaseException("required at least format string argument, without this it does not make sense")

    def test_smoke_generic_no_value(self):
        assert "ahoj" in cli.main(WGET + " --key test --formatstring ahoj")

    def test_smoke_generic(self):
        assert "wget/download/test" in cli.main(WGET + " --key test --formatstring {} --value name")

class TestAPI(object):
    """ Test API """
    def test_smoke(self):
        tree_object_list = cli.inspect_dirs(directories=[WGET])
        for tree_object in tree_object_list:
            filtered = cli.prune(tree_object, keys=["test"], whole=False, names=[], filters=[])
            formatted = cli.formatstring(filtered, "{}", ["name"])
            assert "wget/download/test" in formatted

    def test_smoke_default_dir(self):
        tree_object_list = cli.inspect_dirs()
        tree_object = tree_object_list[0]
        assert tree_object.name

        filtered = cli.prune(tree_object, keys=["test"], whole=False, names=[], filters=[])
        assert filtered

        filtered = cli.prune(tree_object, keys=[], whole=False, names=["test"], filters=[])
        assert filtered

        filtered = cli.prune(tree_object, keys=[], whole=False, names=[], filters=["tag: test"])
        assert not filtered

        filtered = cli.prune(tree_object, keys=[], whole=False, names=[], filters=["test"])
        assert not filtered




