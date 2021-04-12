# coding: utf-8

from __future__ import unicode_literals, absolute_import

import os
import pytest
import time
import threading
import tempfile
import fmf.utils as utils
import fmf.cli
from fmf.base import Tree
from shutil import rmtree

try:
    import queue
except ImportError:
    import Queue as queue


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLES = PATH + "/../../examples/"
FMF_REPO = "https://github.com/psss/fmf.git"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Tree
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class TestTree(object):
    """ Tree class """

    def setup_method(self, method):
        """ Load examples """
        self.wget = Tree(EXAMPLES + "wget")
        self.merge = Tree(EXAMPLES + "merge")

    def test_basic(self):
        """ No directory path given """
        with pytest.raises(utils.GeneralError):
            Tree("")
        with pytest.raises(utils.GeneralError):
            Tree(None)
        with pytest.raises(utils.RootError):
            Tree("/")

    def test_hidden(self):
        """ Hidden files and directories """
        assert ".hidden" not in self.wget.children

    def test_inheritance(self):
        """ Inheritance and data types """
        deep = self.wget.find("/recursion/deep")
        assert deep.data["depth"] == 1000
        assert deep.data["description"] == "Check recursive download options"
        assert deep.data["tags"] == ["Tier2"]

    def test_scatter(self):
        """ Scattered files """
        scatter = Tree(EXAMPLES + "scatter").find("/object")
        assert len(list(scatter.climb())) == 1
        assert scatter.data["one"] == 1
        assert scatter.data["two"] == 2
        assert scatter.data["three"] == 3

    def test_scattered_inheritance(self):
        """ Inheritance of scattered files """
        grandson = Tree(EXAMPLES + "child").find("/son/grandson")
        assert grandson.data["name"] == "Hugo"
        assert grandson.data["eyes"] == "blue"
        assert grandson.data["nose"] == "long"
        assert grandson.data["hair"] == "fair"

    def test_subtrees(self):
        """ Subtrees should be ignored """
        child = Tree(EXAMPLES + "child")
        assert child.find("/nobody") is None

    def test_empty(self):
        """ Empty structures should be ignored """
        child = Tree(EXAMPLES + "empty")
        assert child.find("/nothing") is None
        assert child.find("/zero") is None

    def test_none_key(self):
        """ Handle None keys """
        with pytest.raises(utils.FormatError):
            tree = Tree({None: "weird key"})

    def test_deep_hierarchy(self):
        """ Deep hierarchy on one line """
        deep = Tree(EXAMPLES + "deep")
        assert len(deep.children) == 1

    def test_deep_dictionary(self):
        """ Get value from a deep dictionary """
        deep = Tree(EXAMPLES + "deep")
        assert deep.data["hardware"]["memory"]["size"] == 8
        assert deep.get(["hardware", "memory", "size"]) == 8
        assert deep.get(["hardware", "bad", "size"], 12) == 12
        assert deep.get("nonexistent", default=3) == 3

    def test_merge_plus(self):
        """ Extending attributes using the '+' suffix """
        child = self.merge.find("/parent/extended")
        assert "General" in child.data["description"]
        assert "Specific" in child.data["description"]
        assert child.data["tags"] == ["Tier1", "Tier2", "Tier3"]
        assert child.data["time"] == 15
        assert child.data["vars"] == dict(x=1, y=2, z=3)
        assert child.data["disabled"] == True
        assert "time+" not in child.data
        with pytest.raises(utils.MergeError):
            child.data["time+"] = "string"
            child.inherit()

    def test_merge_minus(self):
        """ Reducing attributes using the '-' suffix """
        child = self.merge.find("/parent/reduced")
        assert "General" in child.data["description"]
        assert "description" not in child.data["description"]
        assert child.data["tags"] == ["Tier1"]
        assert child.data["time"] == 5
        assert child.data["vars"] == dict(x=1)
        assert "time+" not in child.data
        with pytest.raises(utils.MergeError):
            child.data["disabled-"] = True
            child.inherit()
        child.data.pop("disabled-")
        with pytest.raises(utils.MergeError):
            child.data["time-"] = "bad"
            child.inherit()

    def test_merge_deep(self):
        """ Merging a deeply nested dictionary """
        child = self.merge.find("/parent/buried")
        assert child.data["very"]["deep"]["dict"] == dict(x=2, y=1, z=0)

    def test_get(self):
        """ Get attributes """
        assert isinstance(self.wget.get(), dict)
        assert "Petr" in self.wget.get("tester")

    def test_show(self):
        """ Show metadata """
        assert isinstance(self.wget.show(brief=True), type(""))
        assert self.wget.show(brief=True).endswith("\n")
        assert isinstance(self.wget.show(), type(""))
        assert self.wget.show().endswith("\n")
        assert "tester" in self.wget.show()

    def test_update(self):
        """ Update data """
        data = self.wget.get()
        self.wget.update(None)
        assert self.wget.data == data

    def test_find_node(self):
        """ Find node by name """
        assert self.wget.find("non-existent") == None
        protocols = self.wget.find("/protocols")
        assert isinstance(protocols, Tree)

    def test_find_root(self):
        """ Find metadata tree root """
        tree = Tree(os.path.join(EXAMPLES, "wget", "protocols"))
        assert tree.find("/download/test")

    def test_yaml_syntax_errors(self):
        """ Handle YAML syntax errors """
        path = tempfile.mkdtemp()
        fmf.cli.main("fmf init", path)
        with open(os.path.join(path, "main.fmf"), "w") as main:
            main.write("missing\ncolon:")
        with pytest.raises(utils.FileError):
            tree = fmf.Tree(path)
        rmtree(path)

    def test_yaml_duplicate_keys(self):
        """ Handle YAML duplicate keys """
        path = tempfile.mkdtemp()
        fmf.cli.main("fmf init", path)

        # Simple test
        with open(os.path.join(path, "main.fmf"), "w") as main:
            main.write("a: b\na: c\n")
        with pytest.raises(utils.FileError):
            fmf.Tree(path)

        # Add some hierarchy
        subdir = os.path.join(path, "dir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "a.fmf"), "w") as new_file:
            new_file.write("a: d\n")
        with pytest.raises(utils.FileError):
            fmf.Tree(path)

        # Remove duplicate key, check that inheritance doesn't
        # raise an exception
        with open(os.path.join(path, "main.fmf"), "w") as main:
            main.write("a: b\n")
        fmf.Tree(path)

        rmtree(path)

    def test_inaccessible_directories(self):
        """ Inaccessible directories should be silently ignored """
        directory = tempfile.mkdtemp()
        accessible = os.path.join(directory, "accessible")
        inaccessible = os.path.join(directory, "inaccessible")
        os.mkdir(accessible, 511)
        os.mkdir(inaccessible, 000)
        with open(os.path.join(accessible, "main.fmf"), "w") as main:
            main.write("key: value\n")
        Tree.init(directory)
        tree = Tree(directory)
        assert tree.find("/accessible").get("key") == "value"
        assert tree.find("/inaccessible") is None
        os.chmod(inaccessible, 511)
        rmtree(directory)

    def test_node_copy_complete(self):
        """ Create deep copy of the whole tree """
        original = self.merge
        duplicate = original.copy()
        duplicate.data["x"] = 1
        assert original.parent is None
        assert duplicate.parent is None
        assert original.get("x") is None
        assert duplicate.get("x") == 1

    def test_node_copy_child(self):
        """ Duplicate child changes do not affect original """
        original = self.merge
        duplicate = original.copy()
        original_child = original.find("/parent/extended")
        duplicate_child = duplicate.find("/parent/extended")
        original_child.data["original"] = True
        duplicate_child.data["duplicate"] = True
        assert original_child.get("original") is True
        assert duplicate_child.get("original") is None
        assert original_child.get("duplicate") is None
        assert duplicate_child.get("duplicate") is True

    def test_node_copy_subtree(self):
        """ Create deep copy of a subtree """
        original = self.merge.find("/parent/extended")
        duplicate = original.copy()
        duplicate.data["x"] = 1
        assert original.parent == duplicate.parent
        assert duplicate.parent.name == "/parent"
        assert duplicate.get("x") == 1
        assert original.get("x") is None


class TestRemote(object):
    """ Get tree node data using remote reference """

    @pytest.mark.web
    def test_tree_node_remote(self):
        reference = {
            "url": FMF_REPO,
            "ref": "0.10",
            "path": "examples/deep",
            "name": "/one/two/three",
        }

        # Values of test in 0.10 tag
        expected_data = {
            "hardware": {"memory": {"size": 8}, "network": {"model": "e1000"}},
            "key": "value",
        }

        # Full identifier
        node = Tree.node(reference)
        assert node.get() == expected_data

        # Default ref
        reference.pop("ref")
        node = Tree.node(reference)
        assert node.get() == expected_data

        # Raise exception for invalid tree nodes
        with pytest.raises(utils.ReferenceError):
            reference["name"] = "not_existing_name_"
            node = Tree.node(reference)

    def test_tree_node_local(self):
        reference = {
            "path": EXAMPLES + "wget",
            "name": "/protocols/https",
        }
        node = Tree.node(reference)
        assert node.get("time") == "1 min"

    def test_tree_node_relative_path(self):
        with pytest.raises(utils.ReferenceError):
            Tree.node(dict(path="some/relative/path"))

    @pytest.mark.web
    def test_tree_commit(self, tmpdir):
        # Tag
        node = Tree.node(dict(url=FMF_REPO, ref="0.12"))
        assert node.commit == "6570aa5f10729991625d74036473a71f384d745b"
        # Hash
        node = Tree.node(dict(url=FMF_REPO, ref="fa05dd9"))
        assert "fa05dd9" in node.commit
        assert "fa05dd9" in node.commit  # return already detected value
        # Data
        node = Tree(dict(x=1))
        assert node.commit is False
        # No git repository
        tree = Tree(Tree.init(str(tmpdir)))
        assert tree.commit is False

    @pytest.mark.web
    def test_tree_concurrent(self):
        def get_node(ref):
            try:
                node = Tree.node(dict(url=FMF_REPO, ref=ref))
                q.put(True)
            except Exception as error:
                q.put(error)

        possible_refs = [None, "0.12", "fa05dd9"]
        q = queue.Queue()
        threads = []
        for i in range(10):
            # Arguments vary based on current thread index
            threads.append(
                threading.Thread(
                    target=get_node, args=(possible_refs[i % len(possible_refs)],)
                )
            )
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # For number of threads check their results
        all_good = True
        for t in threads:
            value = q.get()
            if isinstance(value, Exception):
                print(value)  # so it is visible in the output
                all_good = False
        assert all_good

    def test_tree_concurrent_timeout(self, monkeypatch):
        # Much shorter timeout
        monkeypatch.setattr("fmf.utils.NODE_LOCK_TIMEOUT", 2)

        def long_fetch(*args, **kwargs):
            # Longer than timeout
            time.sleep(7)
            return EXAMPLES

        # Patch fetch to sleep and later return tmpdir path
        monkeypatch.setattr("fmf.utils.fetch_repo", long_fetch)

        # Background thread to get node() acquiring lock
        def target():
            Tree.node(
                {
                    "url": "localhost",
                    "name": "/",
                }
            )

        thread = threading.Thread(target=target)
        thread.start()

        # Small sleep to mitigate race
        time.sleep(2)

        # "Real" fetch shouldn't get the lock
        with pytest.raises(utils.GeneralError):
            Tree.node(
                {
                    "url": "localhost",
                    "name": "/",
                }
            )

        # Wait on parallel thread to finish
        thread.join()
