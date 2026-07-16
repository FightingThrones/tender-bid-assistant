#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招投标范文解析器：Word(.docx) / PDF(.pdf) -> 统一结构化 JSON
将买来的标书范文"拆骨"成可入库的知识片段。

用法:
  python parse_bid_doc.py <file.docx|file.pdf> [--out out.json]
  python parse_bid_doc.py <folder> [--out out_dir]      # 批量解析整个目录

输出 JSON 结构:
{
  "source": "路径",
  "doc_type": "docx|pdf",
  "title": "文档标题",
  "sections": [
    {"heading": "章节标题", "level": 1, "text": "正文...", "tables": [[...]]}
  ],
  "raw_text": "全文纯文本"
}
"""
import sys, os, json, argparse


def _ensure_deps():
    try:
        import docx  # noqa
    except ImportError:
        sys.exit("缺少 python-docx，请先安装: pip install python-docx")
    try:
        import pdfplumber  # noqa
    except ImportError:
        sys.exit("缺少 pdfplumber，请先安装: pip install pdfplumber")


def parse_docx(path):
    import docx
    from docx.document import Document
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(path)
    sections = []
    cur = None

    def new_section(heading, level):
        s = {"heading": heading, "level": level, "text": "", "tables": []}
        sections.append(s)
        return s

    body = d.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            p = Paragraph(child, d)
            txt = (p.text or "").strip()
            if not txt:
                continue
            style = (p.style.name if p.style else "") or ""
            if style.startswith("Heading") or style.startswith("标题") or style.startswith("TOC") is False and _looks_heading(txt):
                # 结构化标题
                lvl = 1
                try:
                    num = "".join(ch for ch in style if ch.isdigit())
                    if num:
                        lvl = int(num)
                except Exception:
                    lvl = 1
                if not (style.startswith("Heading") or style.startswith("标题")):
                    lvl = 2  # 启发式判断的标题给低一级
                cur = new_section(txt, lvl)
            else:
                if cur is None:
                    cur = new_section("(前言)", 0)
                cur["text"] += txt + "\n"
        elif isinstance(child, CT_Tbl):
            t = Table(child, d)
            tbl = [[c.text.strip() for c in row.cells] for row in t.rows]
            if cur is None:
                cur = new_section("(表格)", 0)
            cur["tables"].append(tbl)

    title = d.core_properties.title or (sections[0]["heading"] if sections else os.path.basename(path))
    return title, sections


def parse_pdf(path):
    import pdfplumber

    sections = []
    raw_parts = []

    def new_section(heading, level):
        s = {"heading": heading, "level": level, "text": "", "tables": []}
        sections.append(s)
        return s

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            raw_parts.append(txt)
            for line in txt.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if _looks_heading(line):
                    if not sections:
                        new_section("(正文)", 0)
                    sections.append({"heading": line, "level": 2, "text": "", "tables": []})
                else:
                    if not sections:
                        new_section("(正文)", 0)
                    sections[-1]["text"] += line + "\n"
            for t in (page.extract_tables() or []):
                if not sections:
                    new_section("(表格)", 0)
                sections[-1]["tables"].append(t)

    title = os.path.basename(path)
    return title, sections, "\n".join(raw_parts)


def _looks_heading(line):
    """启发式：判断一行是否像章节标题（用于无样式信息的 PDF）。"""
    if len(line) > 40:
        return False
    s = line.strip()
    # 数字编号：1. 1.1 一、1、1.1.2
    if (s[0].isdigit() and ("." in s[:5] or "、" in s[:5] or "．" in s[:5])):
        return True
    if s[0] in "一二三四五六七八九十" and ("、" in s[:3] or "．" in s[:3] or "." in s[:3]):
        return True
    # 常见标书章节后缀
    if s.endswith(("方案", "计划", "措施", "说明", "承诺", "保障", "标准", "大纲", "摘要")):
        return True
    # 全中文且无标点、较短，可能是标题
    if len(s) <= 18 and all("\u4e00" <= c <= "\u9fff" for c in s) and "，" not in s:
        return True
    return False


def parse_one(path, out_path=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        title, sections = parse_docx(path)
        raw = "\n".join(s["text"] for s in sections)
        doc_type = "docx"
    elif ext == ".pdf":
        title, sections, raw = parse_pdf(path)
        doc_type = "pdf"
    else:
        raise ValueError("不支持的格式: " + ext)
    result = {
        "source": path,
        "doc_type": doc_type,
        "title": title,
        "sections": sections,
        "raw_text": raw,
    }
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main():
    _ensure_deps()
    ap = argparse.ArgumentParser(description="招投标范文解析器 docx/pdf -> JSON")
    ap.add_argument("path", help="单个文件或目录")
    ap.add_argument("--out", help="输出 JSON 路径；目录批量时作为输出目录")
    args = ap.parse_args()

    if os.path.isdir(args.path):
        out_dir = args.out or os.path.join(args.path, "_parsed")
        os.makedirs(out_dir, exist_ok=True)
        count = 0
        for fn in sorted(os.listdir(args.path)):
            if fn.lower().endswith((".docx", ".pdf")):
                src = os.path.join(args.path, fn)
                dst = os.path.join(out_dir, os.path.splitext(fn)[0] + ".json")
                parse_one(src, dst)
                count += 1
                print("parsed:", fn)
        print(f"\n完成：{count} 个文件 -> {out_dir}")
    else:
        res = parse_one(args.path, args.out)
        if args.out:
            print("wrote", args.out)
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
