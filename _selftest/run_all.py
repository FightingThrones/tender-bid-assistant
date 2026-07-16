#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自测运行器：生成样例 -> 临时构建 catalog -> 生成 Markdown/Word 初稿。"""
import os, sys, subprocess
BASE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.dirname(BASE)
sys.path.insert(0, os.path.join(SK, "scripts"))

# 1. 造样例
import make_sample  # 运行即生成 sample.docx / tender.txt / company.yaml / kb

out_dir = os.path.join(BASE, "output")
catalog_dir = os.path.join(BASE, "catalog")
build_cmd = [
    sys.executable,
    os.path.join(SK, "scripts", "build_catalog.py"),
    "--root", BASE,
    "--out-dir", catalog_dir,
    "--force",
]
print("[构建索引]", " ".join(build_cmd))
subprocess.run(build_cmd, check=True)

cmd = [
    sys.executable,
    os.path.join(SK, "scripts", "gen_bid.py"),
    "--tender", os.path.join(BASE, "tender_it.txt"),
    "--company", os.path.join(BASE, "company_it.yaml"),
    "--root", BASE,
    "--catalog", os.path.join(catalog_dir, "catalog.json"),
    "--out", out_dir,
    "--top", "3",
    "--docx",
]
print("[生成]", " ".join(cmd))
subprocess.run(cmd, check=True)

md_path = os.path.join(out_dir, "标书初稿.md")
print("\n===== 生成的标书初稿.md 前 1200 字 =====\n")
with open(md_path, encoding="utf-8") as f:
    print(f.read()[:1200])
