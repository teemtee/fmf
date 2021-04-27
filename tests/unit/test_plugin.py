# coding: utf-8

from __future__ import absolute_import, unicode_literals

import os
import tempfile
import unittest
from pathlib import Path
from shutil import copytree, rmtree

from fmf.base import Tree
from fmf.constants import PLUGIN_ENV
from fmf.plugin_loader import enabled_plugins

PATH = Path(__file__).parent
EXAMPLES = PATH / "data"
PLUGIN_PATH = PATH.parent.parent / "fmf" / "plugins"


class Base(unittest.TestCase):
    def setUp(self):
        self.test_path = EXAMPLES / "tests_plugin"
        self.tempdir = tempfile.mktemp()
        copytree(self.test_path, self.tempdir)
        # ensure the cache is cleared, to ensure that plugis are not already
        # stored
        enabled_plugins.cache_clear()

    def tearDown(self):
        enabled_plugins.cache_clear()
        rmtree(self.tempdir)
        os.environ.pop(PLUGIN_ENV)


class Pytest(Base):
    """ Verify reading data done via plugins """

    def setUp(self):
        super().setUp()
        os.environ[PLUGIN_ENV] = "fmf.plugins.pytest"
        self.plugin_tree = Tree(self.tempdir)

    def test_basic(self):
        item = self.plugin_tree.find("/test_basic/test_skip")

        self.assertFalse(item.data.get("enabled"))
        self.assertIn("Jan", item.data["author"])
        self.assertIn(
            "python3 -m pytest -m '' -v test_basic.py::test_skip", item.data
            ["test"])

    def test_modify(self):
        item = self.plugin_tree.find("/test_basic/test_pass")
        self.assertNotIn("duration", item.data)
        self.assertIn("Tier1", item.data["tag"])
        self.assertNotIn("tier2", item.data["tag"])
        self.assertEqual("0", item.data["tier"])
        with item as data:
            data["tag"].append("tier2")
            data["duration"] = ("10m")
            data.pop("tier")

        self.plugin_tree = Tree(self.tempdir)
        item = self.plugin_tree.find("/test_basic/test_pass")
        self.assertIn("duration", item.data)
        self.assertEqual("10m", item.data["duration"])
        self.assertIn("Tier1", item.data["tag"])
        self.assertIn("tier2", item.data["tag"])
        self.assertIn("tier2", item.data["tag"])
        self.assertNotIn("tier", item.data)

    def test_rewrite(self):
        item = self.plugin_tree.find("/test_rewrite/test_pass")
        self.assertNotIn("duration", item.data)
        self.assertIn("Tier1", item.data["tag"])
        self.assertIn("tier2", item.data["tag"])
        self.assertEqual("added", item.data["added_fmf_file"])
        self.assertEqual("Rewrite", item.data["summary"])

    def test_rewrite_modify(self):
        self.test_rewrite()
        item = self.plugin_tree.find("/test_rewrite/test_pass")
        with item as data:
            data["tag+"] += ["tier3"]
            data["extra_id"] = 1234

        self.plugin_tree = Tree(self.tempdir)
        item = self.plugin_tree.find("/test_rewrite/test_pass")
        self.test_rewrite()
        self.assertEqual(1234, item.data["extra_id"])
        self.assertIn("tier3", item.data["tag"])


class Bash(Base):
    """ Verify reading data done via plugins """

    def setUp(self):
        super().setUp()
        os.environ[PLUGIN_ENV] = str(PLUGIN_PATH / "bash.py")
        self.plugin_tree = Tree(self.tempdir)

    def test_read(self):
        item = self.plugin_tree.find("/runtest")
        self.assertIn("tier1", item.data["tag"])
        self.assertIn("./runtest.sh", item.data["test"])
        self.assertIn("Jan", item.data["author"])

    def test_modify(self):
        self.assertNotIn("runtest.fmf", os.listdir(self.tempdir))
        item = self.plugin_tree.find("/runtest")
        self.assertIn("tier1", item.data["tag"])
        self.assertIn("./runtest.sh", item.data["test"])
        with item as data:
            data["tier"] = 0
            data["duration"] = "10m"
        self.plugin_tree = Tree(self.tempdir)
        item = self.plugin_tree.find("/runtest")
        self.assertIn("runtest.fmf", os.listdir(self.tempdir))
        self.assertEqual("10m", item.data["duration"])
        self.assertEqual(0, item.data["tier"])
        self.assertIn("tier1", item.data["tag"])
        self.assertIn("./runtest.sh", item.data["test"])


class TestConf(unittest.TestCase):
    def setUp(self):
        self.test_path = EXAMPLES / "config"
        enabled_plugins.cache_clear()
        self.plugin_tree = Tree(self.test_path)

    def tearDown(self):
        enabled_plugins.cache_clear()

    def test_basic(self):
        item = self.plugin_tree.find("/test_plugin_config/TestCls")
        self.assertEqual(len(item.children), 3)
