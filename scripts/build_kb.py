#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把解析后的标书范文 JSON 整理进知识库。
用法:
  python build_kb.py --parsed parsed/xxx.json --industry 软件开发 --scenario 政府采购 [--auto]

--auto 会尝试从 sections 自动抽取章节大纲与范文片段，资质/评分留占位待人工补。
不加 --auto 则仅生成骨架，全部字段留待人工填充。
"""
import os, sys, json, argparse, yaml


def load_parsed(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def auto_extract(parsed):
    sections = parsed.get("sections", [])
    outline = []
    snippets = {}
    for s in sections:
        h = s.get("heading", "")
        if h in ("(前言)", "(正文)", "(表格)"):
            continue
        outline.append(h)
        body = (s.get("text", "") or "").strip()
        if body:
            snippets[h] = body[:2000]  # 截断，避免过长
    return outline, snippets


def build(industry, scenario, parsed, auto):
    rec = {
        "industry": industry,
        "scenario": scenario,
        "applicable": "",
        "qualifications": [],
        "scoring": {"price": None, "technical": None, "commercial": None},
        "sections": [],
        "snippets": {},
        "deductions": [],
        "source_title": parsed.get("title", ""),
    }
    if auto:
        outline, snippets = auto_extract(parsed)
        rec["sections"] = [{"id": str(i + 1), "title": t, "outline": []} for i, t in enumerate(outline)]
        rec["snippets"] = snippets
    else:
        rec["sections"] = [{"id": "commercial", "title": "商务标", "outline": []},
                           {"id": "technical", "title": "技术标", "outline": []},
                           {"id": "quote", "title": "报价文件", "outline": []}]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--industry", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--kb", default=os.path.join(os.path.dirname(__file__), "..", "knowledge"))
    args = ap.parse_args()

    parsed = load_parsed(args.parsed)
    rec = build(args.industry, args.scenario, parsed, args.auto)

    kb_dir = os.path.join(args.kb, args.industry)
    os.makedirs(kb_dir, exist_ok=True)
    # 文件名用场景，避免重名
    fname = args.scenario + ".yaml"
    out = os.path.join(kb_dir, fname)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(rec, f, sort_keys=False, allow_unicode=True)
    print("wrote", out)
    if not args.auto:
        print("提示：已生成骨架，请人工补全 qualifications/scoring/snippets/deductions。")


if __name__ == "__main__":
    main()
