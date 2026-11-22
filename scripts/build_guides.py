"""Build printable, offline help pages from the two canonical Markdown guides."""

import html
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend/public/assets"
PAGES = {
    "EVALUATOR_GUIDE_ELI5.md": (
        "evaluator-guide.html",
        "Evaluator guide",
        "Simple explanations. Real evidence.",
    ),
    "RUN_SERVER.md": (
        "run-server.html",
        "Run the server",
        "Start, stop and troubleshoot your local workspace.",
    ),
}


def inline(value):
    value = html.escape(value)

    def link(match):
        label, url = match.groups()
        url = PAGES.get(url, (url,))[0]
        return f'<a href="{url}">{label}</a>'

    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", link, value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)


def render(source):
    lines = source.splitlines()
    output = []
    toc = []
    i = 0
    code_count = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            language = line[3:]
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            code_count += 1
            output.append(
                f'<div class="code-block"><div class="code-heading"><span>{html.escape(language or "COMMAND")}</span><button type="button" data-copy="code-{code_count}">Copy command</button></div><pre><code id="code-{code_count}">{html.escape(chr(10).join(code))}</code></pre></div>'
            )
            i += 1
            continue
        heading = re.match(r"^(#{1,3}) (.+)$", line)
        if heading:
            level = len(heading[1])
            title = heading[2]
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            output.append(f'<h{level} id="{slug}">{inline(title)}</h{level}>')
            if level == 2:
                toc.append((slug, title))
            i += 1
            continue
        if line.startswith("|"):
            table = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [cell.strip() for cell in lines[i].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    table.append(cells)
                i += 1
            output.append(
                '<div class="table-scroll"><table><thead><tr>'
                + "".join("<th>" + inline(c) + "</th>" for c in table[0])
                + "</tr></thead><tbody>"
            )
            for row in table[1:]:
                output.append(
                    "<tr>"
                    + "".join("<td>" + inline(c) + "</td>" for c in row)
                    + "</tr>"
                )
            output.append("</tbody></table></div>")
            continue
        if line.startswith("> "):
            quote = []
            while i < len(lines) and lines[i].startswith("> "):
                quote.append(lines[i][2:])
                i += 1
            output.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
            continue
        ordered = bool(re.match(r"^\d+\. ", line))
        if ordered or line.startswith("- "):
            tag = "ol" if ordered else "ul"
            output.append("<" + tag + ">")
            while i < len(lines) and (
                bool(re.match(r"^\d+\. ", lines[i]))
                if ordered
                else lines[i].startswith("- ")
            ):
                output.append(
                    "<li>" + inline(re.sub(r"^(?:\d+\.|-) ", "", lines[i])) + "</li>"
                )
                i += 1
            output.append("</" + tag + ">")
            continue
        paragraph = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^(?:#|```|\||> |\d+\. |- )", lines[i])
        ):
            paragraph.append(lines[i])
            i += 1
        output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(output), toc


CSS = """*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:#f3f6f8;color:#1b2a3b;font:16px/1.75 "Segoe UI",Arial,sans-serif}a{color:#086479}header{background:#0a1726;color:#ecf7fc;padding:38px max(24px,calc((100vw - 1200px)/2));border-bottom:4px solid #50d9e8}header small{letter-spacing:2px;color:#80c7d5}header h1{margin:8px 0;font-size:38px;line-height:1.2}header p{color:#b1c7d4}header nav{display:flex;gap:20px;flex-wrap:wrap}header a{color:#90e7ee}button{font:inherit;cursor:pointer;border:1px solid #66818d;background:transparent;color:inherit;border-radius:5px;padding:5px 13px}.layout{display:grid;grid-template-columns:245px minmax(0,1fr);gap:40px;max-width:1200px;margin:36px auto;padding:0 24px}aside{align-self:start;position:sticky;top:20px;max-height:90vh;overflow:auto;font-size:12px}aside a{display:block;padding:6px 0;text-decoration:none;color:#466074}article{background:white;padding:38px 48px;border:1px solid #dae4eb;border-radius:10px;min-width:0}article>h1{font-size:30px;line-height:1.25}h2{font-size:24px;line-height:1.4;padding-top:22px;margin-top:34px;border-top:1px solid #dce6ed}h3{font-size:19px;margin-top:28px}p{margin:15px 0}li{margin:9px 0}strong{color:#122f45}blockquote{margin:24px 0;padding:20px 24px;background:#e9f6fa;border-left:4px solid #168da0;border-radius:4px}code{font:13px/1.7 Consolas,monospace;background:#edf2f5;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}.code-block{margin:22px 0;border:1px solid #cbdbe4;border-radius:7px;overflow:hidden}.code-heading{display:flex;justify-content:space-between;align-items:center;background:#e7eff4;padding:7px 14px;font-size:11px;letter-spacing:.7px}.code-heading button{font-size:11px}pre{margin:0;padding:20px;background:#101d2d;color:#e3f5fc;white-space:pre-wrap;overflow-wrap:anywhere}pre code{padding:0;background:none;color:inherit;font-size:12px}.table-scroll{overflow:auto;margin:22px 0}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:12px 14px;text-align:left;vertical-align:top;border-bottom:1px solid #d7e3eb}th{background:#eaf1f6;color:#24455f}footer{max-width:1200px;margin:30px auto;padding:20px 24px;color:#60798a;font-size:12px}a:focus-visible,button:focus-visible{outline:3px solid #12a5bf;outline-offset:3px}#copy-status{font-size:12px} @media(max-width:850px){.layout{grid-template-columns:1fr;gap:16px;margin:20px auto}aside{position:static;max-height:180px;border:1px solid #d2e0e8;padding:14px}article{padding:22px}header h1{font-size:29px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{header{background:white;color:black;padding:0;border-bottom:1px solid #333}header small,header p{color:#333}header nav,aside,.code-heading button,#copy-status,footer{display:none}.layout{display:block;margin:0;padding:0}article{border:0;padding:0}body{background:white;font-size:10pt;line-height:1.5}h2{break-after:avoid}table{font-size:9pt}tr,blockquote,.code-block{break-inside:avoid}pre{background:#f3f3f3;color:black}a{color:inherit;text-decoration:none}h1{font-size:22pt}h2{font-size:15pt}}"""
SCRIPT = """document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(document.getElementById(button.dataset.copy).textContent);document.getElementById('copy-status').textContent='Command copied. Paste it into PowerShell.';button.textContent='Copied';}catch{document.getElementById('copy-status').textContent='Select the command text and copy it manually.'}}));"""


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for source, (filename, title, subtitle) in PAGES.items():
        content, toc = render((ROOT / "docs" / source).read_text(encoding="utf-8"))
        navigation = "".join(
            f'<a href="#{slug}">{html.escape(label)}</a>' for slug, label in toc
        )
        page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Neural Cartographer</title><style>{CSS}</style></head><body><header><small>NEURAL CARTOGRAPHER / PROJECT HANDBOOK</small><h1>{title}</h1><p>{subtitle}</p><nav><a href="/">Open the website</a><a href="evaluator-guide.html">Evaluator guide</a><a href="run-server.html">Server instructions</a><button type="button" onclick="window.print()">Print / save as PDF</button></nav></header><div class="layout"><aside aria-label="On this page"><strong>ON THIS PAGE</strong>{navigation}</aside><article>{content}<p id="copy-status" role="status" aria-live="polite"></p></article></div><footer>Local project documentation · 2 November 2026 · Canonical Markdown: docs/{source}. Frozen model results are reported as measured.</footer><script>{SCRIPT}</script></body></html>'
        (OUTPUT / filename).write_text(page, encoding="utf-8")
        print("Built", filename)


if __name__ == "__main__":
    main()
