# Claude Code Skills 演習報告

## 1. 目的

Claude Code の Skills 機能について、公式ドキュメントを参照しながら、既存 Skill の利用・カスタム Skill の作成・引数や Dynamic Context の利用・安全な実行確認までを実践した。

本演習では、単に Skill を作成するだけでなく、**実際に呼び出して動作を確認すること**を重視した。

---

## 2. 実施環境

- Claude Code
- Windows / PowerShell
- Cursor
- Git / GitHub
- 対象プロジェクト: `ai-sales-automation`

主な対象ファイル:

- `main.py`
- `email_templates.py`
- `outlook_draft.py`
- `company_researcher.py`
- `prospects.csv`
- `.claude/skills/`

---

## 3. Bundled Skills の確認

Claude Code に標準・バンドルされている Skill を実際に呼び出し、用途を確認した。

### `/code-review`

`email_templates.py` の変更差分に対してコードレビューを実施した。

確認内容:

- 変更差分のレビュー
- セキュリティ観点
- 既存処理への影響
- 潜在的なリスク

`html.escape()` を追加した変更について、意図した HTML エスケープ処理として問題ないことを確認した。

### `/debug`

Claude Code のデバッグ用 Skill の用途を確認した。

学習用として `email_templates.py` に意図的な変数名ミスを入れ、その後の `/verify` 演習で検出・修正した。

### `/loop`

継続的なタスクを繰り返し実行する用途を確認した。

今回は継続タスクがなかったため、動作確認のみ実施した。

### `/batch`

複数ファイルをまとめて処理する用途を確認した。

既存ファイルに docstring を追加する想定で試したが、対象ファイルにはすでに必要な記述があり、変更不要と判断された。

### `/claude-api`

Claude API を利用する最小構成の Python サンプルを確認した。

---

## 4. `/run` と `/verify`

対象プロジェクトは Outlook と `prospects.csv` を扱うため、実データや実 Outlook に影響を与えないことを優先した。

### `/run`

通常の `python main.py` 実行では Outlook の下書き作成や CSV 更新が発生する可能性があるため、実 Outlook を使わずにコードのみの smoke test を実施した。

確認内容:

- Python モジュールの import
- CSV 読み込み
- メールテンプレート生成
- 実データを書き換えない範囲での実行

この確認で、学習用に入れていた変数名ミスによる `UnboundLocalError` を検出した。

### `/verify`

実 Outlook を使わず、隔離された一時ディレクトリと stub を利用して検証した。

確認内容:

- CLI の処理経路
- リサーチあり / なしの分岐
- HTML エスケープ
- Outlook を実際に操作しないこと

最初の検証では、学習用の変数名ミスにより FAIL となった。

該当箇所のみ修正後、再度 `/verify` を実行し、最終的に以下を確認した。

```text
Verdict: PASS
```

---

## 5. `/run-skill-generator`

プロジェクト専用の安全な実行 Skill を生成した。

生成された構成:

```text
.claude/
└─ skills/
   └─ run-ai-sales-automation/
      ├─ SKILL.md
      ├─ driver.py
      ├─ stub_outlook_draft.py
      └─ fixtures/
         └─ sample_prospects.csv
```

実 Outlook や実際の `prospects.csv` に影響を与えず、プロジェクトの処理を確認できる構成になっている。

この演習から、Skill は `SKILL.md` だけでなく、必要に応じて script・fixture・template などの補助ファイルを持てることを理解した。

---

## 6. Personal Skill の確認

既存の Personal Skill として以下を使用した。

```text
~/.claude/skills/summarize-changes/SKILL.md
```

内容の中心:

```markdown
---
description: Summarizes uncommitted changes and flags anything risky.
---

## Current changes

!`git diff HEAD`

## Instructions

変更を2〜3点で要約し、
リスクがあれば指摘してください。
```

### 手動実行

```text
/summarize-changes
```

を実行し、Git の未コミット差分を取得して要約できることを確認した。

### 自動呼び出し

通常の文章として、

```text
What did I change?
```

と依頼した場合にも、Skill が自動的に利用されることを確認した。

この演習から、`description` が Skill の自動呼び出し判断に重要であることを理解した。

---

## 7. Personal Skill と Project Skill

