# coding: utf-8

from __future__ import unicode_literals, absolute_import

import unittest
import os
import tempfile
from fmf.base import Tree
from shutil import rmtree, copytree

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLES = PATH + "/../../examples/"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Tree
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class TestModify(unittest.TestCase):
    """ Tree class """

    def setUp(self):
        self.wget_path = EXAMPLES + "wget"
        self.tempdir = tempfile.mktemp()
        copytree(self.wget_path, self.tempdir)
        self.wget = Tree(self.tempdir)

    def tearDown(self):
        rmtree(self.tempdir)

    def test_inheritance(self):
        """ Inheritance and data types """
        item = self.wget.find('/recursion/deep')
        item_parent = self.wget.find('/recursion')
        # reload the data
        item.modify(dict(depth=2000, new="some")).save()
        item.parent.modify(dict(parent_attr="value")).save()
        self.wget = Tree(self.tempdir)
        item = self.wget.find('/recursion/deep')
        self.assertEqual(item.data['tags'], ['Tier2'])
        self.assertEqual(item.parent.data['tags'], ['Tier2'])
        self.assertEqual(item.data['depth'], 2000)
        self.assertIn('depth', item.data)
        self.assertNotIn('depth', item.parent.data)
        self.assertEqual(item.data['new'], "some")
        self.assertEqual(item.data['parent_attr'], "value")

    def test_deep_modify(self):
        req = self.wget.find('/requirements')
        proto = self.wget.find('/requirements/protocols')
        ftp = self.wget.find('/requirements/protocols/ftp')

        req.modify(dict(new="some")).save()
        proto.modify(dict(coverage="changed", new_attr="val")).save()
        ftp.modify(dict(server="vsftpd")).save()
        # reload the data
        self.wget = Tree(self.tempdir)
        req = self.wget.find('/requirements')
        proto = self.wget.find('/requirements/protocols')
        ftp = self.wget.find('/requirements/protocols/ftp')
        self.assertEqual(req.data["new"], "some")
        self.assertEqual(proto.data["new"], "some")
        self.assertEqual(ftp.data["new"], "some")
        self.assertNotIn("server",proto.data)
        self.assertIn("server", ftp.data)
        self.assertNotIn("new_attr", req.data)
        self.assertIn("new_attr", proto.data)
        self.assertIn("new_attr", ftp.data)
        self.assertEqual(proto.data["coverage"], "changed")
        self.assertIn('adjust', ftp.data)
        self.assertEqual(ftp.data['adjust'][0]['enabled'], False)
        self.assertEqual(ftp.data['adjust'][0]['when'], "arch != x86_64")

    def test_modify_empty(self):
        """
        It must not raise error when empty elemenent node
        """
        self.wget.find('/download/requirements/spider').modify(dict(x=1)).save()
        self.wget = Tree(self.tempdir)
        node = self.wget.find('/download/requirements/spider')
        self.assertEqual(node.data['x'], 1)

    def test_modify_pop(self):
        """
        pop elements from node
        """
        item = '/requirements/protocols/ftp'
        self.wget.find(item).modify("coverage", "tester+", method="pop").save()
        self.wget = Tree(self.tempdir)
        node = self.wget.find(item)
        self.assertNotIn('coverage', node.data)
        self.assertIn('tester', node.data)
        self.assertIn('requirement', node.data)

    def test_modify_clear(self):
        """
        clear data in node
        """
        item = '/requirements/protocols/ftp'
        self.wget.find(item).modify(method="clear").save()
        self.wget = Tree(self.tempdir)
        node = self.wget.find(item)
        self.assertNotIn('coverage', node.data)
        self.assertIn('tester', node.data)
        self.assertNotIn('requirement', node.data)

    def test_modify_unsupported_method(self):
        """
        raise error for unsupported method
        """
        item = '/requirements/protocols/ftp'
        self.assertRaises(ValueError, self.wget.find(item).modify, method="keys")

    def test_context_manager(self):
        """
        try to use context manager for save node data
        """
        item = '/requirements/protocols/ftp'
        with self.wget.find(item) as data:
            data.pop("coverage")
            data.pop("tester+")
            data.update(dict(server="vsftpd"))
        self.wget = Tree(self.tempdir)
        node = self.wget.find(item)
        self.assertNotIn('coverage', node.data)
        self.assertIn('tester', node.data)
        self.assertIn('requirement', node.data)
        self.assertIn("server", node.data)
