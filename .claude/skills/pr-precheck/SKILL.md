---
name: pr-precheck
description: PR を作成する直前・「マージしていい？」に答える前に必ず通すチェックリスト。PR作成・完了宣言の前に使用。
---

# pr-precheck

PR 作成・マージ可否の完了宣言の前に必ず通す確認ゲート。詳細な運用方針は
`CLAUDE.md` の「Claude PR運用フロー」「PR 可視化」を参照（本スキルはそこから導出した
実行コマンド列とゲートのみを持つ薄いラッパー）。

PowerShell は 1コール = 1コマンド。変数展開は使わず、スラッシュ区切りの絶対パスを直書きする。
以下 `<wt>` はタスクの worktree 絶対パス（例: `C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>`）。

## 1. 全コミット push 照合

push 漏れのまま「マージOK」と宣言した実害があるため、必ず二段階で確認する。

PR作成前:

```
git -C <wt> status --short --branch
```

**ゲート**: `ahead`/`behind` が 0 であること。ahead が残っていれば push してから次に進む。

PR作成後（マージ可否を答える直前）:

```
gh pr view <N> --json headRefOid
```

```
git -C <wt> rev-parse HEAD
```

**ゲート**: 両方の commit hash が一致することを確認してから「マージしていい」と答える。
一致しない場合は push 漏れなので、押してから再照合する。

## 2. 検証の実行

影響範囲に応じて実行する。

```
<wt>/.venv/Scripts/python <wt>/tools/run.py check
```

```
<wt>/.venv/Scripts/python <wt>/tools/run.py test
```

必要なら再キャプチャ（3.参照）。

**ゲート**: 報告する検証結果は、実際に実行したツール出力を根拠にする。
実行していない検証を「実行済み」「パス」と書かない。

## 3. 見た目変更がある場合

```
<wt>/.venv/Scripts/python <wt>/tools/run.py capture ...（before/after を captures/ 配下に出力）
```

```
<wt>/.venv/Scripts/python <wt>/tools/run.py pr-media <wt>/captures/before.png <wt>/captures/after.png
```

**ゲート**: 調査用に撮った一時画像は PR の差分（コミット対象）に混ぜない。
`pr-media` で media ブランチにアップロードした URL だけを PR 本文に埋め込む。

## 4. PR 本文はファイル化

ヒアドキュメント連結は権限照合と文字化けの事故源になるため、本文は必ずファイルに書き出してから渡す。

```
gh pr create --title "..." --body-file <wt>/tmp/pr_body.md
```

## 5. PR 作成後の CI 確認

```
gh pr checks <N>
```

**ゲート**: 落ちている場合、原因が自分の変更由来か main 由来（既知の赤）かを切り分けてから報告する。
切り分けずに「CI失敗＝自分の変更のせい」と決めつけない。

## 参照

- `CLAUDE.md` > 「Claude PR運用フロー」
- `CLAUDE.md` > 「PR 可視化」
