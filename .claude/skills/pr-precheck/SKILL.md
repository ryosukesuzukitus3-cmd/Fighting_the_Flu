---
name: pr-precheck
description: PRの作成やレビュー時に、必要な確認を選ぶための任意の手引き。
---

# PR確認の手引き

詳細な方針は `CLAUDE.md` の「作業場所とPR」「検証と証拠」を参照する。
この手引きを毎回呼ぶ必要はない。変更に関係する確認を選び、既に揃っている証拠を再利用する。

## 提出内容を確認する

- 作業treeの未コミット変更と差分を確認し、他の作業を混ぜない。
- PR作成後は、ローカルで検証したコミットとPR先端の `headRefOid` を照合する。不一致をpush漏れと決めつけず、他の更新やブランチも確認する。
- PRのCI状態を確認する。失敗は原因を調べ、未解決のものを報告する。

```powershell
git status --short --branch
git diff --check
git rev-parse HEAD
gh pr view <N> --json headRefOid
gh pr checks <N>
```

## 変更に合う検証を選ぶ

```powershell
.venv/Scripts/python tools/run.py docs-check
.venv/Scripts/python tools/run.py check
.venv/Scripts/python tools/run.py test
```

画面や操作の変更では必要な場面を確認し、実行した検証だけを報告する。
before/after画像、画像のPR添付、`pr-media`によるアップロードは任意とする。
調査用の一時画像は通常のソース差分へ混ぜない。

PR本文には、問題、変更後の振る舞い、検証結果、残る制約を簡潔に書く。
複数行の本文をGitHub CLIへ渡す場合は `--body-file` を使い、引用符や改行の崩れを避ける。

```powershell
gh pr create --title "..." --body-file tmp/pr_body.md
```
