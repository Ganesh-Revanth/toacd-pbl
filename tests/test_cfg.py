"""
Unit tests for the C and C++ Control Flow Graph (CFG) extractor and /api/cfg endpoint.
Skips compiler tests when clang is not installed.
"""

import pytest
import shutil
from unittest.mock import patch

from cfg_extractor import extract_cfg, is_clang_available
from languages.base import NotSupported
from web.server import api_cfg, ApiError


CLANG_AVAILABLE = is_clang_available()
skip_no_clang = pytest.mark.skipif(not CLANG_AVAILABLE, reason="clang/clang++ is not installed")


@skip_no_clang
def test_if_else_cyclomatic_complexity():
    """An if/else statement must yield cyclomatic complexity = 2."""
    code = """
    int test_if(int x) {
        if (x > 0) {
            return 1;
        } else {
            return 2;
        }
    }
    """
    cfg = extract_cfg(code, language="c")
    assert cfg["function"] == "test_if"
    assert cfg["metrics"]["cyclomatic"] == 2
    assert cfg["metrics"]["blocks"] >= 3
    assert cfg["metrics"]["edges"] >= 3
    # Check true and false branch edges exist
    kinds = [e["kind"] for e in cfg["edges"]]
    assert "true" in kinds
    assert "false" in kinds


@skip_no_clang
def test_for_loop_gives_one_loop():
    """A for loop must yield exactly 1 loop (back edge)."""
    code = """
    int test_for() {
        int sum = 0;
        for (int i = 0; i < 10; ++i) {
            sum += i;
        }
        return sum;
    }
    """
    cfg = extract_cfg(code, language="c")
    assert cfg["function"] == "test_for"
    assert cfg["metrics"]["loops"] == 1
    # Check that there is a loop condition block
    friendlies = [b["friendly"] for b in cfg["blocks"]]
    assert any("loop" in f for f in friendlies)


@skip_no_clang
def test_code_after_return_is_unreachable():
    """Code following an unconditional return must be detected as unreachable."""
    code = """
    int test_dead(int a) {
        if (a) return 1;
        return 0;
    dead:
        return 2;
    }
    """
    cfg = extract_cfg(code, language="c")
    assert "dead" in cfg["unreachable"]
    dead_block = next((b for b in cfg["blocks"] if b["id"] == "dead"), None)
    assert dead_block is not None
    assert dead_block["reachable"] is False


@skip_no_clang
def test_switch_with_three_cases():
    """A switch statement with 3 cases must produce proper switch branches and edges."""
    code = """
    int test_switch(int x) {
        switch (x) {
            case 1: return 10;
            case 2: return 20;
            case 3: return 30;
            default: return 0;
        }
    }
    """
    cfg = extract_cfg(code, language="c")
    assert cfg["function"] == "test_switch"
    switch_edges = [e for e in cfg["edges"] if e["kind"] == "switch"]
    # 3 cases + 1 default = 4 switch edges
    assert len(switch_edges) >= 4
    friendlies = [b["friendly"] for b in cfg["blocks"]]
    assert any("switch" in f for f in friendlies)


@skip_no_clang
def test_stl_only_gives_no_user_functions_besides_main():
    """A program including heavy STL headers must filter them out and only return user functions (main)."""
    code = """
    #include <iostream>
    #include <vector>
    #include <algorithm>

    int main() {
        std::vector<int> nums = {3, 1, 4};
        std::sort(nums.begin(), nums.end());
        std::cout << nums[0] << std::endl;
        return 0;
    }
    """
    cfg = extract_cfg(code, language="cpp")
    fn_names = [f["function"] for f in cfg["functions"]]
    assert fn_names == ["main"]
    assert cfg["function"] == "main"


def test_language_not_supported():
    """Requesting CFG for Python or Java must raise NotSupported."""
    with pytest.raises(NotSupported, match="Control flow graphs are available for C and C++"):
        extract_cfg("def foo(): pass", language="python")

    with pytest.raises(NotSupported, match="Control flow graphs are available for C and C++"):
        extract_cfg("class Main {}", language="java")


def test_missing_clang_raises_not_supported():
    """When clang is not installed, NotSupported must be raised."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(NotSupported, match="clang.*was not found"):
            extract_cfg("int main() { return 0; }", language="cpp")


def test_security_check_blocks_dangerous_code():
    """Code with prohibited commands must be rejected by the security check."""
    dangerous = '#include <stdlib.h>\nint main() { system("rm -rf /"); return 0; }'
    with pytest.raises(ValueError, match="Security Error"):
        extract_cfg(dangerous, language="c")


@skip_no_clang
def test_api_cfg_endpoint():
    """The /api/cfg endpoint must return HTTP 200 and standard CFG structure."""
    body = {
        "code": "int main() { if (1 > 0) return 1; return 0; }",
        "language": "c",
    }
    resp = api_cfg(body)
    assert "function" in resp
    assert "blocks" in resp
    assert "edges" in resp
    assert "metrics" in resp
    assert "unreachable" in resp
    assert "functions" in resp


def test_api_cfg_invalid_language():
    """The /api/cfg endpoint must return 503 ApiError for unsupported languages."""
    with pytest.raises(ApiError) as exc_info:
        api_cfg({"code": "print(1)", "language": "python"})
    assert exc_info.value.status == 503
    assert "Control flow graphs are available for C and C++" in str(exc_info.value)


@skip_no_clang
def test_cpp_exception_paths_are_not_reported_unreachable():
    """C++ calls compile to `invoke`; their landing pads must be reachable, not dead code."""
    code = """
    #include <iostream>
    #include <string>
    int main() {
        std::string s = "hi";
        for (int i = 0; i < 3; i++) { std::cout << s << i << "\\n"; }
        return 0;
    }
    """
    cfg = extract_cfg(code, language="cpp")
    fn = next(f for f in cfg["functions"] if f["function"] == "main")
    assert fn["unreachable"] == []
    assert any(e["kind"] == "unwind" for e in fn["edges"])
    # exception edges must not inflate cyclomatic complexity (one loop => 2)
    assert fn["metrics"]["cyclomatic"] == 2


@skip_no_clang
def test_blocks_report_their_source_lines():
    """Each block lists the source lines it covers, so the UI can highlight them."""
    code = (
        "int f(int n) {\n"          # 1
        "    int s = 0;\n"          # 2
        "    if (n > 0) {\n"        # 3
        "        s = 1;\n"          # 4
        "    } else {\n"            # 5
        "        s = 2;\n"          # 6
        "    }\n"                   # 7
        "    return s;\n"           # 8
        "}\n"
    )
    cfg = extract_cfg(code, language="c")
    by_id = {b["id"]: b for b in cfg["blocks"]}
    assert 3 in by_id["entry"]["lines"]
    assert by_id["if.then"]["lines"] == [4]
    assert by_id["if.else"]["lines"] == [6]
