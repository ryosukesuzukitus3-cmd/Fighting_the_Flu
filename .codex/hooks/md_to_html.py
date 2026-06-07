"""Claude Code PostToolUse hook: dialog → optional HTML render of .md.

Two modes:
1. Hook mode (no args, reads stdin):
   - Receives PostToolUse JSON
   - Filters .md files in project / plans / memory
   - Spawns a Windows dialog asking the user to choose:
       [プレーン] [ファンシー] [スキップ]
   - On Plain/Fancy, the dialog launches this same script in CLI mode.
2. CLI mode (--file <path> --mode plain|fancy):
   - plain: Notion-style template + TOC (no API call, no token consumption)
   - fancy: Claude API generates SVG-enhanced HTML (consumes tokens)
   - Opens the resulting HTML in the default browser
"""
from __future__ import annotations
import sys
import os
import json
import re
import html as html_lib
import subprocess
import argparse
import datetime
from pathlib import Path

HOOK_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = HOOK_DIR.parent.parent
OUTPUT_DIR  = PROJECT_DIR / ".html"
TEMPLATE    = HOOK_DIR / "template.html"

# ── モデル設定（新モデル追加時はここだけ更新） ──────────────────────────────
FANCY_MODELS = {
    "light":  "claude-haiku-4-5-20251001",
    "medium": "claude-sonnet-4-6",
    "heavy":  "claude-opus-4-8",
}


# ── ENTRY ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--file", default=None)
    parser.add_argument("--mode", choices=["plain", "fancy"], default="plain")
    args, _ = parser.parse_known_args()

    if args.file:
        cli_render(Path(args.file), args.mode)
    else:
        hook_handler()


# ── HOOK MODE ────────────────────────────────────────────────────────────────

def hook_handler() -> None:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        return

    if data.get("tool_name", "") not in ("Write", "Edit", "MultiEdit"):
        return

    tool_input = data.get("tool_input", {}) or {}
    file_path = (tool_input.get("file_path")
                 or tool_input.get("path")
                 or tool_input.get("notebook_path", ""))
    if not file_path or not file_path.lower().endswith(".md"):
        return

    src = Path(file_path).resolve()
    if not src.exists():
        return

    if determine_output(src) is None:
        return

    show_choice_dialog(src)


def show_choice_dialog(src: Path) -> None:
    """Spawn a non-blocking PowerShell dialog with 3 buttons."""
    script_path = str(Path(__file__).resolve())
    py_exe = sys.executable or "python"

    ps = r'''
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Claude Code — HTML レビュー版'
$form.Size = New-Object System.Drawing.Size(460, 220)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.Font = New-Object System.Drawing.Font('Yu Gothic UI', 9)
$form.BackColor = [System.Drawing.Color]::White

$labelTitle = New-Object System.Windows.Forms.Label
$labelTitle.Text = $env:MD_NAME
$labelTitle.Location = New-Object System.Drawing.Point(24, 24)
$labelTitle.Size = New-Object System.Drawing.Size(400, 24)
$labelTitle.Font = New-Object System.Drawing.Font('Yu Gothic UI', 11, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($labelTitle)

$labelMsg = New-Object System.Windows.Forms.Label
$labelMsg.Text = 'この markdown を HTML レビュー版で出力しますか？'
$labelMsg.Location = New-Object System.Drawing.Point(24, 56)
$labelMsg.Size = New-Object System.Drawing.Size(400, 22)
$labelMsg.ForeColor = [System.Drawing.Color]::FromArgb(80,80,80)
$form.Controls.Add($labelMsg)

$labelPath = New-Object System.Windows.Forms.Label
$labelPath.Text = $env:MD_PATH
$labelPath.Location = New-Object System.Drawing.Point(24, 80)
$labelPath.Size = New-Object System.Drawing.Size(400, 22)
$labelPath.ForeColor = [System.Drawing.Color]::FromArgb(140,140,140)
$labelPath.Font = New-Object System.Drawing.Font('Consolas', 8)
$form.Controls.Add($labelPath)

$btnPlain = New-Object System.Windows.Forms.Button
$btnPlain.Text = 'プレーン'
$btnPlain.Location = New-Object System.Drawing.Point(24, 124)
$btnPlain.Size = New-Object System.Drawing.Size(130, 38)
$btnPlain.DialogResult = 'OK'
$btnPlain.BackColor = [System.Drawing.Color]::FromArgb(37, 99, 235)
$btnPlain.ForeColor = [System.Drawing.Color]::White
$btnPlain.FlatStyle = 'Flat'
$btnPlain.FlatAppearance.BorderSize = 0
$form.Controls.Add($btnPlain)
$form.AcceptButton = $btnPlain

$btnFancy = New-Object System.Windows.Forms.Button
$btnFancy.Text = 'ファンシー'
$btnFancy.Location = New-Object System.Drawing.Point(164, 124)
$btnFancy.Size = New-Object System.Drawing.Size(130, 38)
$btnFancy.DialogResult = 'Yes'
$btnFancy.BackColor = [System.Drawing.Color]::FromArgb(124, 58, 237)
$btnFancy.ForeColor = [System.Drawing.Color]::White
$btnFancy.FlatStyle = 'Flat'
$btnFancy.FlatAppearance.BorderSize = 0
$form.Controls.Add($btnFancy)

$btnSkip = New-Object System.Windows.Forms.Button
$btnSkip.Text = 'スキップ'
$btnSkip.Location = New-Object System.Drawing.Point(304, 124)
$btnSkip.Size = New-Object System.Drawing.Size(130, 38)
$btnSkip.DialogResult = 'Cancel'
$btnSkip.FlatStyle = 'Flat'
$btnSkip.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(220,220,220)
$btnSkip.ForeColor = [System.Drawing.Color]::FromArgb(120,120,120)
$form.Controls.Add($btnSkip)
$form.CancelButton = $btnSkip

$result = $form.ShowDialog()
$mode = $null
if ($result -eq 'OK')   { $mode = 'plain' }
if ($result -eq 'Yes')  { $mode = 'fancy' }
if ($mode) {
    Start-Process -FilePath $env:PY_EXE `
        -ArgumentList @('"' + $env:HOOK_SCRIPT + '"', '--file', '"' + $env:MD_PATH + '"', '--mode', $mode) `
        -WindowStyle Hidden
}
'''

    env = os.environ.copy()
    env["PY_EXE"] = py_exe
    env["HOOK_SCRIPT"] = script_path
    env["MD_PATH"] = str(src)
    env["MD_NAME"] = src.name

    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception:
        pass


