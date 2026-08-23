import ast
import unittest
from pathlib import Path


class ArchitectureTests(unittest.TestCase):
    def test_world_derivation_does_not_import_benchmarks_or_adapters(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "engine" / "oosc" / "world" / "derive.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        forbidden = ("tau2", "agentdojo", "oosc.adapters", "results", "vendor")
        self.assertFalse([name for name in imported if name.startswith(forbidden)])


if __name__ == "__main__":
    unittest.main()
