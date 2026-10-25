#!/usr/bin/env python3
"""
scripts/extract_code_prompts.py
===============================
파이프라인 코드 내 프롬프트 및 가이드라인 텍스트 전수 추출기.

파이프라인 관련 모든 파이썬 파일에서:
- print()나 log()용 단순 콘솔 출력 제외
- 프롬프트 전달용, 시스템 인스트럭션, 작성 가이드라인, 템플릿 등
- 40자 이상의 한글 문자열 리터럴을 파일명/라인번호/변수명과 함께 전수 추출하여 출력합니다.
"""

import os
import sys
import ast
import re

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PIPELINE_FILES = [
    "services/gemini_writer.py",
    "services/content_ops_api.py",
    "services/ask_logitech_ai.py",
    "services/device_blog_registry.py",
    "services/naver_blog_compiler.py",
    "content-system/scripts/verify_blog_with_logitech_ai.py",
    "content-system/scripts/evaluate_editorial_quality.py",
    "content-system/scripts/validate_claim_evidence.py",
    "content-system/scripts/extract_claims.py",
    "content-system/scripts/export_naver_blog_html.py",
    "content-system/scripts/build_writing_strategy.py",
    "content-system/scripts/build_writer_context.py"
]


class PromptStringFinder(ast.NodeVisitor):
    def __init__(self, filepath, source_code):
        self.filepath = filepath
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.current_function = "<module>"
        self.current_assign_target = ""
        self.results = []
        self.ignored_node_ids = set()

    def visit_FunctionDef(self, node):
        old_fn = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_fn

    def visit_AsyncFunctionDef(self, node):
        old_fn = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_fn

    def visit_Assign(self, node):
        targets = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                targets.append(t.id)
            elif isinstance(t, ast.Attribute):
                targets.append(t.attr)
        self.current_assign_target = ", ".join(targets) if targets else "<target>"
        self.generic_visit(node)
        self.current_assign_target = ""

    def visit_Call(self, node):
        # print(...) 또는 log(...) 호출인 경우 해당 인자 노드들을 제외 대상으로 등록
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("print", "log", "debug", "info", "warning", "warn", "error", "critical"):
            for arg in node.args:
                self._mark_ignored(arg)
            for kw in node.keywords:
                self._mark_ignored(kw.value)

        self.generic_visit(node)

    def _mark_ignored(self, node):
        self.ignored_node_ids.add(id(node))
        for child in ast.walk(node):
            self.ignored_node_ids.add(id(child))

    def visit_Constant(self, node):
        if id(node) in self.ignored_node_ids:
            return

        if isinstance(node.value, str):
            val = node.value.strip()
            # 한글 포함 여부 및 40자 이상 체크
            korean_chars = re.findall(r'[가-힣]', val)
            if len(val) >= 40 and len(korean_chars) >= 10:
                # docstring 제외 (함수나 모듈 첫 번째 노드인 경우)
                line_no = getattr(node, 'lineno', -1)
                self.results.append({
                    "line": line_no,
                    "function": self.current_function,
                    "target": self.current_assign_target or "(표현식/리턴값)",
                    "length": len(val),
                    "text": val
                })
        self.generic_visit(node)

    def visit_JoinedStr(self, node):
        if id(node) in self.ignored_node_ids:
            return

        # f-string 전체 텍스트 근사치 조합
        parts = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            else:
                parts.append("{...}")
        combined = "".join(parts).strip()
        korean_chars = re.findall(r'[가-힣]', combined)

        if len(combined) >= 40 and len(korean_chars) >= 10:
            line_no = getattr(node, 'lineno', -1)
            self.results.append({
                "line": line_no,
                "function": self.current_function,
                "target": self.current_assign_target or "(f-string 표현식)",
                "length": len(combined),
                "text": combined
            })
            # 자식 Constant 중복 수집 방지
            self._mark_ignored(node)

        self.generic_visit(node)


def scan_file_prompts(rel_path: str):
    abs_path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
        tree = ast.parse(src, filename=abs_path)
    except Exception as e:
        return [{"line": 0, "function": "PARSE_ERROR", "target": "-", "length": 0, "text": f"Error: {e}"}]

    finder = PromptStringFinder(abs_path, src)
    finder.visit(tree)
    return finder.results


def main():
    print("=" * 80)
    print("  [파이프라인 코드 내 가이드라인 / 프롬프트용 40자 이상 한글 텍스트 전수 추출]")
    print("=" * 80)

    total_prompts = 0

    for rel_file in PIPELINE_FILES:
        results = scan_file_prompts(rel_file)
        if not results:
            continue

        print(f"\n" + "-" * 80)
        print(f"📁 파일: {rel_file} (발견: {len(results)}건)")
        print("-" * 80)

        for idx, item in enumerate(results, 1):
            total_prompts += 1
            print(f"\n  [{idx}] 라인: {item['line']} | 위치: {item['function']} | 대상: {item['target']} ({item['length']}자)")
            # 너무 긴 텍스트는 보기 좋게 표시
            cleaned_text = item['text'].replace('\r', '')
            text_lines = cleaned_text.split('\n')
            if len(text_lines) > 8:
                preview = '\n'.join('      ' + l for l in text_lines[:6])
                print(preview)
                print(f"      ... [총 {len(text_lines)}줄 중 나머지 생략] ...")
                print('      ' + text_lines[-1])
            else:
                for l in text_lines:
                    print(f"      {l}")

    print("\n" + "=" * 80)
    print(f"  [전수 추출 완료: 총 {len(PIPELINE_FILES)}개 파이프라인 파일 중 {total_prompts}건의 프롬프트/가이드라인 텍스트 추출됨]")
    print("=" * 80)


if __name__ == "__main__":
    main()
