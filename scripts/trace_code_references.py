#!/usr/bin/env python3
"""
scripts/trace_code_references.py
================================
파이프라인 소스코드(AST & 정적 분석) 자동 추적기.

수동으로 작성된 리스트가 아니라, 메인 실행 파일부터 시작하여
실제 코드 AST(Abstract Syntax Tree) 및 호출/참조를 재귀적으로 분석하여:
1. 어떤 모듈을 import하는지
2. 어떤 함수/스크립트를 실행(subprocess, call)하는지
3. 어떤 문서/데이터 파일(YAML, MD, JSON, CSV 등)을 open/load 하는지
4. 어떤 결과 파일을 write/save 하는지
코드에 실제로 적힌 파일 경로와 참조 관계를 100% 자동 추출하여 계층 트리로 출력합니다.
"""

import os
import sys
import ast
import re
from typing import Dict, List, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CodeReferenceExtractor(ast.NodeVisitor):
    """Python AST를 순회하며 import, 파일 open, os.path.join, subprocess 호출을 추출."""

    def __init__(self, filepath: str, base_dir: str):
        self.filepath = filepath
        self.base_dir = base_dir
        self.imports = set()          # 로컬 프로젝트 import 대상
        self.external_imports = set() # 표준 라이브러리 / 서드파티
        self.file_reads = set()       # 읽는 파일/패턴
        self.file_writes = set()      # 쓰는 파일/패턴
        self.subprocesses = set()     # subprocess로 실행하는 스크립트
        self.string_literals = set()  # 코드 내 등장하는 확장자 보유 파일/폴더 문자열

    def visit_Import(self, node):
        for alias in node.names:
            self._categorize_import(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self._categorize_import(node.module)
        self.generic_visit(node)

    def _categorize_import(self, mod_name: str):
        parts = mod_name.split(".")
        # 로컬 프로젝트 내부 모듈 여부 판별
        possible_paths = [
            os.path.join(self.base_dir, *parts) + ".py",
            os.path.join(self.base_dir, *parts, "__init__.py"),
            os.path.join(self.base_dir, "content-system", *parts) + ".py",
            os.path.join(self.base_dir, "content-system", "scripts", *parts) + ".py",
            os.path.join(os.path.dirname(self.filepath), *parts) + ".py"
        ]
        found_local = None
        for p in possible_paths:
            if os.path.exists(p):
                found_local = os.path.relpath(p, self.base_dir).replace("\\", "/")
                break

        if found_local:
            self.imports.add(found_local)
        else:
            self.external_imports.add(mod_name)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            val = node.value.strip()
            # 파일 확장자 또는 주요 시스템 경로 패턴 검출
            if re.search(r'\.(yaml|yml|json|md|html|csv|txt|py)$', val, re.IGNORECASE) or any(k in val for k in ["content-system", "01_keyword", "02_writer", "03_sources", "04_qa", "05_publish"]):
                if not val.startswith("http") and not "\n" in val:
                    self.string_literals.add(val)
        self.generic_visit(node)

    def visit_Call(self, node):
        # 1. open(...) 호출 분석
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # open(file, mode)
        if func_name == "open" and node.args:
            mode = "r"
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value

            target_expr = self._stringify_expr(node.args[0])
            if "w" in mode or "a" in mode:
                self.file_writes.add(f"{target_expr} (mode='{mode}')")
            else:
                self.file_reads.add(f"{target_expr} (mode='{mode}')")

        # 2. subprocess.run([sys.executable, script, ...])
        if func_name in ("run", "Popen", "call") and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, (ast.List, ast.Tuple)):
                for elt in first_arg.elts:
                    s_val = self._stringify_expr(elt)
                    if ".py" in s_val:
                        self.subprocesses.add(s_val)

        # 3. shutil.copyfile / copy
        if func_name in ("copyfile", "copy") and len(node.args) >= 2:
            src = self._stringify_expr(node.args[0])
            dst = self._stringify_expr(node.args[1])
            self.file_reads.add(f"{src} (copy source)")
            self.file_writes.add(f"{dst} (copy dest)")

        self.generic_visit(node)

    def _stringify_expr(self, node) -> str:
        """AST 표현식을 대략적인 읽기 쉬운 문자열로 변환."""
        if isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._stringify_expr(node.value)}.{node.attr}"
        elif isinstance(node, ast.JoinedStr):  # f-string
            parts = []
            for part in node.values:
                if isinstance(part, ast.Constant):
                    parts.append(str(part.value))
                elif isinstance(part, ast.FormattedValue):
                    parts.append(f"{{{self._stringify_expr(part.value)}}}")
            return "".join(parts)
        elif isinstance(node, ast.Call):
            # os.path.join(...)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "join":
                sub_args = [self._stringify_expr(a) for a in node.args]
                return "/".join(sub_args)
            func_repr = self._stringify_expr(node.func)
            args_repr = ", ".join(self._stringify_expr(a) for a in node.args[:2])
            return f"{func_repr}({args_repr})"
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return f"{self._stringify_expr(node.left)} + {self._stringify_expr(node.right)}"
        return "<expr>"


