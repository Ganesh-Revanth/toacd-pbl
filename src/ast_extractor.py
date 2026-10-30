import os
import re
import subprocess


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
NODE_RE = re.compile(r"^(?:[|` -]*)?([A-Za-z_][A-Za-z0-9_]*)(?:\s+(.*))?$")
ADDRESS_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")

# clang prints a source location as "file:line:col", and then only what changed since the
# previous location it printed: "line:N:C" when the line changed, "col:C" when it did not.
_LOC_TOKEN = (
    r"(?:(?P<file>[^\s<>,:]+\.(?:cpp|cc|cxx|c\+\+|c|h|hpp|hh|hxx)):(?P<fl>\d+):\d+"
    r"|line:(?P<l>\d+):\d+|col:\d+)"
)
LOC_RE = re.compile(_LOC_TOKEN)
RANGE_RE = re.compile(r"^\s*<[^<>]*(?:<[^<>]*>[^<>]*)*>")          # the "<start, end>" part
OWN_LOC_RE = re.compile(r"^\s*" + _LOC_TOKEN)                      # the node's own location

MAX_TREE_DEPTH = 9
MAX_DETAIL_LENGTH = 220

VISIBLE_NODES = {
    "TranslationUnitDecl",
    "NamespaceDecl",
    "UsingDecl",
    "UsingDirectiveDecl",
    "TypedefDecl",
    "TypeAliasDecl",
    "CXXRecordDecl",
    "ClassTemplateDecl",
    "FunctionTemplateDecl",
    "FunctionDecl",
    "CXXMethodDecl",
    "CXXConstructorDecl",
    "CXXDestructorDecl",
    "FieldDecl",
    "VarDecl",
    "ParmVarDecl",
    "EnumDecl",
    "EnumConstantDecl",
    "CompoundStmt",
    "DeclStmt",
    "IfStmt",
    "ForStmt",
    "CXXForRangeStmt",
    "WhileStmt",
    "DoStmt",
    "SwitchStmt",
    "CaseStmt",
    "DefaultStmt",
    "ReturnStmt",
    "BreakStmt",
    "ContinueStmt",
    "BinaryOperator",
    "CompoundAssignOperator",
    "UnaryOperator",
    "ConditionalOperator",
    "CallExpr",
    "CXXOperatorCallExpr",
    "CXXMemberCallExpr",
    "CXXConstructExpr",
    "CXXNewExpr",
    "CXXDeleteExpr",
    "ArraySubscriptExpr",
    "MemberExpr",
    "DeclRefExpr",
    "RecoveryExpr",
    "IntegerLiteral",
    "FloatingLiteral",
    "CharacterLiteral",
    "StringLiteral",
    "CXXBoolLiteralExpr",
    "CXXNullPtrLiteralExpr",
}


def _ast_depth(line):
    marker = re.search(r"(?:\|-|`-)", line)
    if not marker:
        return 0
    return marker.start() // 2 + 1


def _node_parts(line):
    stripped = line.lstrip(" |`-")
    match = NODE_RE.match(stripped)
    if not match:
        return None, ""
    return match.group(1), match.group(2) or ""


def _is_user_location(line, file_path):
    filename = os.path.basename(file_path)
    absolute = os.path.abspath(file_path)
    return f"<{filename}:" in line or f"<{absolute}:" in line or f", {filename}:" in line


def _has_explicit_external_location(line, file_path):
    if _is_user_location(line, file_path):
        return False
    return bool(re.search(r"</|, /|<[A-Za-z]:", line))


def _has_relative_location(line):
    return "<line:" in line or "<col:" in line


def _trim_details(details):
    details = ADDRESS_RE.sub("", details)
    details = " ".join(details.split())
    if len(details) > MAX_DETAIL_LENGTH:
        details = details[: MAX_DETAIL_LENGTH - 3].rstrip() + "..."
    return details


def extract_ast(file_path):
    """Return a compact clang AST dump containing only user-file subtrees."""
    cmd = [
        "clang++",
        "-Xclang",
        "-ast-dump",
        "-fsyntax-only",
        "-fno-color-diagnostics",
        file_path,
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except OSError:
        return None

    filtered = []
    active_depth = None
    user_file_context = False

    try:
        for raw_line in process.stdout:
            line = ANSI_RE.sub("", raw_line.rstrip("\n"))
            if not line.strip():
                continue

            depth = _ast_depth(line)
            if active_depth is not None and depth <= active_depth:
                active_depth = None

            if _has_explicit_external_location(line, file_path):
                user_file_context = False

            if _is_user_location(line, file_path):
                user_file_context = True

            starts_user_subtree = _is_user_location(line, file_path) or (
                user_file_context and _has_relative_location(line)
            )

            if active_depth is None and starts_user_subtree:
                active_depth = depth

            if active_depth is not None:
                filtered.append(line)
    finally:
        process.wait()

    return "\n".join(filtered) if filtered else None


def _split_location(details):
    """Split raw clang details into (range_text, own_location_match, rest)."""
    clean = ADDRESS_RE.sub("", details, count=1)           # the node's own address comes first
    rng = RANGE_RE.match(clean)
    range_text = rng.group(0) if rng else ""
    after = clean[len(range_text):]
    own = OWN_LOC_RE.match(after)
    rest = after[own.end():] if own else after
    return range_text, own, rest


def _advance(match, current_line):
    if match.group("file"):
        return int(match.group("fl"))
    if match.group("l"):
        return int(match.group("l"))
    return current_line


def parse_ast_to_tree(ast_text, file_path=None):
    """Turn a (filtered) clang dump into nested dicts.

    Each node has: type, details (as before), label (details without locations),
    line / end_line (best effort, from clang's relative location printing) and children.
    """
    if not ast_text:
        return []

    root_nodes = []
    stack = []
    current_line = None        # line of the most recent location clang printed

    for line in ast_text.splitlines():
        if not line.strip():
            continue

        depth = _ast_depth(line)
        node_type, details = _node_parts(line)
        if not node_type:
            continue

        # Locations are relative to the previous one, so every line must be followed,
        # including nodes we later decide not to show.
        range_text, own, rest = _split_location(details)
        start_line = end_line = None
        for index, match in enumerate(LOC_RE.finditer(range_text)):
            current_line = _advance(match, current_line)
            if index == 0:
                start_line = current_line
            end_line = current_line
        if own:
            current_line = _advance(own, current_line)
            if start_line is None:
                start_line = end_line = current_line

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if depth > MAX_TREE_DEPTH or node_type not in VISIBLE_NODES:
            continue

        node = {
            "type": node_type,
            "details": _trim_details(details),
            "label": _trim_details(rest),
            "line": start_line,
            "end_line": end_line if end_line is not None else start_line,
            "children": [],
        }

        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root_nodes.append(node)

        stack.append((depth, node))

    return root_nodes


def extract_node_near_line(ast_text, line_number):
    if not ast_text or line_number is None:
        return None

    fallback = None

    for line in ast_text.splitlines():
        node_type, _ = _node_parts(line)
        if not node_type or node_type not in VISIBLE_NODES:
            continue

        if f":{line_number}:" in line or f"line:{line_number}" in line:
            if "Expr" in node_type or "Stmt" in node_type or "Decl" in node_type:
                return node_type
            fallback = fallback or node_type

    return fallback