# ── CLI MODE ─────────────────────────────────────────────────────────────────

def cli_render(src: Path, mode: str) -> None:
    src = src.resolve()
    if not src.exists():
        return

    out_path = determine_output(src)
    if out_path is None:
        return

    md = src.read_text(encoding="utf-8")

    if mode == "fancy":
        html = render_fancy(md, src)
    else:
        body = convert_markdown(md)
        html = render_plain(body, md, src)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    try:
        os.startfile(str(out_path))
    except Exception:
        pass


# ── OUTPUT PATH ──────────────────────────────────────────────────────────────

def determine_output(src: Path) -> Path | None:
    s = str(src).replace("\\", "/").lower()
    proj = str(PROJECT_DIR).replace("\\", "/").lower()
    if s.startswith(proj + "/"):
        rel = src.relative_to(PROJECT_DIR)
        return OUTPUT_DIR / rel.with_suffix(".html")
    if "/plans/" in s:
        return OUTPUT_DIR / "_plans" / src.with_suffix(".html").name
    if "/memory/" in s:
        return OUTPUT_DIR / "_memory" / src.with_suffix(".html").name
    return None


# ── MARKDOWN → HTML BODY ─────────────────────────────────────────────────────

def convert_markdown(md: str) -> str:
    try:
        import markdown as _md
        return _md.markdown(
            md,
            extensions=["fenced_code", "tables", "attr_list", "sane_lists"],
        )
    except ImportError:
        return simple_md(md)


# ── PLAIN RENDER (Notion-style template + TOC, no API call) ──────────────────

def render_plain(body: str, md: str, src: Path) -> str:
    body = inject_heading_anchors(body)
    toc = build_toc(body)
    title = derive_title(md, src)
    today = datetime.date.today().strftime("%Y.%m.%d")
    src_url = str(src).replace("\\", "/")

    template = TEMPLATE.read_text(encoding="utf-8")
    return (
        template
        .replace("{{TITLE}}", html_lib.escape(title))
        .replace("{{CONTENT}}", body)
        .replace("{{TOC}}", toc or '<p style="font-size:11px;color:#a1a1aa">No headings</p>')
        .replace("{{DATE}}", today)
        .replace("{{SOURCE}}", html_lib.escape(short_source(src)))
        .replace("{{SOURCE_URL}}", html_lib.escape(src_url))
    )


# ── FANCY RENDER (Claude API — consumes tokens) ───────────────────────────────

def select_model(md: str) -> str:
    """Pick a model tier based on document complexity signals."""
    chars = len(md)
    headings    = len(re.findall(r"^#{1,6} ", md, re.MULTILINE))
    code_blocks = len(re.findall(r"^```",     md, re.MULTILINE)) // 2
    table_rows  = len(re.findall(r"^\|",      md, re.MULTILINE))

    score = 0
    if chars > 4000:       score += 2
    elif chars > 1500:     score += 1
    if code_blocks >= 4:   score += 2
    elif code_blocks >= 2: score += 1
    if headings >= 6:      score += 2
    elif headings >= 3:    score += 1
    if table_rows >= 8:    score += 1

    if score >= 4:
        return FANCY_MODELS["heavy"]
    if score >= 2:
        return FANCY_MODELS["medium"]
    return FANCY_MODELS["light"]