Skill の配置場所による違いを確認した。

### Personal Skill

```text
~/.claude/skills/
```

自分の複数プロジェクトで利用する Skill。

### Project Skill

```text
.claude/skills/
```

特定プロジェクト専用の Skill。

Git 管理することで、プロジェクト内の他メンバーとも共有できる。

今回の `ai-sales-automation` 固有の処理や安全ルールを扱う Skill は、Project Skill として管理するのが適切と判断した。

---

## 8. Frontmatter の理解

Skill の `SKILL.md` で利用する代表的な frontmatter を確認した。

主に確認した項目:

- `name`
- `description`
- `argument-hint`
- `arguments`
- `disable-model-invocation`
- `user-invocable`
- `allowed-tools`
- `disallowed-tools`
- `model`
- `context`
- `agent`

特に、実際にメール送信などの副作用がある操作を Skill 化する場合は、

```yaml
disable-model-invocation: true
```

として、Claude が自動で呼び出さない設計が重要だと理解した。

---

## 9. 引数を受け取る Skill

Project Skill として以下を作成した。

```text
.claude/skills/explain-file/SKILL.md
```

目的:

```text
/explain-file <filename>
```

の形式でファイル名を受け取り、初心者向けに役割を説明する。

利用した要素:

```yaml
argument-hint: <filename>
```

および、

```text
$ARGUMENTS
```

を使用した。

実行例:

```text
/explain-file main.py
```

結果として、`main.py` がプロジェクト全体を制御するオーケストレーターであり、

- CSV の読み込み
- 処理済み行のスキップ
- AI リサーチ
- Outlook 下書き作成
- 結果表示

などを担当していることを説明できた。

---

## 10. Dynamic Context

Skill 内から現在の環境情報を取得する方法を確認した。

`summarize-changes` では、

```markdown
!`git diff HEAD`
```

を利用している。

整理すると、

```text
$ARGUMENTS
```

は **ユーザーから渡された入力**、

```text
!command
```

は **実行環境から取得する情報**

という違いがある。

これにより、Git の差分や現在の状態を毎回手作業でプロンプトに貼らず、Skill 側で自動取得できる。

---

## 11. `context: fork` の確認

Project Skill として、

```text
.claude/skills/explore-project/SKILL.md
```

を作成した。

設定例:

```yaml
---
name: explore-project
description: Explores this project's structure and reports what its main files do.
context: fork
agent: Explore
---
```

この Skill を実行した結果、

```text
Running in the background as @explore-project
```

と表示され、通常の会話とは分離されたコンテキストで処理が実行されることを確認した。

`context: fork` により、

- Skill の内容をタスクとして渡す
- 別コンテキストで処理する
- 結果だけをメインの会話へ返す

という構成を作れることを理解した。

この項目までを Skills 演習の範囲とし、次の学習テーマである Sub-agents への橋渡しとした。

---

## 12. Skills 演習を通じて理解したこと

Skills は単なる定型プロンプトではなく、以下を組み合わせて Claude Code の動作を再利用可能な形にできる仕組みだと理解した。

- 指示・手順
- 引数
- Git や shell から取得する Dynamic Context
- 利用可能なツール
- 自動呼び出し / 手動呼び出し
- 補助スクリプトや fixture
- 別コンテキストでの実行

また、安全面では、AI に「やらないで」と指示するだけではなく、実データや外部サービスに影響を与えないテスト環境・stub・権限制御を組み合わせることが重要だと学んだ。

---

## 13. 作成・確認した主な成果物

```text
~/.claude/skills/
└─ summarize-changes/
   └─ SKILL.md

.claude/
└─ skills/
   ├─ explain-file/
   │  └─ SKILL.md
   │
   ├─ explore-project/
   │  └─ SKILL.md
   │
   └─ run-ai-sales-automation/
      ├─ SKILL.md
      ├─ driver.py
      ├─ stub_outlook_draft.py
      └─ fixtures/
         └─ sample_prospects.csv
```

---

## 14. 次の学習

Skills 演習完了後は Sub-agents に進み、以下を学習する。

- Sub-agent の役割
- カスタム Sub-agent
- tools / model の設定
- Skill のプリロード
- 複数 Sub-agent への役割分担
- メイン Agent からの委任設計
