import os
import queue
import re
import shutil
import threading
import time

import pytest

import fmf
import fmf.utils as utils
from fmf.utils import filter, listed, run

GIT_REPO = 'https://github.com/teemtee/fmf'
GIT_REPO_MASTER = 'https://github.com/teemtee/old'


class TestFilter:
    """ Function filter() """

    def setup_method(self, method):
        self.data = {
            "tag": ["Tier1", "TIPpass", "mod:S"],
            "category": "Sanity",
            }

    def test_invalid(self):
        """ Invalid filter format """
        with pytest.raises(utils.FilterError):
            filter("status:proposed", self.data)
        with pytest.raises(utils.FilterError):
            filter("x: 1", None)

    def test_empty_filter(self):
        """ Empty filter should return True """
        assert filter(None, self.data) is True
        assert filter("", self.data) is True

    def test_name_missing(self):
        """ Node name has to be provided when searching for names """
        with pytest.raises(utils.FilterError):
            filter("/tests/core", self.data)
        with pytest.raises(utils.FilterError):
            filter("/tests/one | /tests/two", self.data)

    def test_name_provided(self):
        """ Searching by node names """
        # Basic
        assert filter("/tests/one", self.data, name="/tests/one") is True
        assert filter("/tests/two", self.data, name="/tests/one") is False

        # Combined
        assert filter("/tests/one | /tests/two", self.data, name="/tests/one") is True
        assert filter("/tests/one | tag: bad", self.data, name="/tests/one") is True
        assert filter("/tests/one & tag: bad", self.data, name="/tests/one") is False
        assert filter("/tests/wrong | tag: Tier1", self.data, name="/tests/one") is True
        assert filter("/tests/wrong & tag: Tier1", self.data, name="/tests/one") is False

        # Regular expressions
        assert filter("/.*/one", self.data, name="/tests/one") is False
        assert filter("/.*/one", self.data, name="/tests/one", regexp=True) is True

    def test_basic(self):
        """ Basic stuff and negation """
        assert filter("tag: Tier1", self.data) is True
        assert filter("tag: mod:S", self.data) is True
        assert filter("tag: -Tier2", self.data) is True
        assert filter("tag: -mod:S2", self.data) is True
        assert filter("category: Sanity", self.data) is True
        assert filter("category: -Regression", self.data) is True
        assert filter("tag: Tier2", self.data) is False
        assert filter("tag: -Tier1", self.data) is False
        assert filter("category: Regression", self.data) is False
        assert filter("category: -Sanity", self.data) is False

    def test_operators(self):
        """ Operators """
        assert filter("tag: Tier1 | tag: Tier2", self.data) is True
        assert filter("tag: Tier1 | tag: mod:S", self.data) is True
        assert filter("tag: mod:X | tag: mod:S", self.data) is True
        assert filter("tag: -Tier1 | tag: -Tier2", self.data) is True
        assert filter("tag: Tier1 | tag: TIPpass", self.data) is True
        assert filter("tag: Tier1 | category: Regression", self.data) is True
        assert filter("tag: Tier1 & tag: TIPpass", self.data) is True
        assert filter("tag: Tier1 & category: Sanity", self.data) is True
        assert filter("tag: Tier2 | tag: Tier3", self.data) is False
        assert filter("tag: Tier1 & tag: Tier2", self.data) is False
        assert filter("tag: Tier2 & tag: Tier3", self.data) is False
        assert filter("tag: Tier1 & category: Regression", self.data) is False
        assert filter("tag: Tier2 | category: Regression", self.data) is False

    def test_sugar(self):
        """ Syntactic sugar """
        assert filter("tag: Tier1, Tier2", self.data) is True
        assert filter("tag: Tier2, mod:S", self.data) is True
        assert filter("tag: Tier1, TIPpass", self.data) is True
        assert filter("tag: -Tier2", self.data) is True
        assert filter("tag: -Tier1, -Tier2", self.data) is True
        assert filter("tag: -Tier1, -Tier2", self.data) is True
        assert filter("tag: Tier2, Tier3", self.data) is False

    def test_regexp(self):
        """ Regular expressions """
        assert filter("tag: Tier.*", self.data, regexp=True) is True
        assert filter("tag: Tier[123]", self.data, regexp=True) is True
        assert filter("tag: mod:[XS]", self.data, regexp=True) is True
        assert filter("tag: NoTier.*", self.data, regexp=True) is False
        assert filter("tag: -Tier.*", self.data, regexp=True) is False

    def test_case(self):
        """ Case insensitive """
        assert filter("tag: tier1", self.data, sensitive=False) is True
        assert filter("tag: tippass", self.data, sensitive=False) is True

    def test_unicode(self):
        """ Unicode support """
        assert filter("tag: -ťip", self.data) is True
        assert filter("tag: ťip", self.data) is False
        assert filter("tag: ťip", {"tag": ["ťip"]}) is True
        assert filter("tag: -ťop", {"tag": ["ťip"]}) is True

    def test_escape_or(self):
        """ Escaping the | operator """

        # Escaped
        assert filter(r"category: (Sanity\|Security)", self.data, regexp=True) is True
        assert filter(r"tag: Tier(1\|2)", self.data, regexp=True) is True

        # Unescaped
        with pytest.raises(re.error):
            assert filter(r"category: (Sanity|Security)", self.data, regexp=True) is True
        with pytest.raises(re.error):
            assert filter(r"tag: Tier(1|2)", self.data, regexp=True) is True

    def test_escape_and(self):
        """ Escaping the & operator """
        self.data["text"] = "Q&A"

        # Escaped
        assert filter(r"text: Q\&A", self.data) is True
        assert filter(r"text: Q\&A", self.data) is True

        # Unescaped
        assert filter(r"text: Q&A", self.data, name="foo") is False
        with pytest.raises(utils.FilterError):
            filter(r"text: foo & bar", self.data)


