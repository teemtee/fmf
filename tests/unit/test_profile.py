from unittest import TestCase
from pathlib import Path

import yaml

from fmf import Tree
from fmf.profile import Profile

PROFILE_PATH = Path(__file__).parent / "data" / "profile"
PROFILE =  PROFILE_PATH / "profile_file.yaml"

class ProfileLoad(TestCase):
    def setUp(self) -> None:
        with PROFILE.open("r") as profile_file:
            self.profile_data = yaml.safe_load(profile_file)

    def test_load(self):
        profiles = []
        for k, v in self.profile_data.items():
            profiles.append(Profile(v, name=k))


class ProfileApply(TestCase):
    def setUp(self) -> None:
        with PROFILE.open("r") as profile_file:
            self.profile_data = yaml.safe_load(profile_file)
        self.profiles = []
        for k, v in self.profile_data.items():
            self.profiles.append(Profile(v, name=k))
        self.fmf_tree = Tree(PROFILE_PATH / "tree")

    def test_apply_to_test(self):
        for profile in self.profiles:
            self.fmf_tree.apply_profile(profile)
        for item in self.fmf_tree.climb():
            print(item.data)
