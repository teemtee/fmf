import os
import sys

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
        with utils.cd(WGET):
            fmf.cli.main("fmf show")
            fmf.cli.main("fmf show --debug")
            fmf.cli.main("fmf show --verbose")
        fmf.cli.main("fmf --version")

    def test_missing_root(self):
        """ Missing root """
        with utils.cd("/"):
            with pytest.raises(utils.FileError):
                fmf.cli.main("fmf show")

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
        with utils.cd(WGET):
            output = fmf.cli.main("fmf show")
        assert "download" in output

    def test_recursion(self):
        """ Recursion """
        with utils.cd(WGET):
            output = fmf.cli.main("fmf show --name recursion/deep")
        assert "1000" in output

    def test_inheritance(self):
        """ Inheritance """
        with utils.cd(WGET):
            output = fmf.cli.main("fmf show --name protocols/https")
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
        with utils.cd(WGET):
            output = fmf.cli.main("fmf show --filter x:y")
        assert "wget" not in output

    def test_filtering_by_source(self):
        """ By source """
        with utils.cd(WGET):
            output = fmf.cli.main("fmf show --source protocols/ftp/main.fmf")
        assert "/protocols/ftp" in output

    def test_filtering(self):
        """ Filtering """
        with utils.cd(WGET):
            output = fmf.cli.main(
                "fmf show --filter tags:Tier1 --filter tags:TierSecurity")
            assert "/download/test" in output
            output = fmf.cli.main(
                "fmf show --filter tags:Tier1 --filter tags:Wrong")
            assert "wget" not in output
            output = fmf.cli.main(
                " fmf show --filter 'tags: Tier[A-Z].*'")
            assert "/download/test" in output
            assert "/recursion" not in output

    def test_key_content(self):
        """ Key content """
        with utils.cd(WGET):
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
        with utils.cd(WGET):
            output = fmf.cli.main(
                "fmf show --key depth --format {0} --value name")
        assert "/recursion/deep" in output

    def test_format_functions(self):
        """ Custom format (using python functions) """
        with utils.cd(WGET):
            output = fmf.cli.main(
                "fmf show --key depth --format {0} --value os.path.basename(name)")
        assert "deep" in output
        assert "/recursion" not in output

    @pytest.mark.skipif(os.geteuid() == 0, reason="Running as root")
    def test_init(self, tmp_path):
        """ Initialize metadata tree """
        with utils.cd(tmp_path):
            fmf.cli.main("fmf init")
            fmf.cli.main("fmf show")
            # Already exists
            with pytest.raises(utils.FileError):
                fmf.cli.main("fmf init")
            version_path = tmp_path / ".fmf" / "version"
            with version_path.open() as version:
                assert "1" in version.read()
            # Permission denied
            secret_path = tmp_path / "denied"
            secret_path.mkdir(0o666)
            with pytest.raises(utils.FileError):
                fmf.cli.main('fmf init --path {}'.format(secret_path))
            secret_path.chmod(0o777)
            # Invalid version
            with version_path.open("w") as version:
                version.write("bad")
            with pytest.raises(utils.FormatError):
                fmf.cli.main("fmf ls")
            # Missing version
            version_path.unlink()
            with pytest.raises(utils.FormatError):
                fmf.cli.main("fmf ls")

    def test_conditions(self):
        """ Advanced filters via conditions """
        path = PATH + "/../../examples/conditions"
        # Compare numbers
        with utils.cd(path):
            output = fmf.cli.main("fmf ls --condition 'float(release) >= 7'")
            assert len(output.splitlines()) == 3
            output = fmf.cli.main("fmf ls --condition 'float(release) > 7'")
            assert len(output.splitlines()) == 2
            # Access a dictionary key
            output = fmf.cli.main(
                "fmf ls --condition \"execute['how'] == 'dependency'\"")
            assert output.strip() == "/top/rhel7"
            # Wrong key means unsatisfied condition
            output = fmf.cli.main(
                "fmf ls --condition \"execute['wrong key'] == 0\"")
            assert output == ''

    def test_clean(self, tmpdir, monkeypatch):
        """ Cache cleanup """
        # Do not manipulate with real, user's cache
        monkeypatch.setattr('fmf.utils._CACHE_DIRECTORY', str(tmpdir))
        testing_file = tmpdir.join("something")
        testing_file.write("content")
        fmf.cli.main("fmf clean")
        assert not os.path.isfile(str(testing_file))
