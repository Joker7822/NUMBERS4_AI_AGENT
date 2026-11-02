"""Keep the public release label consistent without implying a tagged release."""
import re
import tomllib
from pathlib import Path
import unittest

from numbers4_agent import __version__


ROOT=Path(__file__).resolve().parents[1]


class ProjectMetadataTests(unittest.TestCase):
    def test_version_is_consistent_in_package_readme_and_dashboard(self):
        pyproject=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
        self.assertEqual(pyproject['project']['version'],__version__)
        self.assertRegex(__version__,r'^0\.[0-9]+\.[0-9]+$')
        readme=(ROOT/'README.md').read_text(encoding='utf-8')
        dashboard=(ROOT/'docs'/'index.html').read_text(encoding='utf-8')
        self.assertIn(f'v{__version__}',readme)
        self.assertIn(f'v{__version__}',dashboard)
        labels=set(re.findall(r'\bv0\.\d+\.\d+\b',readme+'\n'+dashboard))
        self.assertEqual(labels,{f'v{__version__}'})


if __name__=='__main__':
    unittest.main()