def extract_regex_paths_from_file(filepath: str) -> Dict[str, Set[str]]:
    """AST 외에 정규식으로 os.path.join, 변수 정의, 파일 읽기/쓰기를 교차 추출."""
    reads = set()
    writes = set()
    referenced_files = set()

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return {"reads": reads, "writes": writes, "referenced_files": referenced_files}

    for line in lines:
        stripped = line.strip()

        # with open(...) as ...
        m_open = re.search(r'open\s*\(\s*([^,\)]+)(?:,\s*["\']([rwa\+b]+)["\'])?', stripped)
        if m_open:
            path_arg = m_open.group(1).strip()
            mode = m_open.group(2) or "r"
            if "w" in mode or "a" in mode:
                writes.add(f"{path_arg} (mode={mode})")
            else:
                reads.add(f"{path_arg} (mode={mode})")

        # yaml.safe_load, json.load
        if "yaml.safe_load" in stripped or "json.load" in stripped:
            m_load = re.search(r'(?:yaml\.safe_load|json\.load)\s*\(\s*([^\)]+)\)', stripped)
            if m_load:
                reads.add(f"데이터 역직렬화({m_load.group(1).strip()})")

        # yaml.safe_dump, json.dump
        if "yaml.safe_dump" in stripped or "json.dump" in stripped:
            m_dump = re.search(r'(?:yaml\.safe_dump|json\.dump)\s*\(\s*([^,]+),\s*([^\)]+)\)', stripped)
            if m_dump:
                writes.add(f"데이터 직렬화 저장({m_dump.group(2).strip()})")

        # 문자열로 하드코딩/정의된 파일 경로
        m_paths = re.findall(r'["\']([^"\']+\.(?:yaml|yml|json|md|html|csv|txt|py))["\']', stripped)
        for p in m_paths:
            if not p.startswith("http"):
                referenced_files.add(p)

    return {"reads": reads, "writes": writes, "referenced_files": referenced_files}


def analyze_file_recursively(start_file_rel: str, visited: Set[str] = None) -> Dict:
    if visited is None:
        visited = set()

    abs_path = os.path.join(BASE_DIR, start_file_rel)
    if not os.path.exists(abs_path):
        return None

    norm_rel = os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
    if norm_rel in visited:
        return {"file": norm_rel, "already_visited": True}
    visited.add(norm_rel)

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
            line_count = len(code.splitlines())
            size_bytes = len(code.encode("utf-8"))
        tree = ast.parse(code, filename=abs_path)
    except Exception as e:
        return {"file": norm_rel, "error": str(e)}

    extractor = CodeReferenceExtractor(abs_path, BASE_DIR)
    extractor.visit(tree)

    regex_info = extract_regex_paths_from_file(abs_path)

    # 병합
    combined_reads = extractor.file_reads.union(regex_info["reads"])
    combined_writes = extractor.file_writes.union(regex_info["writes"])
    combined_literals = extractor.string_literals.union(regex_info["referenced_files"])

    # 로컬 import 재귀 분석
    child_modules = {}
    for imp in extractor.imports:
        child_res = analyze_file_recursively(imp, visited)
        if child_res:
            child_modules[imp] = child_res

    # subprocess 스크립트 재귀 분석
    for sub in extractor.subprocesses:
        # sub가 경로 또는 변수일 수 있음
        clean_sub = sub.strip("\"' ")
        if clean_sub.endswith(".py"):
            possible = [
                clean_sub,
                os.path.join("content-system", "scripts", os.path.basename(clean_sub)),
                os.path.join("scripts", os.path.basename(clean_sub))
            ]
            for p in possible:
                p_abs = os.path.join(BASE_DIR, p)
                if os.path.exists(p_abs):
                    p_rel = os.path.relpath(p_abs, BASE_DIR).replace("\\", "/")
                    child_res = analyze_file_recursively(p_rel, visited)
                    if child_res:
                        child_modules[f"subprocess:{p_rel}"] = child_res
                    break

    return {
        "file": norm_rel,
        "line_count": line_count,
        "size_bytes": size_bytes,
        "imports": sorted(list(extractor.imports)),
        "external_imports": sorted(list(extractor.external_imports)),
        "file_reads": sorted(list(combined_reads)),
        "file_writes": sorted(list(combined_writes)),
        "subprocesses": sorted(list(extractor.subprocesses)),
        "referenced_file_literals": sorted(list(combined_literals)),
        "children": child_modules
    }