class TestPluralize:
    """ Function pluralize() """

    def test_basic(self):
        assert utils.pluralize("cloud") == "clouds"
        assert utils.pluralize("sky") == "skies"
        assert utils.pluralize("boss") == "bosses"


class TestListed:
    """ Function listed() """

    def test_basic(self):
        assert listed(range(1)) == '0'
        assert listed(range(2)) == '0 and 1'

    def test_quoting(self):
        assert listed(range(3), quote='"') == '"0", "1" and "2"'

    def test_max(self):
        assert listed(range(4), max=3) == '0, 1, 2 and 1 more'
        assert listed(range(5), 'number', max=2) == '0, 1 and 3 more numbers'

    def test_text(self):
        assert listed(range(6), 'category') == '6 categories'
        assert listed(7, "leaf", "leaves") == '7 leaves'
        assert listed(0, "item") == "0 items"


class TestSplit:
    """ Function split() """

    def test_basic(self):
        assert utils.split('a b c') == ['a', 'b', 'c']
        assert utils.split('a, b, c') == ['a', 'b', 'c']
        assert utils.split(['a, b', 'c']) == ['a', 'b', 'c']


class TestLogging:
    """ Logging """

    def test_level(self):
        for level in [1, 4, 7, 10, 20, 30, 40]:
            utils.Logging('fmf').set(level)
            assert utils.Logging('fmf').get() == level

    def test_smoke(self):
        utils.Logging('fmf').set(utils.LOG_ALL)
        utils.info("something")
        utils.log.info("info")
        utils.log.debug("debug")
        utils.log.cache("cache")
        utils.log.data("data")
        utils.log.all("all")


class TestColoring:
    """ Coloring """

    def test_invalid(self):
        with pytest.raises(RuntimeError):
            utils.Coloring().set(3)

    def test_mode(self):
        for mode in range(3):
            utils.Coloring().set(mode)
            assert utils.Coloring().get() == mode

    def test_color(self):
        utils.Coloring().set()
        utils.color("text", "lightblue", enabled=True)


class TestCache:
    """ Local cache manipulation """

    def test_clean_cache_directory(self, tmpdir):
        utils.set_cache_directory(str(tmpdir))
        file_inside = tmpdir.join('some_file')
        file_inside.write('content')
        assert os.path.isfile(str(file_inside))
        utils.clean_cache_directory()
        assert not os.path.isdir(str(tmpdir))
        utils.set_cache_directory(None)

    def test_set_cache_expiration(self):
        with pytest.raises(ValueError):
            utils.set_cache_expiration('string')


