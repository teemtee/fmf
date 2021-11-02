import os

import fmf.cli

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../../examples/wget"


class TestSmoke:
    """ Smoke Test """

    def test_smoke(self):
        """ Smoke test """
        fmf.cli.main("fmf ls", WGET)

    def test_output(self):
        """ There is some output """
        output = fmf.cli.main("fmf ls", WGET)
        assert "download" in output