def print_tree(analysis: Dict, depth: int = 0):
    indent = "  " * depth
    if not analysis:
        return

    fn = analysis.get("file", "")
    lines = analysis.get("line_count", 0)
    size = analysis.get("size_bytes", 0)

    if analysis.get("already_visited"):
        print(f"{indent}└── 🔁 [기방문 모듈] {fn}")
        return

    prefix = "📦 [MAIN ENTRY]" if depth == 0 else "├── 📄 [호출/참조 모듈]"
    print(f"\n{indent}{prefix} {fn} ({lines}줄, {size:,} 바이트)")

    # 1. 파일 읽기/오픈
    if analysis.get("file_reads"):
        print(f"{indent}    📖 [읽는 파일/데이터 open()]:")
        for r in analysis["file_reads"]:
            print(f"{indent}       - {r}")

    # 2. 파일 쓰기/저장
    if analysis.get("file_writes"):
        print(f"{indent}    ✍️ [쓰는 파일/결과물 open()]:")
        for w in analysis["file_writes"]:
            print(f"{indent}       - {w}")

    # 3. 코드 내 참조된 파일명/문서
    if analysis.get("referenced_file_literals"):
        print(f"{indent}    🔗 [코드 내 문자열로 참조된 파일/문서]:")
        for ref in analysis["referenced_file_literals"]:
            # 로컬 파일 존재 여부 체크
            check_p = os.path.join(BASE_DIR, ref)
            exists_mark = "✓존재" if os.path.exists(check_p) else "⚡동적/상대경로"
            print(f"{indent}       - {ref} [{exists_mark}]")

    # 4. 외부/표준 라이브러리
    if depth == 0 and analysis.get("external_imports"):
        print(f"{indent}    ⚙️ [외부 라이브러리 및 표준 모듈]: {', '.join(analysis['external_imports'][:10])}")

    # 5. 서브 모듈 / 자식 파일 재귀 출력
    children = analysis.get("children", {})
    if children:
        print(f"{indent}    ⬇️ [하위 모듈/스크립트 연쇄 호출 ({len(children)}개)]:")
        for c_key, c_val in children.items():
            print_tree(c_val, depth + 2)


def main():
    print("=" * 80)
    print("  [파이프라인 전체 소스코드 AST 정적 의존성 및 파일 참조 자동 추적]")
    print("=" * 80)

    # 1. 파이프라인 메인 엔트리 파일
    entry_point = "services/gemini_writer.py"
    if len(sys.argv) > 1:
        entry_point = sys.argv[1].replace("\\", "/")

    print(f">> 시작 메인 파일: {entry_point}")
    analysis = analyze_file_recursively(entry_point)

    if not analysis:
        print(f"Error: {entry_point} not found!")
        sys.exit(1)

    print_tree(analysis)

    print("\n" + "=" * 80)
    print("  [추적 완료: 코드 내 모든 import, open(), subprocess, 파일 리터럴 전수 분석됨]")
    print("=" * 80)


if __name__ == "__main__":
    main()
