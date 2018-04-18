# coding: utf-8

from __future__ import unicode_literals, absolute_import

import os
import sys
import fmf.cli

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../examples/wget"


class TestCommandLine(object):
    """ Command Line """

    def test_smoke(self):
        """ Smoke test """
        fmf.cli.main("")
        fmf.cli.main(WGET)
        fmf.cli.main(WGET + " --debug")
        fmf.cli.main(WGET + " --verbose")

    def test_output(self):
        """ There is some output """
        output = fmf.cli.main(WGET)
        assert "wget" in output

    def test_recursion(self):
        """ Recursion """
        output = fmf.cli.main(WGET + " --name recursion/deep")
        assert "1000" in output

    def test_inheritance(self):
        """ Inheritance """
        output = fmf.cli.main(WGET + " --name protocols/https")
        assert "psplicha" in output

    def test_sys_argv(self):
        """ Parsing sys.argv """
        backup = sys.argv
        sys.argv = ['fmf', WGET, '--name', 'recursion/deep']
        output = fmf.cli.main()
        assert "1000" in output
        sys.argv = backup

    def test_missing_attribute(self):
        """ Missing attribute """
        output = fmf.cli.main(WGET + " --filter x:y")
        assert "wget" not in output

    def test_filtering(self):
        """ Filtering """
        output = fmf.cli.main(WGET +
            " --filter tags:Tier1 --filter tags:TierSecurity")
        assert "wget/download/test" in output
        output = fmf.cli.main(WGET +
            " --filter tags:Tier1 --filter tags:Wrong")
        assert "wget" not in output

    def test_key_content(self):
        """ Key content """
        output = fmf.cli.main(WGET + " --key depth")
        assert "wget/recursion/deep" in output
        assert "wget/download/test" not in output

    def test_format_basic(self):
        """ Custom format (basic) """
        output = fmf.cli.main(WGET + " --format foo")
        assert "wget" not in output
        assert "foo" in output

    def test_format_key(self):
        """ Custom format (find by key, check the name) """
        output = fmf.cli.main(
            [WGET, "--key", "depth", "--format", "{0}", "--value", "name"])
        assert "wget/recursion/deep" in output

    def test_format_functions(self):
        """ Custom format (using python functions) """
        output = fmf.cli.main(
            [WGET, "--key", "depth", "--format", "{0}",
            "--value", "os.path.basename(name)"])
        assert "deep" in output
        assert "wget/recursion" not in output
