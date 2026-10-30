"""Tests for the source-line tracking added to ast_extractor.parse_ast_to_tree."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ast_extractor import parse_ast_to_tree  # noqa: E402

DUMP = """|-FunctionDecl 0x55 <main.cpp:3:1, line:10:1> line:3:5 main 'int ()'
| `-CompoundStmt 0x56 <col:12, line:10:1>
|   |-DeclStmt 0x57 <line:4:5, col:14>
|   | `-VarDecl 0x58 <col:5, col:13> col:9 x 'int' cinit
|   |   `-IntegerLiteral 0x59 <col:13> 'int' 5
|   |-IfStmt 0x5a <line:5:5, line:7:5>
|   | |-BinaryOperator 0x5b <line:5:9, col:13> 'bool' '>'
|   | | |-ImplicitCastExpr 0x5c <col:9> 'int' <LValueToRValue>
|   | | | `-DeclRefExpr 0x5d <col:9> 'int' lvalue Var 0x58 'x' 'int'
|   | | `-IntegerLiteral 0x5e <col:13> 'int' 3
|   | `-CompoundStmt 0x5f <col:16, line:7:5>
|   `-ReturnStmt 0x60 <line:9:5, col:12>
|     `-IntegerLiteral 0x61 <col:12> 'int' 0"""


def find(nodes, type_name):
    for n in nodes:
        if n["type"] == type_name:
            return n
        hit = find(n["children"], type_name)
        if hit:
            return hit
    return None


class AstLineTests(unittest.TestCase):
    def setUp(self):
        self.tree = parse_ast_to_tree(DUMP)

    def test_function_spans_its_whole_body(self):
        fn = self.tree[0]
        self.assertEqual((fn["line"], fn["end_line"]), (3, 10))

    def test_relative_col_locations_keep_the_current_line(self):
        self.assertEqual(find(self.tree, "VarDecl")["line"], 4)
        self.assertEqual(find(self.tree, "IntegerLiteral")["line"], 4)

    def test_multi_line_statement_has_a_range(self):
        node = find(self.tree, "IfStmt")
        self.assertEqual((node["line"], node["end_line"]), (5, 7))

    def test_hidden_nodes_still_advance_the_line_state(self):
        # ImplicitCastExpr is not shown, but the nodes after it must still be on line 5.
        self.assertEqual(find(self.tree, "DeclRefExpr")["line"], 5)
        self.assertEqual(find(self.tree, "ReturnStmt")["line"], 9)

    def test_label_drops_addresses_and_locations(self):
        self.assertEqual(self.tree[0]["label"], "main 'int ()'")
        self.assertEqual(find(self.tree, "BinaryOperator")["label"], "'bool' '>'")
        self.assertEqual(find(self.tree, "CompoundStmt")["label"], "")

    def test_existing_fields_are_unchanged(self):
        fn = self.tree[0]
        self.assertIn("main", fn["details"])
        self.assertIsInstance(fn["children"], list)

    def test_windows_style_absolute_path(self):
        dump = "|-FunctionDecl 0x1 <C:\\Users\\me\\Temp\\main.cpp:12:1, line:14:1> line:12:6 helper 'void ()'"
        node = parse_ast_to_tree(dump)[0]
        self.assertEqual((node["line"], node["end_line"]), (12, 14))

    def test_empty_input(self):
        self.assertEqual(parse_ast_to_tree(""), [])


if __name__ == "__main__":
    unittest.main()
