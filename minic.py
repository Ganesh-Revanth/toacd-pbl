#!/usr/bin/env python3
"""
minic.py - command-line driver for the MiniC compiler core.

Usage:
    python minic.py program.c                 # compile and run
    python minic.py program.c --tokens --ast --ir --opt
    python minic.py program.c --no-opt        # run the unoptimized IR
    python minic.py -e "int main(){ print(1+2); return 0; }"

Exit status: 0 on success, 1 on lexical/syntax/semantic errors, 2 on runtime errors.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from core.interpreter import run_ir  # noqa: E402
from core.ir import generate_ir  # noqa: E402
from core.lexer import Lexer  # noqa: E402
from core.optimizer import optimize  # noqa: E402
from core.parser import Parser  # noqa: E402
from core.semantic import SemanticAnalyzer  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MiniC compiler driver")
    ap.add_argument("file", nargs="?", help="MiniC source file")
    ap.add_argument("-e", "--expr", help="compile this source string instead of a file")
    ap.add_argument("--tokens", action="store_true", help="print the token stream")
    ap.add_argument("--ast", action="store_true", help="print the AST")
    ap.add_argument("--ir", action="store_true", help="print the unoptimized TAC")
    ap.add_argument("--opt", action="store_true", help="print the optimized TAC and pass statistics")
    ap.add_argument("--no-opt", action="store_true", help="execute the unoptimized IR")
    ap.add_argument("--no-run", action="store_true", help="compile only; do not execute")
    args = ap.parse_args(argv)

    if args.expr is not None:
        source = args.expr
    elif args.file:
        with open(args.file, encoding="utf-8") as fh:
            source = fh.read()
    else:
        ap.error("provide a source file or -e SOURCE")

    lexer = Lexer(source)
    tokens = lexer.tokenize()
    if args.tokens:
        for tok in tokens:
            print(tok)
    errors = [f"lex error: {e}" for e in lexer.errors]

    parser = Parser(tokens)
    ast = parser.parse()
    errors += [f"syntax error: {e}" for e in getattr(parser, "errors", [])]
    if args.ast:
        print(ast.to_tree() if hasattr(ast, "to_tree") else ast)

    if not errors:
        for d in SemanticAnalyzer().analyze(ast):
            errors.append(f"{d.severity} at {d.line}:{d.column}: {d.message}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    ir = generate_ir(ast)
    if args.ir:
        print("\n".join(str(i) for i in ir))
    opt_ir, stats = optimize(ir)
    if args.opt:
        print("\n".join(str(i) for i in opt_ir))
        print(f"# {len(ir)} -> {len(opt_ir)} instructions; {stats}")

    if args.no_run:
        return 0
    try:
        out = run_ir(ir if args.no_opt else opt_ir)
    except (ZeroDivisionError, TimeoutError, RuntimeError) as exc:
        print(f"runtime error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
