import os
import unittest

import fmf

# Prepare path to examples
PATH = os.path.dirname(os.path.realpath(__file__))
EXAMPLES = PATH + "/../../examples/"


class TestNoInheritance(unittest.TestCase):
    """ Verify storing modifed data to disk """

    def setUp(self):
        self.path = EXAMPLES + "no_inherit"
        self.tree = fmf.Tree(self.path)

    def test_base(self):
        root_item = self.tree.find('/')
        a_item = self.tree.find('/a')
        inherite_item = self.tree.find('/a/inherited')
        self.assertIn("special", root_item.data)
        self.assertIn("special", inherite_item.data)
        self.assertNotIn("special", a_item.data)

    def test_undefine(self):
        c_item = self.tree.find("/a/stop_inherit")
        no_c_item = self.tree.find("/a/stop_inherit/no_c")
        self.assertNotIn("special", c_item.data)
        self.assertNotIn("special", no_c_item.data)
        self.assertIn("c", c_item.data)
        self.assertNotIn("c", no_c_item.data)
