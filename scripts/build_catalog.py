#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标书库目录构建器（批量 + 可断点续跑）。
遍历本地私有标书库（默认 private_bid_docs/，不随仓库发布），对每份 .doc/.docx/.pdf：
  - 抽取标题、章节标题列表、全文长度、前 600 字快照（用于后续匹配）
  - 以一级目录名作为行业标签（去掉 "12." 这类数字前缀）
输出（data/ 下）：
  - catalog.jsonl        一行一文件，可断点续跑（崩了重跑会自动跳过已处理）
  - catalog.json         汇总索引（构建完成后生成，gen_bid 读取它）
  - catalog_report.md    人类可读的库概览（各行业计数 + 样例）
用法:
  python build_catalog.py [--root "./private_bid_docs"] [--out-dir ../data] [--force]
"""
import os, sys, json, argparse, subprocess, re

DEFAULT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "private_bid_docs"))
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "data",
    "catalog",
    "output",
    "outputs",
    "output_real",
    "output_verify",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "envs",
}


def _decode(bs):
    try:
        t = bs.decode("utf-8")
    except Exception:
        t = bs.decode("gb18030", errors="replace")
    if t.count("\ufffd") > max(5, len(t) // 20):
        try:
            t = bs.decode("gb18030", errors="replace")
        except Exception:
            pass
    return t


def extract_doc(path):
    try:
        out = subprocess.run(["antiword", path], capture_output=True, timeout=60).stdout
    except Exception:
        return None, [], ""
    text = _decode(out)
    return None, _headings(text), text


def extract_docx(path):
    import docx
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        d = docx.Document(path)
    except Exception:
        return None, [], ""
    title = d.core_properties.title
    lines = []
    headings = []
    body = d.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            p = Paragraph(child, d)
            txt = (p.text or "").strip()
            if not txt:
                continue
            style = (p.style.name if p.style else "") or ""
            if style.startswith("Heading") or style.startswith("标题"):
                headings.append(txt)
            lines.append(txt)
        elif isinstance(child, CT_Tbl):
            t = Table(child, d)
            for row in t.rows:
                lines.append(" | ".join(c.text.strip() for c in row.cells))
    text = "\n".join(lines)
    return title, headings, text


def extract_pdf(path):
    import pdfplumber
    headings = []
    parts = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                parts.append(txt)
                for line in txt.split("\n"):
                    line = line.strip()
                    if line and _looks_heading(line):
                        headings.append(line)
    except Exception:
        return None, [], ""
    return None, headings, "\n".join(parts)


def _looks_heading(line):
    if len(line) > 40:
        return False
    s = line.strip()
    if s and s[0].isdigit() and ("." in s[:5] or "、" in s[:5] or "．" in s[:5]):
        return True
    if s and s[0] in "一二三四五六七八九十" and ("、" in s[:3] or "．" in s[:3] or "." in s[:3]):
        return True
    if s.endswith(("方案", "计划", "措施", "说明", "承诺", "保障", "标准", "大纲", "摘要", "部分")):
        return True
    if len(s) <= 18 and all("\u4e00" <= c <= "\u9fff" for c in s) and "，" not in s:
        return True
    return False


def _headings(text):
    hs = []
    for line in text.split("\n"):
        line = line.strip()
        if line and _looks_heading(line) and line not in hs:
            hs.append(line)
    return hs


def industry_of(rel_path):
    top = rel_path.split(os.sep)[0]
    m = re.match(r"^\d+[.\s、]*", top)
    if m:
        top = top[m.end():]
    return top or "未分类"


def scenario_of(rel_path):
    parts = rel_path.split(os.sep)
    # 一级目录=行业，二级目录（若有）=场景
    if len(parts) >= 2:
        s = parts[1]
        return re.sub(r"^\d+[.\s、]*", "", s).strip()
    return ""


def best_title(headings, filename):
    for h in headings:
        if 4 <= len(h) <= 30:
            return h
    return os.path.splitext(filename)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--force", action="store_true", help="忽略断点，全量重建")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    jsonl_path = os.path.join(args.out_dir, "catalog.jsonl")
    ckpt_path = os.path.join(args.out_dir, ".ckpt.json")

    done = set()
    if not args.force and os.path.exists(ckpt_path):
        try:
            with open(ckpt_path, "r", encoding="utf-8") as f:
                done = set(json.load(f).get("done", []))
            print(f"[resume] 已有 {len(done)} 个文件处理记录，跳过")
        except Exception:
            done = set()

    # 统计已写入 jsonl 的条目（断点续跑时保留）
    entries_existing = {}
    if not args.force and os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    entries_existing[e["rel"]] = e
                except Exception:
                    pass
        print(f"[resume] 已索引 {len(entries_existing)} 条")

    ext_count = {}
    ind_count = {}
    skipped = 0
    processed = 0
    new_count = 0

    # 决定是覆盖还是追加写 jsonl
    mode = "w" if args.force else "a"
    # 续跑时只保留已存在条目，追加新的
    with open(jsonl_path, mode, encoding="utf-8") as jf:
        # 续跑：先确保已存在的条目还在文件里（a 模式会保留，w 会清空由 entries_existing 重写）
        if args.force:
            entries_existing = {}

        for dirpath, dirnames, files in os.walk(args.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in files:
                low = fn.lower()
                if low.endswith(".downloading") or fn.startswith("~$"):
                    continue
                if not low.endswith((".doc", ".docx", ".pdf")):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, args.root)
                if rel in done and rel in entries_existing:
                    continue  # 已处理且有效，跳过
                ext = "doc" if low.endswith(".doc") else ("docx" if low.endswith(".docx") else "pdf")
                ext_count[ext] = ext_count.get(ext, 0) + 1
                try:
                    if ext == "doc":
                        title, hs, text = extract_doc(full)
                    elif ext == "docx":
                        title, hs, text = extract_docx(full)
                    else:
                        title, hs, text = extract_pdf(full)
                except Exception:
                    skipped += 1
                    done.add(rel)
                    continue
                if not text or len(text) < 30:
                    skipped += 1
                    done.add(rel)
                    continue
                ind = industry_of(rel)
                ind_count[ind] = ind_count.get(ind, 0) + 1
                e = {
                    "rel": rel,
                    "ext": ext,
                    "industry": ind,
                    "scenario": scenario_of(rel),
                    "title": title or best_title(hs, fn),
                    "headings": hs[:40],
                    "chars": len(text),
                    "snippet": text[:600].replace("\n", " ").strip(),
                }
                jf.write(json.dumps(e, ensure_ascii=False) + "\n")
                jf.flush()
                entries_existing[rel] = e
                done.add(rel)
                processed += 1
                new_count += 1
                if processed % 50 == 0:
                    # 定期写断点
                    with open(ckpt_path, "w", encoding="utf-8") as cf:
                        json.dump({"done": list(done)}, cf)
                    print(f"[progress] 新增 {new_count} | 累计索引 {len(entries_existing)} | 跳过 {skipped}")

    # 收尾：写断点 + 汇总
    with open(ckpt_path, "w", encoding="utf-8") as cf:
        json.dump({"done": list(done)}, cf)
    all_entries = list(entries_existing.values())
    catalog_path = os.path.join(args.out_dir, "catalog.json")
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump({"count": len(all_entries), "entries": all_entries}, f, ensure_ascii=False)
    print(f"catalog.json: {len(all_entries)} 条 | 本轮新增 {new_count} | 跳过 {skipped} | 扩展名 {ext_count}")

    # 人类可读报告
    by_ind = {}
    for e in all_entries:
        by_ind.setdefault(e["industry"], []).append(e)
    report = ["# 标书模板库概览", "", f"> 共 {len(all_entries)} 份可解析模板（来自 {args.root}）", ""]
    for ind, lst in sorted(by_ind.items(), key=lambda kv: -len(kv[1])):
        report.append(f"## {ind}（{len(lst)} 份）")
        for e in lst[:6]:
            report.append(f"- {e['title']}  `{e['rel']}`")
        if len(lst) > 6:
            report.append(f"- …（其余 {len(lst)-6} 份）")
        report.append("")
    with open(os.path.join(args.out_dir, "catalog_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("wrote", catalog_path, "and catalog_report.md")


if __name__ == "__main__":
    main()