def render_fancy(md: str, src: Path) -> str:
    try:
        import anthropic
    except ImportError:
        return render_plain(convert_markdown(md), md, src)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    model = select_model(md)
    title = derive_title(md, src)
    today = datetime.date.today().strftime("%Y.%m.%d")

    prompt = f"""以下のMarkdownドキュメントをリッチなHTMLに変換してください。

## 要件

1. **図の自動生成**: フローチャート・状態遷移図・クラス図・シーケンス図など、図で表現できる箇所を特定し、インラインSVGで作図してください。図が有効でない場合は省略して構いません。
2. **デザイン**: Notion / Linear のようなクリーンでモダンなスタイル。白背景、Inter + Yu Gothic UI フォント、最大幅760px。
3. **完全な自己完結HTML**: DOCTYPE, head(インラインCSS含む), body をすべて含むファイルとして出力してください。
4. **日本語対応**: 日本語フォント設定必須（Yu Gothic UI, Hiragino Sans, sans-serif フォールバック）。
5. **SVG**: 外部ライブラリ・外部URL一切なし。インライン埋め込みのみ。
6. タイトル: `{html_lib.escape(title)}`  生成日: `{today}`

## Markdown

```
{md}
```

HTMLコードのみを出力してください（```html ... ``` で囲んでも構いません）。"""

    message = client.messages.create(
        model=model,
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}],
    )

    content = message.content[0].text.strip()
    content = re.sub(r"^```html\s*\n", "", content)
    content = re.sub(r"\n```\s*$", "", content)
    return content


# ── HELPERS ──────────────────────────────────────────────────────────────────

def derive_title(md: str, src: Path) -> str:
    for line in md.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return src.stem


def short_source(src: Path) -> str:
    s = str(src)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home):]
    return s.replace("\\", "/")


_HEADING_RE = re.compile(
    r'<h([2-4])(?:\s[^>]*?id="([^"]+)")?[^>]*>(.+?)</h\1>',
    re.IGNORECASE | re.DOTALL,
)

def inject_heading_anchors(html: str) -> str:
    used: set[str] = set()
    def slugify(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        slug = re.sub(r"[^\w぀-ヿ一-鿿\- ]", "", text).strip().lower()
        slug = re.sub(r"\s+", "-", slug) or "section"
        base = slug
        i = 2
        while slug in used:
            slug = f"{base}-{i}"; i += 1
        used.add(slug)
        return slug

    def repl(m: re.Match) -> str:
        level, ident, inner = m.group(1), m.group(2), m.group(3)
        if not ident:
            ident = slugify(inner)
            return f'<h{level} id="{ident}">{inner}</h{level}>'
        used.add(ident)
        return m.group(0)

    return _HEADING_RE.sub(repl, html)


def build_toc(html: str) -> str:
    items: list[str] = []
    for m in _HEADING_RE.finditer(html):
        level = int(m.group(1))
        ident = m.group(2) or ""
        text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if not ident:
            continue
        items.append(f'<li class="toc-h{level}"><a href="#{ident}">{html_lib.escape(text)}</a></li>')
    if not items:
        return ""
    return "<ul>" + "".join(items) + "</ul>"


# ── MINIMAL FALLBACK MARKDOWN PARSER ─────────────────────────────────────────

def simple_md(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    code_buf: list[str] = []
    in_list = None
    in_table = False
    table_buf: list[str] = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    def flush_table():
        nonlocal in_table, table_buf
        if in_table:
            out.append(_table_to_html(table_buf))
            table_buf = []
            in_table = False

    for line in lines:
        if line.startswith("```"):
            flush_list(); flush_table()
            if in_code:
                out.append("<pre><code>" + html_lib.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        if "|" in line and re.match(r"^\s*\|", line):
            in_table = True
            table_buf.append(line)
            continue
        else:
            flush_table()

        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            flush_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        if re.match(r"^\s*[-*]\s+", line):
            if in_list != "ul":
                flush_list()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{_inline(re.sub(r'^\\s*[-*]\\s+', '', line))}</li>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            if in_list != "ol":
                flush_list()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{_inline(re.sub(r'^\\s*\\d+\\.\\s+', '', line))}</li>")
            continue

        flush_list()

        if re.match(r"^\s*---+\s*$", line):
            out.append("<hr>")
            continue

        if line.startswith(">"):
            out.append(f"<blockquote><p>{_inline(line.lstrip('>').strip())}</p></blockquote>")
            continue

        if line.strip() == "":
            out.append("")
        else:
            out.append(f"<p>{_inline(line)}</p>")

    flush_list(); flush_table()
    if in_code:
        out.append("<pre><code>" + html_lib.escape("\n".join(code_buf)) + "</code></pre>")

    return "\n".join(out)


def _inline(text: str) -> str:
    text = html_lib.escape(text)
    text = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _table_to_html(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    if len(cells) < 2:
        return ""
    if len(cells) > 2 and re.match(r"^[\s:|-]+$", "|".join(cells[1])):
        head, body = cells[0], cells[2:]
    else:
        head, body = cells[0], cells[1:]
    parts = ["<table><thead><tr>"]
    parts += [f"<th>{_inline(c)}</th>" for c in head]
    parts.append("</tr></thead><tbody>")
    for row in body:
        parts.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
