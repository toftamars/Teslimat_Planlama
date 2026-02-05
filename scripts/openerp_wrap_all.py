#!/usr/bin/env python3
"""Tüm data XML'lerde kökü openerp yapıp içeriği data ile sarar (sunucu RelaxNG uyumu)."""
import os
import re

BASE = os.path.join(os.path.dirname(__file__), "..", "teslimat_planlama")

def process(path: str, noupdate: str = "1") -> None:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Zaten openerp + data varsa atla
    if "<openerp>" in content and "<data " in content:
        return
    # odoo -> openerp
    content = content.replace("<odoo>", "<openerp>").replace("</odoo>", "</openerp>")
    # openerp altında data yoksa ekle
    if "<data " not in content or content.strip().startswith("<?xml"):
        # openerp sonrası ilk satırdan sonra <data> ekle, </openerp> öncesine </data> ekle
        lines = content.split("\n")
        out = []
        in_openerp = False
        data_added = False
        for i, line in enumerate(lines):
            out.append(line)
            if line.strip() == "<openerp>":
                in_openerp = True
            elif in_openerp and not data_added and line.strip() and "<openerp>" not in line:
                # openerp'ten sonra ilk içerik satırından önce data ekle
                indent = "    " if line.startswith("    ") else ""
                out.insert(-1, indent + "<data noupdate=\"" + noupdate + "\">")
                data_added = True
            elif data_added and line.strip() == "</openerp>":
                # </openerp> öncesine </data> ekle
                out.insert(-1, "    </data>")
        content = "\n".join(out)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK", path)

def main():
    for root, _dirs, files in os.walk(BASE):
        for name in files:
            if not name.endswith(".xml"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, BASE)
            noupdate = "0" if "security" in rel or "program_kurulum" in rel else "1"
            process(path, noupdate)

if __name__ == "__main__":
    main()
