import os
import unittest

from fmf.base import Tree

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLES = PATH + "/../../examples/"


class TestGetItems(unittest.TestCase):
    """ Verify getter of items """

    def setUp(self):
        self.wget_path = EXAMPLES + "wget"
        self.wget = Tree(self.wget_path)

    def test_item_child(self):
        item = self.wget['/recursion']['/deep']
        self.assertEqual(item.get("depth"), 1000)
        self.assertEqual(item.name, '/recursion/deep')

    def test_item_data(self):
        item = self.wget['/recursion']['/deep']
        self.assertEqual(item["depth"], 1000)
        self.assertEqual(item.name, '/recursion/deep')

    def test_not_existing_key_child(self):
        with self.assertRaises(KeyError):
            self.wget['/bbbad']

    def test_not_existing_key_data(self):
        item = self.wget['/recursion']['/deep']
        with self.assertRaises(KeyError):
            item["bbbad"]
