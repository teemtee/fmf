import os

import pytest
from click.testing import CliRunner

import fmf.cli
import fmf.utils as utils

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../../examples/wget"


class TestCommandLine:
    """ Command Line """

    def test_smoke(self):
        """ Smoke test """
        runner = CliRunner()
        with utils.cd(WGET):
            runner.invoke(fmf.cli.main, "show")
            runner.invoke(fmf.cli.main, "show --debug")
            runner.invoke(fmf.cli.main, "show --verbose")
        runner.invoke(fmf.cli.main, "--version")

    def test_missing_root(self):
        """ Missing root """
        with utils.cd("/"):
            with pytest.raises(utils.RootError):
                CliRunner().invoke(fmf.cli.main, "show", catch_exceptions=False)

    def test_invalid_path(self):
        """ Missing root """
        with pytest.raises(utils.FileError):
            CliRunner().invoke(
                fmf.cli.main,
                "show --path /some-non-existent-path",
                catch_exceptions=False)

    def test_wrong_command(self):
        """ Wrong command """
        result = CliRunner().invoke(fmf.cli.main, "wrongcommand", catch_exceptions=False)
        assert result.exit_code == 2
        assert "No such command 'wrongcommand'" in result.stdout

    def test_output(self):
        """ There is some output """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show")
        assert "download" in result.output

    def test_recursion(self):
        """ Recursion """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show --name recursion/deep")
        assert "1000" in result.output

    def test_inheritance(self):
        """ Inheritance """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show --name protocols/https")
        assert "psplicha" in result.output

    def test_missing_attribute(self):
        """ Missing attribute """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show --filter x:y")
        assert "wget" not in result.output

    def test_filtering_by_source(self):
        """ By source """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show --source protocols/ftp/main.fmf")
        assert "/protocols/ftp" in result.output

    def test_filtering(self):
        """ Filtering """
        runner = CliRunner()
        with utils.cd(WGET):
            result = runner.invoke(
                fmf.cli.main,
                "show --filter tags:Tier1 --filter tags:TierSecurity")
            assert "/download/test" in result.output
            result = runner.invoke(
                fmf.cli.main,
                "show --filter tags:Tier1 --filter tags:Wrong")
            assert "wget" not in result.output
            result = runner.invoke(
                fmf.cli.main,
                "show --filter 'tags: Tier[A-Z].*'")
            assert "/download/test" in result.output
            assert "/recursion" not in result.output

    def test_key_content(self):
        """ Key content """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show --key depth")
        assert "/recursion/deep" in result.output
        assert "/download/test" not in result.output

    def test_format_basic(self):
        """ Custom format (basic) """
        with utils.cd(WGET):
            result = CliRunner().invoke(fmf.cli.main, "show --format foo")
        assert "wget" not in result.output
        assert "foo" in result.output

    def test_format_key(self):
        """ Custom format (find by key, check the name) """
        with utils.cd(WGET):
            result = CliRunner().invoke(
                fmf.cli.main,
                "show --key depth --format {0} --value name")
        assert "/recursion/deep" in result.output

    def test_format_functions(self):
        """ Custom format (using python functions) """
        with utils.cd(WGET):
            result = CliRunner().invoke(
                fmf.cli.main,
                "show --key depth --format {0} --value os.path.basename(name)")
        assert "deep" in result.output
        assert "/recursion" not in result.output

    @pytest.mark.skipif(os.geteuid() == 0, reason="Running as root")
    def test_init(self, tmp_path):
        """ Initialize metadata tree """
        runner = CliRunner()
        with utils.cd(tmp_path):
            runner.invoke(fmf.cli.main, "init")
            runner.invoke(fmf.cli.main, "show")
            # Already exists
            with pytest.raises(utils.FileError):
                runner.invoke(fmf.cli.main, "init", catch_exceptions=False)
            version_path = tmp_path / ".fmf" / "version"
            with version_path.open() as version:
                assert "1" in version.read()
            # Permission denied
            secret_path = tmp_path / "denied"
            secret_path.mkdir(0o666)
            with pytest.raises(utils.FileError):
                runner.invoke(
                    fmf.cli.main,
                    "init --path {}".format(secret_path),
                    catch_exceptions=False)
            secret_path.chmod(0o777)
            # Invalid version
            with version_path.open("w") as version:
                version.write("bad")
            with pytest.raises(utils.FormatError):
                runner.invoke(fmf.cli.main, "ls", catch_exceptions=False)
            # Missing version
            version_path.unlink()
            with pytest.raises(utils.FormatError):
                runner.invoke(fmf.cli.main, "ls", catch_exceptions=False)

    def test_conditions(self):
        """ Advanced filters via conditions """
        path = PATH + "/../../examples/conditions"
        # Compare numbers
        runner = CliRunner()
        with utils.cd(path):
            # Compare numbers
            result = runner.invoke(fmf.cli.main, "ls --condition 'float(release) >= 7'")
            assert len(result.output.splitlines()) == 3
            result = runner.invoke(fmf.cli.main, "ls --condition 'float(release) > 7'")
            assert len(result.output.splitlines()) == 2
            # Access a dictionary key
            result = runner.invoke(
                fmf.cli.main,
                "ls --condition \"execute['how'] == 'dependency'\"")
            assert result.output.strip() == "/top/rhel7"
            # Wrong key means unsatisfied condition
            result = runner.invoke(
                fmf.cli.main,
                "ls --condition \"execute['wrong key'] == 0\"")
            assert result.output == ''

    def test_clean(self, tmpdir, monkeypatch):
        """ Cache cleanup """
        # Do not manipulate with real, user's cache
        monkeypatch.setattr('fmf.utils._CACHE_DIRECTORY', str(tmpdir))
        testing_file = tmpdir.join("something")
        testing_file.write("content")
        CliRunner().invoke(fmf.cli.main, "clean")
        assert not os.path.isfile(str(testing_file))
