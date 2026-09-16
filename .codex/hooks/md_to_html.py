"""Explicit Markdown-to-HTML rendering; no stdin hook or dialog is launched.

--file PATH writes a local plain HTML review without an API call.
--open opens that result in the default browser only when requested.
--mode fancy opts into an API call and requires FLU_HTML_MODEL to be set.
"""
from __future__ import annotations

import argparse
import datetime
import html as html_lib
import os
from pathlib import Path
import re
import sys
import webbrowser

HOOK_DIR = Path(__file__).resolve().parent
PROJECT_DIR = HOOK_DIR.parent.parent
OUTPUT_DIR = PROJECT_DIR / ".html"
TEMPLATE = HOOK_DIR / "template.html"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Markdown file to render")
    parser.add_argument("--mode", choices=["plain", "fancy"], default="plain")
    parser.add_argument("--open", action="store_true", help="Open the rendered HTML in a browser")
    args = parser.parse_args(argv)
    try:
        out_path = cli_render(Path(args.file), args.mode)
        if args.open and not webbrowser.open(out_path.as_uri()):
            raise RuntimeError(f"Could not open browser: {out_path}")
    except Exception as exc:
        print(f"[md_to_html] {exc}", file=sys.stderr)
        return 2
    print(out_path)
    return 0


def cli_render(src: Path, mode: str) -> Path:
    src = src.resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Markdown file not found: {src}")
    out_path = determine_output(src)
    if out_path is None:
        raise ValueError(f"File is outside this worktree, plans, or memory: {src}")
    md = src.read_text(encoding="utf-8")
    if mode == "fancy":
        html = render_fancy(md, src)
    else:
        html = render_plain(convert_markdown(md), md, src)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


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

def render_fancy(md: str, src: Path) -> str:
    model = os.environ.get("FLU_HTML_MODEL", "").strip()
    if not model:
        raise RuntimeError("Set FLU_HTML_MODEL before explicitly requesting fancy rendering")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Fancy rendering requires the optional anthropic package") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

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

    content = next(
        (block.text for block in message.content if block.type == "text"), ""
    ).strip()
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
    raise SystemExit(main())
