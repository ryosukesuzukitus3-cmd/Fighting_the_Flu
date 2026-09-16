---
name: worktree-task-start
description: タスク用worktreeとvenvを用意・再開するときに参照できる任意の手引き。
---

# 作業場所の用意

詳細な方針は `CLAUDE.md` の「作業場所とPR」を参照する。
同じタスクの作業場所がある場合は、状態を確認して再開できる。この手引きの実行自体を開始条件にしない。

## 新しいタスク

管理用mainで変更と既存worktreeを確認する。未コミットのユーザー作業や他タスクを移動・上書きしない。
管理用mainではファイルを編集せず、新しいタスクは専用worktreeに分ける。

```powershell
git status --short --branch
git worktree list
git fetch --prune origin
git worktree add C:/02_work/01_Fighting_the_Flu-worktrees/flu-claude-some-task -b claude/some-task origin/main
```

新しいworktreeへ移って環境を用意する。Pythonの対応範囲は `pyproject.toml` に従う。

```powershell
py -3 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python tools/run.py check
```

最初から検査が失敗する場合は、その状態を記録して原因を調べる。既存の不具合の調査・修正を止める条件にはしない。
MarkdownのHTML変換やAPI用の追加依存は、それらを利用するときだけ用意する。

## 中断後の再開

作業場所、現在のブランチ、未コミット変更、リモートとの差を確認する。
他タスクのworktreeを無断で別ブランチへ切り替えて流用しない。

```powershell
git status --short --branch
git branch -vv
```
