# coding: utf-8

from __future__ import unicode_literals, absolute_import

import os
import pytest
import fmf.base
import fmf.cli

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Prepare path and config examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLE = PATH + "/../examples/wget"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Tests
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def test_smoke():
    """ Smoke test """
    fmf.cli.main(EXAMPLE)

def test_output():
    """ There is some output """
    output = fmf.cli.main(EXAMPLE)
    assert "wget" in output

def test_recursion():
    """ Recursion """
    output = fmf.cli.main(EXAMPLE + " --name recursion/deep")
    assert "1000" in output

def test_inheritance():
    """ Inheritance """
    output = fmf.cli.main(EXAMPLE + " --name protocols/https")
    assert "psplicha" in output
