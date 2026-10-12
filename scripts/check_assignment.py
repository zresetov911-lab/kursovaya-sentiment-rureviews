# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from docx import Document

sys.stdout.reconfigure(encoding="utf-8")
doc = Document(Path(__file__).resolve().parents[1] / "report" / "Kursovaya_Reshetov_Sentiment_Analysis.docx")
started = False
for p in doc.paragraphs:
    t = p.text.strip()
    if "Утверждаю" in t or t == "ЗАДАНИЕ":
        started = True
    if not started:
        continue
    shown = t if t else "(пусто)"
    print(f"[{p.style.name}] {shown[:180]}")
    if t == "Аннотация":
        break
