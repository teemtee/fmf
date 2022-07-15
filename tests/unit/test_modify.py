import io
import os
import re
import tempfile
import unittest
from shutil import copytree, rmtree

import pytest

from fmf.base import Tree
from fmf.context import Context
from fmf.utils import GeneralError

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLES = PATH + "/../../examples/"


class TestModify(unittest.TestCase):
    """ Verify storing modifed data to disk """

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
        # Modify data and store to disk
        with item as data:
            data.update(dict(depth=2000, new="two\nlines"))
        with item.parent as data:
            data.update(dict(parent_attr="value"))
        # Reload the data and verify
        self.wget = Tree(self.tempdir)
        item = self.wget.find('/recursion/deep')
        self.assertEqual(item.data['tags'], ['Tier2'])
        self.assertEqual(item.parent.data['tags'], ['Tier2'])
        self.assertEqual(item.data['depth'], 2000)
        self.assertIn('depth', item.data)
        self.assertNotIn('depth', item.parent.data)
        self.assertEqual(item.data['new'], "two\nlines")
        self.assertEqual(item.data['parent_attr'], "value")
        with open(os.path.join(self.tempdir, 'recursion/deep.fmf')) as file:
            self.assertTrue(re.search('two\n +lines', file.read()))

    def test_deep_modify(self):
        """ Deep structures """
        requirements = self.wget.find('/requirements')
        protocols = self.wget.find('/requirements/protocols')
        ftp = self.wget.find('/requirements/protocols/ftp')
        # Modify data and store to disk
        with requirements as data:
            data['new'] = 'some'
        with protocols as data:
            data.update(dict(coverage="changed", new_attr="val"))
        with ftp as data:
            data['server'] = 'vsftpd'
        # Reload the data and verify
        self.wget = Tree(self.tempdir)
        requirements = self.wget.find('/requirements')
        protocols = self.wget.find('/requirements/protocols')
        ftp = self.wget.find('/requirements/protocols/ftp')
        self.assertEqual(requirements.data["new"], "some")
        self.assertEqual(protocols.data["new"], "some")
        self.assertEqual(ftp.data["new"], "some")
        self.assertNotIn("server", protocols.data)
        self.assertIn("server", ftp.data)
        self.assertNotIn("new_attr", requirements.data)
        self.assertIn("new_attr", protocols.data)
        self.assertIn("new_attr", ftp.data)
        self.assertEqual(protocols.data["coverage"], "changed")
        self.assertIn('adjust', ftp.data)
        self.assertEqual(ftp.data['adjust'][0]['enabled'], False)
        self.assertEqual(ftp.data['adjust'][0]['when'], "arch != x86_64")

    def test_deep_hierarchy(self):
        """ Multiple virtual hierarchy levels shortcut """
        with open(os.path.join(self.tempdir, 'deep.fmf'), 'w') as file:
            file.write('/one/two/three:\n x: 1\n')
        deep = Tree(self.tempdir).find('/deep/one/two/three')
        with deep as data:
            data['y'] = 2
        deep = Tree(self.tempdir).find('/deep/one/two/three')
        self.assertEqual(deep.get('x'), 1)
        self.assertEqual(deep.get('y'), 2)

    def test_modify_empty(self):
        """ Nodes with no content should be handled as an empty dict """
        with self.wget.find('/download/requirements/spider') as data:
            data['x'] = 1
        self.wget = Tree(self.tempdir)
        node = self.wget.find('/download/requirements/spider')
        self.assertEqual(node.data['x'], 1)

    def test_modify_pop(self):
        """ Pop elements from node data """
        item = '/requirements/protocols/ftp'
        with self.wget.find(item) as data:
            data.pop('coverage')
            data.pop('tester+')
        self.wget = Tree(self.tempdir)
        node = self.wget.find(item)
        self.assertNotIn('coverage', node.data)
        self.assertIn('tester', node.data)
        self.assertIn('requirement', node.data)

    def test_modify_clear(self):
        """ Clear node data """
        item = '/requirements/protocols/ftp'
        with self.wget.find(item) as data:
            data.clear()
        self.wget = Tree(self.tempdir)
        node = self.wget.find(item)
        self.assertNotIn('coverage', node.data)
        self.assertIn('tester', node.data)
        self.assertNotIn('requirement', node.data)

    def test_modify_unsupported_method(self):
        """ Raise error for trees initialized from a dict """
        with pytest.raises(GeneralError, match='No raw data'):
            with Tree(dict(x=1)) as data:
                data['y'] = 2

    def test_context_manager(self):
        """ Use context manager to save node data """
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

    def test_modify_unicode(self):
        """ Ensure that unicode characters are properly handled """
        path = os.path.join(self.tempdir, 'unicode.fmf')
        with io.open(path, 'w', encoding='utf-8') as file:
            file.write('jméno: Leoš')
        with Tree(self.tempdir).find('/unicode') as data:
            data['příjmení'] = 'Janáček'
        reloaded = Tree(self.tempdir).find('/unicode')
        assert reloaded.get('jméno') == 'Leoš'
        assert reloaded.get('příjmení') == 'Janáček'

    def test_modify_after_adjust(self):
        """ Preserve original data even when adjust is used """
        item = '/requirements/protocols/ftp'
        wget = Tree(self.tempdir)
        # Expects new attribute + original data
        expected = {'new_attr': "new_value"}
        expected.update(wget.find(item).copy().get())
        wget.adjust(Context(arch='ppc64le'))
        with wget.find(item) as data:
            data['new_attr'] = "new_value"
        assert expected == Tree(self.tempdir).find(item).get()
