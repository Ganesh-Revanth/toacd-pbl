"""
Control flow graph (CFG) extractor for C and C++ programs.

Compiles source code to LLVM IR using clang/clang++ (-S -emit-llvm -O0 -fno-discard-value-names -g)
and parses the resulting basic blocks, terminators, and branch targets into structured CFG models.
Does not use regex heuristics on source code.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

from languages.base import NotSupported


COMPILE_TIMEOUT_S = 30.0


def is_clang_available() -> bool:
    """Return True if clang++ or clang is found in PATH or environment."""
    return bool(shutil.which("clang++") or shutil.which("clang"))


def get_clang_cmd(language: str = "cpp") -> Tuple[str, List[str]]:
    """Return compiler binary and base arguments for language ('c' or 'cpp')."""
    lang = (language or "cpp").lower().strip()
    if lang == "c":
        clang_cmd = shutil.which("clang") or shutil.which("clang++")
        if not clang_cmd:
            raise NotSupported("clang was not found. Install clang to use the C/C++ control flow graph.")
        args = ["-std=c11"]
        if "clang++" in os.path.basename(clang_cmd).lower():
            args.extend(["-x", "c"])
        return clang_cmd, args

    clang_cmd = shutil.which("clang++") or shutil.which("clang")
    if not clang_cmd:
        raise NotSupported("clang++ was not found. Install clang to use the C/C++ control flow graph.")
    args = ["-std=c++17"]
    if "clang++" not in os.path.basename(clang_cmd).lower():
        args.extend(["-x", "c++"])
    return clang_cmd, args


def _get_friendly(label: str, is_entry: bool, term_inst: str, insts: List[str]) -> str:
    """Provide a user-friendly name for a basic block based on its LLVM label and instructions."""
    lbl = label.lower()
    term = term_inst.lower()
    if is_entry:
        return "entry"
    if "lpad" in lbl or "catch" in lbl:
        return "exception handler"
    if "ehcleanup" in lbl or "cleanup" in lbl:
        return "exception cleanup"
    if "eh.resume" in lbl or "terminate" in lbl:
        return "rethrow"
    if "invoke.cont" in lbl:
        return "after call"
    if "if.then" in lbl or "then" in lbl:
        return "then branch"
    if "if.else" in lbl or "else" in lbl:
        return "else branch"
    if "if.end" in lbl:
        return "after if"
    if "for.cond" in lbl or "while.cond" in lbl or "do.cond" in lbl or "cond" in lbl:
        return "loop condition"
    if "for.body" in lbl or "while.body" in lbl or "do.body" in lbl:
        return "loop body"
    if "for.inc" in lbl or "inc" in lbl:
        return "loop increment"
    if "for.end" in lbl or "while.end" in lbl or "do.end" in lbl:
        return "after loop"
    if "sw.bb" in lbl or "case" in lbl:
        return "switch case"
    if "sw.default" in lbl or "default" in lbl:
        return "switch default"
    if "sw.epilog" in lbl:
        return "after switch"
    if term.startswith("ret") or lbl == "return" or "return" in lbl:
        return "return"
    if "dead" in lbl or "unreachable" in lbl:
        return "unreachable block"
    return f"block {label}"


def extract_cfg_from_ll(ll_text: str, src_filename: str = "main.cpp") -> List[Dict[str, Any]]:
    """
    Parse LLVM IR assembly text and extract CFG for every function defined in the user's file.
    Filters out STL/template instantiations and external headers using clang -g debug metadata.
    """
    # 1. Parse DIFile debug mappings (!12 = !DIFile(filename: "...", directory: "..."))
    di_files: Dict[str, str] = {}
    for m in re.finditer(r'!(\d+)\s*=\s*!DIFile\((.*?)\)', ll_text):
        fn_m = re.search(r'filename:\s*"([^"]+)"', m.group(2))
        if fn_m:
            di_files[m.group(1)] = fn_m.group(1)

    # 2. Parse DISubprograms (!45 = distinct !DISubprogram(name: "...", file: !12, line: 10, ...))
    di_subs: Dict[str, Dict[str, Any]] = {}
    for m in re.finditer(r'!(\d+)\s*=\s*(?:distinct\s*)?!DISubprogram\((.*?)\)', ll_text, re.DOTALL):
        sub_id = m.group(1)
        content = m.group(2)
        name_m = re.search(r'\bname:\s*"([^"]+)"', content)
        file_m = re.search(r'\bfile:\s*!(\d+)', content)
        line_m = re.search(r'\bline:\s*(\d+)', content)
        fn_name = name_m.group(1) if name_m else ""
        file_id = file_m.group(1) if file_m else None
        line_no = int(line_m.group(1)) if line_m else 0
        file_path = di_files.get(file_id, "") if file_id else ""
        di_subs[sub_id] = {"name": fn_name, "file": file_path, "line": line_no}

    # DILocation ids -> source line, used to tell which source lines each block covers
    di_locs: Dict[str, int] = {}
    for m in re.finditer(r'!(\d+)\s*=\s*(?:distinct\s*)?!DILocation\(line:\s*(\d+)', ll_text):
        di_locs[m.group(1)] = int(m.group(2))

    def _block_source_lines(raw_lines: List[str]) -> List[int]:
        # A plain `br label` is only glue back to the join point and is often tagged with the
        # closing brace or `else` line, so it is ignored when the block has real statements.
        found: Set[int] = set()
        glue: Set[int] = set()
        for ln in raw_lines:
            if ln.startswith("#dbg"):
                ids = re.findall(r'!(\d+)\)\s*$', ln)
            else:
                ids = re.findall(r'!dbg\s*!(\d+)', ln)
            target = glue if re.match(r'^br\s+label\b', ln) else found
            for i in ids:
                n = di_locs.get(i, 0)
                if n > 0:
                    target.add(n)
        return sorted(found or glue)

    src_base = os.path.basename(src_filename)

    # 3. Match top-level function definitions: define ... @name(...) ... {
    fn_def_re = re.compile(
        r'^define\s+[^{]+?@([a-zA-Z0-9_.]+)\s*\(.*?\)[^{]*?\{',
        re.MULTILINE
    )

    functions: List[Dict[str, Any]] = []

    for match in fn_def_re.finditer(ll_text):
        linkage_name = match.group(1)
        header_text = match.group(0)
        dbg_m = re.search(r'!dbg\s*!(\d+)', header_text)
        dbg_id = dbg_m.group(1) if dbg_m else None

        # Exclude clang internal glue functions
        if linkage_name.startswith("__cxx_global_var_init") or linkage_name.startswith("_GLOBAL__sub_I"):
            continue

        # Check whether this function is located in the user's source file
        fn_info = di_subs.get(dbg_id, {})
        file_path = fn_info.get("file", "").replace("\\", "/")
        is_user_file = False
        if file_path:
            is_user_file = file_path.endswith("/" + src_base) or file_path == src_base
        elif not dbg_id and linkage_name == "main":
            is_user_file = True

        if not is_user_file:
            continue

        display_name = fn_info.get("name") or linkage_name
        line_no = fn_info.get("line") or 1

        # Extract function body between matching outer braces
        start = match.end()
        depth = 1
        i = start
        while i < len(ll_text) and depth > 0:
            c = ll_text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        fn_body = ll_text[start:i - 1]

        # Parse basic blocks in fn_body
        raw_blocks: List[Tuple[str, List[str]]] = []
        curr_label: Optional[str] = None
        curr_lines: List[str] = []

        for line in fn_body.splitlines():
            sline = line.strip()
            if not sline:
                continue
            lbl_m = re.match(r'^([a-zA-Z0-9_.]+):\s*(?:;.*)?$', sline)
            if lbl_m:
                if curr_label is not None:
                    raw_blocks.append((curr_label, curr_lines))
                curr_label = lbl_m.group(1)
                curr_lines = []
            else:
                if curr_label is None:
                    curr_label = "entry"
                curr_lines.append(sline)

        if curr_label is not None:
            raw_blocks.append((curr_label, curr_lines))

        if not raw_blocks:
            continue

        # Build blocks and edges
        blocks: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_edges: Set[Tuple[str, str, str]] = set()

        for idx, (lbl, lines) in enumerate(raw_blocks):
            clean_insts = [
                ln for ln in lines
                if not ln.startswith(";")
                and not ln.startswith("#dbg")
                and not ln.startswith("!dbg")
                and not ln.startswith("call void @llvm.dbg")
            ]
            block_text = "\n".join(clean_insts)
            term_str = clean_insts[-1] if clean_insts else ""

            b_edges: List[Dict[str, Any]] = []
            is_exit = False

            # 1. Switch statement (may span multiple lines in LLVM IR)
            m_switch = re.search(r'\bswitch\s+[^,]+,\s*label\s+%([a-zA-Z0-9_.]+)\s*\[(.*?)\]', block_text, re.DOTALL)
            if m_switch:
                def_lbl = m_switch.group(1)
                b_edges.append({"from": lbl, "to": def_lbl, "kind": "switch"})
                cases_str = m_switch.group(2)
                for m_case in re.finditer(r'label\s+%([a-zA-Z0-9_.]+)', cases_str):
                    b_edges.append({"from": lbl, "to": m_case.group(1), "kind": "switch"})
            else:
                # 2. Conditional branch
                # `invoke` ends the block with: to label %normal unwind label %handler
                m_inv = re.search(r'\bto\s+label\s+%([a-zA-Z0-9_.]+)\s+unwind\s+label\s+%([a-zA-Z0-9_.]+)', term_str)
                if m_inv:
                    # C++ call that may throw: a normal path and an exception path
                    b_edges.append({"from": lbl, "to": m_inv.group(1), "kind": "jump"})
                    b_edges.append({"from": lbl, "to": m_inv.group(2), "kind": "unwind"})
                    m_cond = None
                else:
                    m_cond = re.search(r'\bbr\s+i1\s+[^,]+,\s*label\s+%([a-zA-Z0-9_.]+),\s*label\s+%([a-zA-Z0-9_.]+)', term_str)
                if m_cond:
                    b_edges.append({"from": lbl, "to": m_cond.group(1), "kind": "true"})
                    b_edges.append({"from": lbl, "to": m_cond.group(2), "kind": "false"})
                elif not m_inv:
                    # 3. Unconditional jump
                    m_uncond = re.search(r'\bbr\s+label\s+%([a-zA-Z0-9_.]+)', term_str)
                    if m_uncond:
                        b_edges.append({"from": lbl, "to": m_uncond.group(1), "kind": "jump"})
                    elif re.search(r'\b(ret|unreachable|resume)\b', term_str):
                        is_exit = True

            if not b_edges and not is_exit and re.search(r'\b(ret|unreachable|resume)\b', term_str):
                is_exit = True

            for e in b_edges:
                key = (e["from"], e["to"], e["kind"])
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append(e)

            is_entry = (idx == 0)
            friendly = _get_friendly(lbl, is_entry, term_str, clean_insts)

            blocks.append({
                "id": lbl,
                "label": f"%{lbl}" if not lbl.startswith("%") else lbl,
                "friendly": friendly,
                "instructions": clean_insts[:8],
                "is_entry": is_entry,
                "is_exit": is_exit,
                "reachable": True,
                "lines": _block_source_lines(lines),
            })

        # Adjacency map for traversal
        adj: Dict[str, List[str]] = {b["id"]: [] for b in blocks}
        for e in edges:
            if e["from"] in adj:
                adj[e["from"]].append(e["to"])

        # BFS Reachability from entry
        entry_id = blocks[0]["id"]
        reachable_set: Set[str] = set()
        queue = [entry_id]
        reachable_set.add(entry_id)

        while queue:
            curr = queue.pop(0)
            for nxt in adj.get(curr, []):
                if nxt not in reachable_set:
                    reachable_set.add(nxt)
                    queue.append(nxt)

        unreachable_ids: List[str] = []
        for b in blocks:
            b["reachable"] = (b["id"] in reachable_set)
            if not b["reachable"]:
                unreachable_ids.append(b["id"])

        # Back-edge (loop) detection via DFS from entry
        visited: Set[str] = set()
        on_stack: Set[str] = set()
        back_edges = 0

        def dfs(u: str) -> None:
            nonlocal back_edges
            visited.add(u)
            on_stack.add(u)
            for v in adj.get(u, []):
                if v in on_stack:
                    back_edges += 1
                elif v not in visited:
                    dfs(v)
            on_stack.remove(u)

        if entry_id in adj:
            dfs(entry_id)
        for b in blocks:
            if b["id"] in reachable_set and b["id"] not in visited:
                dfs(b["id"])

        num_b = len(blocks)
        num_e = len(edges)
        # Cyclomatic complexity follows normal control flow only: exception
        # (unwind) edges and the blocks only they reach are left out.
        normal_adj: Dict[str, List[str]] = {b["id"]: [] for b in blocks}
        for e in edges:
            if e["kind"] != "unwind" and e["from"] in normal_adj:
                normal_adj[e["from"]].append(e["to"])
        normal_set = {entry_id}
        stack = [entry_id]
        while stack:
            cur = stack.pop()
            for nxt in normal_adj.get(cur, []):
                if nxt not in normal_set:
                    normal_set.add(nxt)
                    stack.append(nxt)
        n_norm = len(normal_set)
        e_norm = sum(1 for e in edges if e["kind"] != "unwind" and e["from"] in normal_set)
        cyclomatic = max(1, e_norm - n_norm + 2)

        functions.append({
            "function": display_name,
            "linkage_name": linkage_name,
            "line": line_no,
            "blocks": blocks,
            "edges": edges,
            "metrics": {
                "blocks": num_b,
                "edges": num_e,
                "cyclomatic": cyclomatic,
                "loops": back_edges,
            },
            "unreachable": unreachable_ids,
        })

    return functions


def extract_cfg(code: str, language: str = "cpp", function: Optional[str] = None, timeout: float = COMPILE_TIMEOUT_S) -> Dict[str, Any]:
    """
    Compile source code using clang with -S -emit-llvm -O0 -fno-discard-value-names -g,
    and return the parsed CFG.

    Raises:
        NotSupported: If language is not C/C++ or clang is missing.
        ValueError: If security check blocks the code or input is invalid.
        RuntimeError: If clang compilation fails.
    """
    lang_id = (language or "cpp").lower().strip()
    if lang_id not in ("cpp", "c"):
        raise NotSupported("Control flow graphs are available for C and C++")

    if not is_clang_available():
        target_name = "C++" if lang_id == "cpp" else "C"
        raise NotSupported(f"clang++ was not found. Install clang to use the {target_name} control flow graph.")

    # Re-use language security check
    from languages import get_language
    lang_obj = get_language(lang_id)
    if lang_obj:
        safe, reason = lang_obj.is_safe(code)
        if not safe:
            raise ValueError(f"Security Error: {reason}")

    compiler_cmd, base_args = get_clang_cmd(lang_id)
    ext = ".c" if lang_id == "c" else ".cpp"

    with tempfile.TemporaryDirectory(prefix="webui_cfg_") as wd:
        src_file = os.path.join(wd, f"main{ext}")
        ll_file = os.path.join(wd, "main.ll")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = [
            compiler_cmd,
            *base_args,
            "-S",
            "-emit-llvm",
            "-O0",
            "-fno-discard-value-names",
            "-g",
            src_file,
            "-o",
            ll_file,
        ]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=wd,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"CFG compilation timed out after {timeout}s.")
        except OSError as e:
            raise NotSupported(f"Failed to execute {compiler_cmd}: {e}")

        if res.returncode != 0:
            err_msg = res.stderr.strip() or "Clang compilation failed."
            raise RuntimeError(f"Clang compilation failed:\n{err_msg}")

        if not os.path.isfile(ll_file):
            raise RuntimeError("LLVM IR file was not generated.")

        with open(ll_file, "r", encoding="utf-8", errors="replace") as f:
            ll_text = f.read()

        functions = extract_cfg_from_ll(ll_text, src_filename=f"main{ext}")

        if not functions:
            return {
                "function": "none",
                "blocks": [],
                "edges": [],
                "metrics": {"blocks": 0, "edges": 0, "cyclomatic": 1, "loops": 0},
                "unreachable": [],
                "functions": [],
            }

        selected_fn = None
        if function:
            selected_fn = next((f for f in functions if f["function"] == function or f["linkage_name"] == function), None)
        if not selected_fn:
            selected_fn = next((f for f in functions if f["function"] == "main"), functions[0])

        return {
            "function": selected_fn["function"],
            "blocks": selected_fn["blocks"],
            "edges": selected_fn["edges"],
            "metrics": selected_fn["metrics"],
            "unreachable": selected_fn["unreachable"],
            "functions": functions,
        }
