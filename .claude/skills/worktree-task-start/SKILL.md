---
name: worktree-task-start
description: 新しい実装・修正タスクを開始するとき、worktree と venv をセットアップする手順。タスク開始時・「worktreeを作って」と言われたときに必ず使用。
---

# worktree-task-start

新規タスクの作業場所を安全に用意するための実行手順。詳細な運用方針は
`CLAUDE.md` の「Claude PR運用フロー」「worktree 運用」を参照（本スキルはそこから導出した
実行コマンド列とゲートのみを持つ薄いラッパー）。

PowerShell は 1コール = 1コマンド。変数展開は使わず、スラッシュ区切りの絶対パスを直書きする。

## 1. 開始前チェック（管理用フォルダで実行）

ユーザーの未コミット変更・チェックアウト中ブランチを壊さないための確認。

```
git -C C:/02_work/01_Fighting_the_Flu status --short --branch
```

**ゲート**: 出力に変更差分がある、またはチェックアウト中ブランチが `main` でない場合は、
その内容をユーザーに報告してから続行する。管理用フォルダでは絶対にファイルを編集・コミットしない。

## 2. 直前に fetch する

古い `origin/main` を base にすると worktree が最初から behind になり、
rebase 系操作が deny リストに触れて詰む。

```
git -C C:/02_work/01_Fighting_the_Flu fetch --prune origin
```

## 3. worktree を作成する

フォルダ名は `C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>`、
ブランチ名は `claude/<短いタスク名>`。**タスク名部分は両者で必ず一致させる。**

```
git -C C:/02_work/01_Fighting_the_Flu worktree add C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名> -b claude/<短いタスク名> origin/main
```

例:

```
git -C C:/02_work/01_Fighting_the_Flu worktree add C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-fix-stage4-boss-ui -b claude/fix-stage4-boss-ui origin/main
```

**禁止**: 既存 worktree のブランチだけを切り替えて流用すること（過去に状態混乱を招いた実害あり）。
タスクごとに新しい worktree を作る。

## 4. venv セットアップ（worktree 内で、1コマンドずつ）

```
py -3 -m venv C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>/.venv
```

```
C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>/.venv/Scripts/python -m pip install -U pip
```

```
C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>/.venv/Scripts/python -m pip install -e "C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>[dev]" markdown
```

`tools/run.py pr-report --fancy` を使う予定のタスクだけ、追加で:

```
C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>/.venv/Scripts/python -m pip install anthropic
```

## 5. 健全性確認

作業を始める前に、この worktree の状態が壊れていないことを確認する。

```
C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名>/.venv/Scripts/python tools/run.py check
```

**ゲート**: `check` がパスしてから初めてファイル編集を始める。失敗したまま作業を進めない。

## 6. 中断→再開時のゲート

同じ worktree で作業を再開する前に、必ず現在ブランチと ahead/behind を確認する。

```
git -C C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名> status --branch
```

```
git -C C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-<短いタスク名> branch -vv
```

想定と違うブランチ・想定外の ahead/behind が出た場合は、編集前にユーザーへ報告する。

## 参照

- `CLAUDE.md` > 「Claude PR運用フロー」
- `CLAUDE.md` > 「worktree 運用」
