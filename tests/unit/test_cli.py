import os
from pathlib import Path

import pytest
from click.testing import CliRunner

import fmf.utils as utils
from fmf.cli import cd, main

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
WGET = PATH + "/../../examples/wget"
CONDITIONS = PATH + "/../../examples/conditions"


class TestCommandLine:
    """ Command Line """

    def test_smoke(self):
        """ Smoke test """
        runner = CliRunner()
        runner.invoke(main, args=['--version'])
        with cd(WGET):
            runner.invoke(main, args=['show'])
            runner.invoke(main, args=['show', '--debug'])
            runner.invoke(main, args=['show', '--verbose'])

    def test_missing_root(self):
        """ Missing root """
        with cd('/'):
            result = CliRunner().invoke(main, args=['show'])
            assert isinstance(result.exception, utils.FileError)

    def test_invalid_path(self):
        """ Missing root """
        result = CliRunner().invoke(main, args=['show', '--path', '/some-non-existent-path'])
        assert isinstance(result.exception, utils.FileError)

    def test_wrong_command(self):
        """ Wrong command """
        result = CliRunner().invoke(main, args=['wrongcommand'])
        assert result.exit_code == 2
        assert "Error: No such command" in result.output

    def test_output(self):
        """ There is some output """
        with cd(WGET):
            result = CliRunner().invoke(main, args=['show'])
        assert "download" in result.output

    def test_recursion(self):
        """ Recursion """
        with cd(WGET):
            result = CliRunner().invoke(main, args=['show', '--name', 'recursion/deep'])
        assert "1000" in result.output

    def test_inheritance(self):
        """ Inheritance """
        with cd(WGET):
            result = CliRunner().invoke(main, args=['show', '--name', 'protocols/https'])
        assert "psplicha" in result.output

    # def test_sys_argv(self):
    #     """ Parsing sys.argv """
    #     backup = sys.argv
    #     sys.argv = ['fmf', 'show', '--path', WGET, '--name', 'recursion/deep']
    #     output = main()
    #     assert "1000" in output
    #     sys.argv = backup

    def test_missing_attribute(self):
        """ Missing attribute """
        with cd(WGET):
            result = CliRunner().invoke(main, args=['show', '--name', '--filter', 'x:y'])
        assert "wget" not in result.output

    def test_filtering_by_source(self):
        """ By source """
        with cd(WGET):
            result = CliRunner().invoke(main, args=['show', '--source', 'protocols/ftp/main.fmf'])
        assert "/protocols/ftp" in result.output

    def test_filtering(self):
        """ Filtering """
        runner = CliRunner()
        with cd(WGET):
            result = runner.invoke(
                main,
                args=[
                    'show',
                    '--filter',
                    'tags:Tier1',
                    '--filter',
                    'tags:TierSecurity'])
            assert "/download/test" in result.output
            result = runner.invoke(
                main,
                args=[
                    'show',
                    '--filter',
                    'tags:Tier1',
                    '--filter',
                    'tags:Wrong'])
            assert "wget" not in result.output
            result = runner.invoke(
                main,
                args=[
                    'show',
                    '--filter',
                    'tags: Tier[A-Z].*',
                    '--filter',
                    'tags:TierSecurity'])
            assert "/download/test" in result.output
            assert "/recursion" not in result.output

    def test_key_content(self):
        """ Key content """
        with cd(WGET):
            result = CliRunner().invoke(main, args=['show', '--key', 'depth'])
        assert "/recursion/deep" in result.output
        assert "/download/test" not in result.output

    def test_format_basic(self):
        """ Custom format (basic) """
        result = CliRunner().invoke(main, args=['show', '--format', 'foo'])
        assert "wget" not in result.output
        assert "foo" in result.output

    def test_format_key(self):
        """ Custom format (find by key, check the name) """
        with cd(WGET):
            result = CliRunner().invoke(
                main,
                args=[
                    'show',
                    '--key',
                    'depth',
                    '--format',
                    '{0}',
                    '--value',
                    'name'])
        assert "/recursion/deep" in result.output

    def test_format_functions(self):
        """ Custom format (using python functions) """
        with cd(WGET):
            result = CliRunner().invoke(
                main,
                args=[
                    'show',
                    '--key',
                    'depth',
                    '--format',
                    '{0}',
                    '--value',
                    'os.path.basename(name)'])
        assert "deep" in result.output
        assert "/recursion" not in result.output

    @pytest.mark.skipif(os.geteuid() == 0, reason="Running as root")
    def test_init(self, tmp_path):
        """ Initialize metadata tree """
        runner = CliRunner()
        with cd(tmp_path):
            runner.invoke(main, args=['init'])
            runner.invoke(main, args=['show'])
            # Already exists
            result = runner.invoke(main, args=['init'])
            assert isinstance(result.exception, utils.FileError)
            version_path = Path('.', ".fmf", "version")
            with open(version_path) as version:
                assert "1" in version.read()
            # Permission denied
            secret_path = Path('.', 'denied')
            secret_path.mkdir(0o666)
            result = runner.invoke(
                main, args=['init', '--path', str(secret_path.relative_to('.'))])
            assert isinstance(result.exception, utils.FileError)
            secret_path.chmod(0o777)
            # Invalid version
            with open(version_path, "w") as version:
                version.write("bad")
            result = runner.invoke(main, args=['ls'])
            assert isinstance(result.exception, utils.FormatError)
            # Missing version
            version_path.unlink()
            result = runner.invoke(main, args=['ls'])
            assert isinstance(result.exception, utils.FormatError)

    def test_conditions(self):
        """ Advanced filters via conditions """
        runner = CliRunner()
        with cd(CONDITIONS):
            # Compare numbers
            result = runner.invoke(main, args=['ls', '--condition', 'float(release) >= 7'])
            assert len(result.output.splitlines()) == 3
            result = runner.invoke(main, args=['ls', '--condition', 'float(release) > 7'])
            assert len(result.output.splitlines()) == 2
            # Access a dictionary key
            result = runner.invoke(
                main,
                args=[
                    'ls',
                    '--condition',
                    'execute["how"] == "dependency"'])
            assert result.output.strip() == "/top/rhel7"
            result = runner.invoke(main, args=['ls', '--condition', 'execute["wrong key"] == "0"'])
            # Wrong key means unsatisfied condition
            assert result.output == ''

    def test_clean(self, tmpdir, monkeypatch):
        """ Cache cleanup """
        # Do not manipulate with real, user's cache
        monkeypatch.setattr('fmf.utils._CACHE_DIRECTORY', str(tmpdir))
        testing_file = tmpdir.join("something")
        testing_file.write("content")
        CliRunner().invoke(main, ['clean'])
        assert not os.path.isfile(str(testing_file))
