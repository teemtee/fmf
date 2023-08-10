import os

from click.testing import CliRunner

import fmf.utils as utils
from fmf.cli import main

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../../examples/wget"


class TestSmoke:
    """ Smoke Test """

    def test_smoke(self):
        """ Smoke test """
        with utils.cd(WGET):
            CliRunner().invoke(main, ['ls'])

    def test_output(self):
        """ There is some output """
        with utils.cd(WGET):
            result = CliRunner().invoke(main, ['ls'])
            assert "download" in result.output
