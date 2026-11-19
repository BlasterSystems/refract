from __future__ import annotations

import fnmatch
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PackagingTests(unittest.TestCase):
    def test_every_template_is_included_in_package_data(self) -> None:
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        patterns = config["tool"]["setuptools"]["package-data"]["refract"]
        package = ROOT / "src/refract"
        missing = [
            path.relative_to(package).as_posix()
            for path in (package / "templates").rglob("*")
            if path.is_file()
            and not any(
                fnmatch.fnmatch(path.relative_to(package).as_posix(), pattern.replace("**/", "*"))
                for pattern in patterns
            )
        ]
        self.assertEqual([], missing, "templates missing from the wheel; extend tool.setuptools.package-data")


if __name__ == "__main__":
    unittest.main()
