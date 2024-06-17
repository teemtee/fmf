import os

import fmf.cli
import fmf.utils as utils

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../../examples/wget"


class TestSmoke:
    """ Smoke Test """

    def test_smoke(self):
        """ Smoke test """
        with utils.cd(WGET):
            fmf.cli.main("fmf ls")

    def test_output(self):
        """ There is some output """
        with utils.cd(WGET):
            output = fmf.cli.main("fmf ls")
            assert "download" in output
