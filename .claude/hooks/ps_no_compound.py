#!/usr/bin/env python
"""PreToolUse hook for the PowerShell tool.

PowerShell の複合一行は権限システムが「文字列まるごと」で照合するため
（Bash のようにサブコマンド分割されない）、許可済みコマンドを `;` で連結
したり `& $var` で呼び出すと毎回手動承認になる。さらに PowerShell ツールは
コール間でシェル変数を保持しないので `$wt = "..."; & $py ...` 形式は実行時にも壊れる。

このフックは、その「照合不能になる形」を deny して理由を返し、
1コール=1コマンド・変数なし・スラッシュ絶対パスへ誘導する。
deny 後に Claude が単発コマンドへ書き直せば、settings.json の単発ルールにマッチして
承認プロンプトが出なくなる（＝記事 https://qiita.com/nkjzm/items/f7032326b6644492665e の方式）。

安全側の設計: 判定に迷う場合は何も出力せず exit 0（通常の権限フローに委ねる）。
"""
import json
import re
import sys


def strip_quoted(s: str) -> str:
    # "..." と '...' の中身を除去し、文字列内の ; や & を区切り扱いしない
    s = re.sub(r'"[^"]*"', '""', s)
    s = re.sub(r"'[^']*'", "''", s)
    return s


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if data.get("tool_name") not in (None, "PowerShell"):
        # matcher で PowerShell に絞っているが、念のため他ツールは素通り
        return 0

    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    scan = strip_quoted(cmd)

    reasons = []
    if ";" in scan:
        reasons.append("`;` でコマンドを連結しない")
    if "&&" in scan or "||" in scan:
        reasons.append("`&&`/`||` を使わない（PS5.1では構文エラーかつ照合不能）")
    if re.search(r"&\s*\$", scan):
        reasons.append("`& $var`（変数経由の呼び出し）を使わない／コール間で変数は保持されない")

    if not reasons:
        return 0

    msg = (
        "PowerShellの複合一行は権限照合できず毎回確認が出ます。"
        "1コール=1コマンドに分け、" + " / ".join(reasons) + "。"
        "venv/ツールは変数を使わずスラッシュ絶対パスで実行してください。例: "
        '& "C:/02_work/01_Fighting_the_Flu-worktrees/<wt>/.venv/Scripts/python.exe" '
        '"C:/02_work/01_Fighting_the_Flu-worktrees/<wt>/tools/run.py" check'
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }
    # ensure_ascii=True (default): \uXXXX 形式で出力し、Windows のコンソール
    # コードページ(cp932)による文字化けを避ける。JSONパーサ側で日本語に復元される。
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