@pytest.mark.web
class TestFetch:
    """ Remote reference from fmf github """

    def test_fetch_default_branch(self):
        # On GitHub 'main' is the default
        repo = utils.fetch_repo(GIT_REPO)
        output, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], repo)
        assert 'main' in output
        # The beakerlib library still uses 'master'
        repo = utils.fetch_repo(GIT_REPO_MASTER)
        output, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], repo)
        assert 'master' in output

    def test_switch_branches(self):
        # Default branch
        repo = utils.fetch_repo(GIT_REPO)
        output, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], repo)
        assert 'main' in output
        # Custom commit
        repo = utils.fetch_repo(GIT_REPO, '0.12')
        output, _ = run(['git', 'rev-parse', 'HEAD'], repo)
        assert '6570aa5' in output
        # Back to the default branch
        repo = utils.fetch_repo(GIT_REPO)
        output, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], repo)
        assert 'main' in output

    def test_shallow_clone(self, tmpdir):
        fetched_to = utils.fetch_repo(GIT_REPO, destination=str(tmpdir))
        out, _ = run(["git", "rev-parse", "--is-shallow-repository"], fetched_to)
        assert 'true' in out

        fetched_to = utils.fetch_repo(GIT_REPO, destination=str(tmpdir), ref='fedora')
        out, _ = run(["git", "rev-parse", "--is-shallow-repository"], fetched_to)
        assert 'false' in out

    def test_fetch_valid_id(self):
        repo = utils.fetch_repo(GIT_REPO, '0.10')
        assert utils.os.path.isfile(utils.os.path.join(repo, 'fmf.spec'))

    @pytest.mark.skipif(
        not hasattr(pytest, "warns"), reason="Missing pytest.warns")
    def test_fetch_deprecation(self):
        with pytest.warns(FutureWarning):
            repo = utils.fetch(GIT_REPO, '0.10')
        assert utils.os.path.isfile(utils.os.path.join(repo, 'fmf.spec'))

    def test_fetch_invalid_url(self):
        with pytest.raises(utils.GeneralError):
            utils.fetch_repo('invalid')

    def test_fetch_invalid_ref(self):
        with pytest.raises(utils.GeneralError):
            utils.fetch_repo(GIT_REPO, 'invalid')

    def test_cache_expiration(self):
        repo = utils.fetch_repo(GIT_REPO)
        fetch_head = (os.path.join(repo, '.git', 'FETCH_HEAD'))
        os.remove(fetch_head)
        repo = utils.fetch_repo(GIT_REPO)
        assert os.path.isfile(fetch_head)

    @pytest.mark.skipif(os.geteuid() == 0, reason="Running as root")
    def test_invalid_cache_directory(self, monkeypatch):
        with pytest.raises(utils.GeneralError):
            monkeypatch.setenv("XDG_CACHE_HOME", "/etc")
            utils.fetch_repo(GIT_REPO)

    def test_custom_directory(self, monkeypatch, tmpdir):
        target = str(tmpdir.join('dir'))
        utils.set_cache_directory(target)
        cache = utils.get_cache_directory()
        assert target == cache

        # Environment takes precedence
        target_env = str(tmpdir.join('from_env'))
        utils.set_cache_directory(target)  # no-op since it stays same
        monkeypatch.setenv("FMF_CACHE_DIRECTORY", target_env)
        cache = utils.get_cache_directory()
        assert target_env == cache

    @pytest.mark.parametrize("trailing", ['', '/'])
    def test_destination(self, tmpdir, trailing):
        # Does not exist
        dest = str(tmpdir.join('branch_new' + trailing))
        repo = utils.fetch_repo(GIT_REPO, destination=dest)
        assert repo == dest
        assert os.path.isfile(os.path.join(repo, 'fmf.spec'))

        # Is an empty directory
        dest = str(tmpdir.mkdir('another' + trailing))
        repo = utils.fetch_repo(GIT_REPO, destination=dest)
        assert repo == dest
        assert os.path.isfile(os.path.join(repo, 'fmf.spec'))

    def test_invalid_destination(self, tmpdir):
        # Is a file
        dest = tmpdir.join('file')
        dest.write('content')
        with pytest.raises(utils.GeneralError):
            utils.fetch_repo(GIT_REPO, destination=str(dest))

        # Is a directory, but not empty
        dest = tmpdir.mkdir('yet_another')
        dest.join('some_file').write('content')
        with pytest.raises(utils.GeneralError) as error:
            utils.fetch_repo(GIT_REPO, destination=str(dest))
        # Git's error message
        assert "already exists and is not an empty" in error.value.args[1].output
        # We report same error message as before
        assert str(error.value) == str(error.value.args[1])

    def test_env(self):
        # Nonexistent repo on github makes git to ask for password
        # Set handler for user input as echo to return immediately
        with pytest.raises(utils.GeneralError) as error:
            utils.fetch_repo('https://github.com/psss/fmf-nope-nope.git',
                             env={"GIT_ASKPASS": "echo"})
        # Assert 'git clone' string in exception's message
        assert "git clone" in error.value.args[0]

    @pytest.mark.parametrize("ref", ["main", "0.10", "8566a39"])
    def test_out_of_sync_ref(self, ref):
        """ Solve Your branch is behind ... """
        repo = utils.fetch_repo(GIT_REPO, ref)
        out, err = run(["git", "rev-parse", "HEAD"], repo)
        old_ref = out
        # Move head one commit back, doesn't invalidate FETCH!
        out, err = run(["git", "reset", "--hard", "HEAD^1"], repo)
        out, err = run(["git", "rev-parse", "HEAD"], repo)
        assert out != old_ref
        # Fetch again, it should move the head back to origin/main
        repo = utils.fetch_repo(GIT_REPO, ref)
        out, err = run(["git", "rev-parse", "HEAD"], repo)
        assert out == old_ref

    def test_fetch_concurrent(self):
        def do_fetch_repo():
            try:
                utils.fetch_repo(GIT_REPO, '0.10')
                q.put(True)
            except Exception as error:
                q.put(error)

        # make sure cache is empty (is there a better way how to target repo?)
        repo = utils.fetch_repo(GIT_REPO, '0.10')
        shutil.rmtree(repo)

        q = queue.Queue()
        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=do_fetch_repo))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # for number of threads check their results
        all_good = True
        for t in threads:
            value = q.get()
            if isinstance(value, Exception):
                print(value)  # so it is visible in the output
                all_good = False
        assert all_good

    def test_fetch_concurrent_timeout(self, monkeypatch, tmpdir):
        # Much shorter timeout
        monkeypatch.setattr('fmf.utils.FETCH_LOCK_TIMEOUT', 2)

        def long_run(*args, **kwargs):
            # Runs several times inside fetch so it is longer than timeout
            time.sleep(2)

        def no_op(*args, **kwargs):
            pass

        # Patch run to use sleep instead
        monkeypatch.setattr('fmf.utils.run', long_run)
        monkeypatch.setattr('fmf.utils.shutil.copyfile', no_op)

        # Background thread to fetch_repo() the same destination acquiring lock
        def target():
            utils.fetch_repo(GIT_REPO, '0.10', destination=str(tmpdir))
        thread = threading.Thread(target=target)
        thread.start()

        # Small sleep to mitigate race
        time.sleep(2)

        # "Real" fetch shouldn't get the lock
        with pytest.raises(utils.GeneralError):
            utils.fetch_repo(GIT_REPO, '0.10', destination=str(tmpdir))

        # Wait on parallel thread to finish
        thread.join()

    def test_fetch_tree_concurrent_timeout(self, monkeypatch, tmpdir):
        # Much shorter timeouts
        monkeypatch.setattr('fmf.utils.FETCH_LOCK_TIMEOUT', 1)
        monkeypatch.setattr('fmf.utils.NODE_LOCK_TIMEOUT', 2)

        real_fetch_repo = utils.fetch_repo

        def long_fetch_repo(*args, **kwargs):
            time.sleep(4)
            return real_fetch_repo(*args, **kwargs)

        # Patch fetch_repo with delay
        monkeypatch.setattr('fmf.utils.fetch_repo', long_fetch_repo)
        # Without remembering get_cache_directory value
        monkeypatch.setattr('fmf.utils._CACHE_DIRECTORY', str(tmpdir))

        # Background thread to fetch_tree() the same destination acquiring lock
        def target():
            utils.fetch_tree(GIT_REPO, '0.10')
        thread = threading.Thread(target=target)
        thread.start()

        # Small sleep to mitigate race
        time.sleep(1)

        # "Real" fetch shouldn't get the lock
        with pytest.raises(utils.GeneralError):
            utils.fetch_tree(GIT_REPO, '0.10')

        # Wait on parallel thread to finish
        thread.join()

    def test_force_cache_fetch(self, monkeypatch, tmpdir):
        # Own cache dir without remembering get_cache_directory value
        monkeypatch.setattr('fmf.utils._CACHE_DIRECTORY', str(tmpdir))
        repo = utils.fetch_repo(GIT_REPO, '0.10')
        fetch_head = (os.path.join(repo, '.git', 'FETCH_HEAD'))
        assert os.path.isfile(fetch_head)
        utils.invalidate_cache()
        assert not os.path.isfile(fetch_head)


class TestDictToYaml:
    """ Verify dictionary to yaml format conversion """

    def test_sort(self):
        """ Verify key sorting """
        data = dict(y=2, x=1)
        assert fmf.utils.dict_to_yaml(data) == "y: 2\nx: 1\n"
        assert fmf.utils.dict_to_yaml(data, sort=True) == "x: 1\ny: 2\n"


class TestSplitPatternReplacement:
    @pytest.mark.parametrize("src", [
        "",  # Empty input
        "/",  # Not long enough input
        ";/;",  # Not long enough - missing 'REPL;'
        ";;;",  # PATTERN and REPL parts empty
        "/a/b/c",  # Input after trailing deliminer
        "/a/b/c/d/",  # More than 3 delimiters
        "/x;y/",  # No REPL part as delimiter is /
        "/a/a;"  # No trailing delimiter
        ])
    def test_invalid(self, src):
        with pytest.raises(utils.FormatError):
            utils.split_pattern_replacement(src)

    def test_simple(self):
        assert utils.split_pattern_replacement(
            '/a/b/') == utils.PatternReplacement('a', 'b')
        assert utils.split_pattern_replacement(
            ';ac/dc;rose;') == utils.PatternReplacement('ac/dc', 'rose')
