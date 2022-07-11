import os
import sys
import tempfile

import pytest

import fmf.cli
import fmf.utils as utils

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../../examples/wget"


class TestCommandLine:
    """ Command Line """

    def test_smoke(self):
        """ Smoke test """
        fmf.cli.main("fmf show", WGET)
        fmf.cli.main("fmf show --debug", WGET)
        fmf.cli.main("fmf show --verbose", WGET)
        fmf.cli.main("fmf --version")

    def test_missing_root(self):
        """ Missing root """
        with pytest.raises(utils.FileError):
            fmf.cli.main("fmf show", "/")

    def test_invalid_path(self):
        """ Missing root """
        with pytest.raises(utils.FileError):
            fmf.cli.main("fmf show --path /some-non-existent-path")

    def test_wrong_command(self):
        """ Wrong command """
        with pytest.raises(utils.GeneralError):
            fmf.cli.main("fmf wrongcommand")

    def test_output(self):
        """ There is some output """
        output = fmf.cli.main("fmf show", WGET)
        assert "download" in output

    def test_recursion(self):
        """ Recursion """
        output = fmf.cli.main("fmf show --name recursion/deep", WGET)
        assert "1000" in output

    def test_inheritance(self):
        """ Inheritance """
        output = fmf.cli.main("fmf show --name protocols/https", WGET)
        assert "psplicha" in output

    def test_sys_argv(self):
        """ Parsing sys.argv """
        backup = sys.argv
        sys.argv = ['fmf', 'show', '--path', WGET, '--name', 'recursion/deep']
        output = fmf.cli.main()
        assert "1000" in output
        sys.argv = backup

    def test_missing_attribute(self):
        """ Missing attribute """
        output = fmf.cli.main("fmf show --filter x:y", WGET)
        assert "wget" not in output

    def test_filtering_by_source(self):
        """ By source """
        output = fmf.cli.main("fmf show --source protocols/ftp/main.fmf", WGET)
        assert "/protocols/ftp" in output

    def test_filtering(self):
        """ Filtering """
        output = fmf.cli.main(
            "fmf show --filter tags:Tier1 --filter tags:TierSecurity", WGET)
        assert "/download/test" in output
        output = fmf.cli.main(
            "fmf show --filter tags:Tier1 --filter tags:Wrong", WGET)
        assert "wget" not in output
        output = fmf.cli.main(
            " fmf show --filter 'tags: Tier[A-Z].*'", WGET)
        assert "/download/test" in output
        assert "/recursion" not in output

    def test_key_content(self):
        """ Key content """
        output = fmf.cli.main("fmf show --key depth")
        assert "/recursion/deep" in output
        assert "/download/test" not in output

    def test_format_basic(self):
        """ Custom format (basic) """
        output = fmf.cli.main(WGET + "fmf show --format foo")
        assert "wget" not in output
        assert "foo" in output

    def test_format_key(self):
        """ Custom format (find by key, check the name) """
        output = fmf.cli.main(
            "fmf show --key depth --format {0} --value name", WGET)
        assert "/recursion/deep" in output

    def test_format_functions(self):
        """ Custom format (using python functions) """
        output = fmf.cli.main(
            "fmf show --key depth --format {0} --value os.path.basename(name)",
            WGET)
        assert "deep" in output
        assert "/recursion" not in output

    @pytest.mark.skipif(os.geteuid() == 0, reason="Running as root")
    def test_init(self):
        """ Initialize metadata tree """
        path = tempfile.mkdtemp()
        fmf.cli.main("fmf init", path)
        fmf.cli.main("fmf show", path)
        # Already exists
        with pytest.raises(utils.FileError):
            fmf.cli.main("fmf init", path)
        version_path = os.path.join(path, ".fmf", "version")
        with open(version_path) as version:
            assert "1" in version.read()
        # Permission denied
        secret_path = os.path.join(path, 'denied')
        os.makedirs(secret_path)
        os.chmod(secret_path, 0o666)
        with pytest.raises(utils.FileError):
            fmf.cli.main('fmf init --path {}'.format(secret_path), path)
        os.chmod(secret_path, 0o777)
        # Invalid version
        with open(version_path, "w") as version:
            version.write("bad")
        with pytest.raises(utils.FormatError):
            fmf.cli.main("fmf ls", path)
        # Missing version
        os.remove(version_path)
        with pytest.raises(utils.FormatError):
            fmf.cli.main("fmf ls", path)

    def test_conditions(self):
        """ Advanced filters via conditions """
        path = PATH + "/../../examples/conditions"
        # Compare numbers
        output = fmf.cli.main("fmf ls --condition 'float(release) >= 7'", path)
        assert len(output.splitlines()) == 3
        output = fmf.cli.main("fmf ls --condition 'float(release) > 7'", path)
        assert len(output.splitlines()) == 2
        # Access a dictionary key
        output = fmf.cli.main(
            "fmf ls --condition \"execute['how'] == 'dependency'\"", path)
        assert output.strip() == "/top/rhel7"
        # Wrong key means unsatisfied condition
        output = fmf.cli.main(
            "fmf ls --condition \"execute['wrong key'] == 0\"", path)
        assert output == ''

    def test_clean(self, tmpdir, monkeypatch):
        """ Cache cleanup """
        # Do not manipulate with real, user's cache
        monkeypatch.setattr('fmf.utils._CACHE_DIRECTORY', str(tmpdir))
        testing_file = tmpdir.join("something")
        testing_file.write("content")
        fmf.cli.main("fmf clean")
        assert not os.path.isfile(str(testing_file))
