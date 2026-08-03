# Kata

**AI とのペアプログラミングのためのプロジェクトメモリ——一度コンパイルし、継続的に更新、人間が問い、AI が保守する。**

[![tests](https://github.com/litianyi-007/kata/actions/workflows/test.yml/badge.svg)](https://github.com/litianyi-007/kata/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-22d3ee.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-22d3ee.svg)](#クイックスタート)

![Kata — AIペア・エンジニアリングのためにビジネスの意味論をコンパイルする。プロジェクトメモリのための AI 保守型 wiki。](docs/assets/readme/kata-hero-banner.svg)

> 言語リンク：[🇨🇳 中文](README.md)（デフォルト）・[🇬🇧 English](README.en.md)

## 何を解決するのか

プロジェクトに積み上がった判断——なぜこの閾値がこの数値なのか、前回このアプローチが却下されたのは
なぜか——は、チャット履歴に散らばり、誰も開かなくなったドキュメントに散らばっている。agent の
セッションを切り替えるたびに、これらは毎回学び直すか、あるいはまったく学ばれずに終わり、同じ間違いを
また繰り返すことになる。

kata は **AI が保守し、人間が問いかける wiki** だ。着想元は
[Karpathy の LLM-Wiki 構想](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)——
「RAG と違い、wiki は一度コンパイルしてから最新に保つもの」「あなた（人間）が素材を選び、良い問いを
立て、残りは LLM に任せる」。kata はこの構想の上に **自己閉ループ** を足した：ingest → 相互リンク →
価値ある問いは hub ページとしてアーカイブ → 次の session はまず hub を読んでから着手する。

実測例：NECallKit（マルチプラットフォームの Electron + native SDK）での 4 週間の dogfood で、
アーカイブされた 1 件の問い（filed query）が wiki に **17 本のエッジ** を追加した——通常の
import は 1 ページあたり平均 5 本のエッジしか生まない。実際のバグ 3 件（B066/B070/B074）、
wiki は 1 つ。詳細は
[Essay #1 草稿](docs/essay-drafts/2026-05-13-essay1-code-quality-vs-business-DRAFT.md) を参照。

![アーカイブされた問い 1 件で +17 エッジ。import は 1 ページ平均 5 エッジ。wiki は読み込むときではなく、問いかけたときに育つ。](docs/assets/essay/V1-wiki-compounding.svg)

### 類似ツールとの比較

|                        | kata                             | Obsidian Copilot / Smart Connections | MCP memory servers | RAG / ベクトルDB     |
|------------------------|-----------------------------------|---------------------------------------|---------------------|----------------------|
| 真実はどこにあるか     | あなたの markdown ファイル        | あなたの markdown ファイル            | server 側のストレージ | embedding インデックス |
| 一度コンパイルか毎回か | 一度コンパイルし、継続的に更新    | クエリのたびにその場で計算            | クエリのたびにその場で計算 | クエリのたびにその場で計算 |
| 相互参照               | ingest 時にページへ書き込む       | embedding からその場で計算            | なし、または schema で固定 | なし                  |
| オフラインで使えるか   | はい（embedding モデル不要）      | embedding モデルが必要                | server が必要        | embedding モデルが必要 |

kata は総合結果を wiki 本体に焼き込む。RAG やチャットの記憶は毎回ゼロから計算し直す——流動的な検索
には向いているが、相互参照がどこにも定着しないので、使うほど厚みが増すことはない。

## クイックスタート

前提条件：Git ≥ 2.20（v1.8 の sync カスタム merge driver に必要）；Python 3.10+（純粋な stdlib
のみ、`plugin/scripts/` 配下のスクリプトに `pip install` は不要）。

kata には **4 つの並行するインストール経路** がある——自分の LLM ツールに合うものを選べばいい。
4 つの経路はどれも **同じ 18 個の skill** と **同じ wiki ファイルシステムのレイアウト** を生む。
wiki の中身そのものは常に `~/.llm-wiki/<project>/` に独立して置かれ、どの経路でインストールしたか
とは無関係だ。

| 経路 | ツール | インストール先 | 範囲 |
|---|---|---|---|
| A | Claude Code（推奨） | `~/.claude/plugins/`（`claude /plugin install` が管理） | グローバル |
| B | Codex CLI | `~/.codex/skills/` + `~/kata/`（生成された skills + 環境変数） | グローバル |
| C | Standalone（任意の LLM） | セッションに system prompt として貼り付け | セッション単位 |
| D | GitHub Copilot CLI（v2.15.2+） | `~/.config/github-copilot/copilot-cli/`（`copilot plugin install` が管理） | グローバル |

**Path A — Claude Code：**

```bash
claude /plugin marketplace add litianyi-007/kata
claude /plugin install kata@kata
```

ローカル clone 上でプラグインを直接編集する場合：`claude /plugin marketplace add .` の後は
`./plugin/skills/` 内の変更が再インストールなしで反映される。更新/アンインストール：
`claude /plugin update kata` / `claude /plugin uninstall kata`（wiki の中身には影響しない）。

**Path B — Codex CLI**（Codex にはプラグインマーケットプレイスがなく、skills を discovery
ディレクトリに生成する方式）：

```bash
git clone https://github.com/litianyi-007/kata ~/kata
echo 'export KATA_HOME="$HOME/kata"' >> ~/.zshrc   # または ~/.bashrc
python ~/kata/scripts/install_codex_skills.py
```

インストール/更新後は Codex を再起動しないと新しい session には反映されない。`plugin/AGENTS.md`
は Codex の skill レジストリでは **ない**——インストーラーが生成する各 skill に注入する共通の
説明文だ。プロジェクト単位で別バージョンを使いたいだけなら `--dest <project>/.codex/skills`
を追加すればよい。

**Path C — Standalone（任意の LLM）：**

```bash
cat SKILL.md | pbcopy   # macOS の場合；Linux は xclip、Windows は clip を使う
```

`SKILL.md` は自己完結型——各 skill の説明、各ガード、既知の制限がすべて書かれている。A/B と同じ
schema と wiki レイアウトを生むが、代わりに決定的な Python スクリプトがなく（LLM が毎回ソートや
グラフクエリをその場で計算する必要がある）、`wiki-sync` の自動マージドライバもない。

**Path D — GitHub Copilot CLI：**

```bash
copilot plugin install litianyi-007/kata
```

Copilot CLI はリポジトリルート直下の `plugin.json`（v2.15.2 で追加、Copilot はトップレベルの
マニフェストしか探さず、サブディレクトリは再帰的に見ない）を読み、そこから `plugin/skills/`
を指す——Claude Code と同じ SKILL.md 群を使う。

### 最初の wiki を動かす

```bash
# 1. 初期化——対話形式でドメインを尋ね、適したカテゴリを提案する
/kata:wiki-init --path=~/.llm-wiki/my-project --domain="Electron + native SDK"

# 2. 最初のソースを取り込む——画像は自動で raw/assets/ に保存され、相互参照も自動で書き込まれる
/kata:wiki-ingest docs/ARCHITECTURE.md

# 3. 何がコンパイルされたか見てみる——新規ページ、新しく増えたエッジ、次に ingest すべき候補
/kata:wiki-digest

# 4. 本当の意思決定の問いを投げる——回答は hub ページとしてアーカイブされ、以後の agent はまずそれを読んでから動く
/kata:wiki-query "Electron renderer と native SDK の間の IPC トポロジは何か？"

# 5. グラフを探索する（[[wikilinks]] を BFS でたどる）
/kata:wiki-graph --neighbors attention --depth=2 --format=mermaid

# 6. 定期的なヘルスチェック
/kata:wiki-lint
```

## 18 個の skill 一覧

| Skill | 呼び出し | 一言で |
|---|---|---|
| wiki-init | `/kata:wiki-init` | 対話形式で起動：ドメインを尋ね、カテゴリを提案し、SCHEMA.md を書き、index.md/log.md を作成する |
| wiki-import | `/kata:wiki-import <path>` | 既存のドキュメントシステム（Obsidian/Notion/Confluence/フォルダ）を一括インポート。重複排除、レジューム対応、5 段階 |
| wiki-ingest | `/kata:wiki-ingest <source>` | 1 件のソースを取り込む：原文+画像を保存し、SCHEMA.md に従ってページを作成/更新し、index.md と log.md を更新する |
| wiki-search | `/kata:wiki-search <query>` | キーワード/タグ/タイプでランク付け検索。デフォルトでは active 層のみを見る。qmd/MCP へ拡張可能 |
| wiki-graph | `/kata:wiki-graph [モード]` | wiki をグラフとして問い合わせる：近傍探索、最短経路、hub/孤立ページ検出、frontmatter フィルタ——グラフ DB は維持しない |
| wiki-tier | `/kata:wiki-tier` | active-archived-frozen の 3 層メモリ閾値を確認/調整。手動 pin による上書きも可能 |
| wiki-digest | `/kata:wiki-digest` | 週次ヘルスチェック：活発度、階層分布、コンテンツの穴、クラスタ横断の統合、次の一手の提案 |
| wiki-query | `/kata:wiki-query <question>` | 引用付きで回答し、明示的な確信度を報告する。ページへの回填も可能。ローカルで miss した場合は外部プラグインにフォールバックできる |
| wiki-lint | `/kata:wiki-lint` | 構造チェック（孤立ページ/リンク切れ/frontmatter/陳腐化/階層/次元の完全性）+ コンテンツの穴 + SCHEMA.md 進化の提案 |
| wiki-config | `/kata:wiki-config` | SCHEMA.md の統一された読み書き窓口——`--show`/`--get`/`--set`/`--explain`/`--validate`、パス指定で操作 |
| wiki-dream | `/kata:wiki-dream` | auto-dreaming：凍結/アーカイブ済みページを再評価し、関連性が回復していれば復活を提案する。ファイルシステムを読むだけ |
| wiki-watch | `/kata:wiki-watch` | `raw/` 配下の新規ファイルを監視してキューに入れる。実際に ingest されるのは drain したときだけ——自分から wiki-ingest を呼び出すことは決してない |
| wiki-sync | `/kata:wiki-sync` | マルチマシン git 同期：log.md 用カスタムマージドライバ + ローカルロック + force-push 検知 + wiki_id 身元検証 |
| wiki-spec | `/kata:wiki-spec preflight <path>` | 新しい spec を起草する前に関連する既存 spec をスキャンし、著者に関係性を宣言させることで spec コーパスの内部消耗を防ぐ |
| wiki-session-ingest | `/kata:wiki-session-ingest` | 現在の AI CLI セッションから洞察を選び出し、wiki に蒸留する（増分方式、前回以降の新規メッセージのみを見る） |
| wiki-mcp-server | `/kata:wiki-mcp-server` | この wiki を読み取り専用の MCP server として起動し、他の MCP client や別の kata からのフェデレーションクエリに応える |
| wiki-federate | `/kata:wiki-federate search <query>` | wiki 間フェデレーションクエリ：`.federation.yaml` に登録された peer kata へ読み取り専用でクエリし、出典ごとに結果をマージする |
| wiki-skill-create | `/kata:wiki-skill-create` | プロジェクトローカルの skill を生成し、kata の query/ingest をこのプロジェクトの実際のコーディング/テスト/検証パイプラインに接続する |

日常の使い方をつなげると（4 つのループであって、4 つの独立したコマンドではない）：

- **デイリーループ** — 素材を `raw/` に放り込む → `wiki-ingest` → `wiki-digest --since=1d` でざっと確認。
- **クエスチョンループ** — `wiki-search`（または `wiki-graph --neighbors`）で位置を特定 →
  `wiki-query` で回答する。価値ある回答は自動的に `queries/*.md` として回填され、グラフの新しい
  ノードになる。
- **探索ループ** — `wiki-graph --shortest-path A,B` で、2 つのエンティティの間にある気づいて
  いなかった橋渡し概念を見つける。
- **ウィークリーループ** — `wiki-digest` で全体状況を見て、`wiki-lint` で構造/コンテンツの穴と
  schema 進化の提案を見つける。

## できないこと / 境界の実際

このセクションは免責事項ではない——以下の各項目は、すでに満たされている安全境界（セールスポイント）
であるか、正直な制限であるかのどちらかだ。

**すでに満たしている境界：**

- **フェデレーションクエリは境界を越えては読み取り専用**——kata は peer wiki に書き込むことは
  決してない。`wiki-mcp-server` が公開するのは `wiki-search` / `wiki-graph` の読み取り専用
  サブセットと `wiki-spec-preflight`（候補を出すだけで `--enforce` は公開しない）だけ。
  `wiki-ingest`、`wiki-import`、`wiki-tier --pin`、`wiki-dream --apply` は MCP 経由で
  公開されることは決してない。
- **`wiki-watch` 自身が `wiki-ingest` を呼び出すことは決してない**（ソースコードのコメント
  そのままの表現）——drain は常に明示的な人手によるステップであり、設定を誤った watcher が
  wiki ページを黙って変更することはあり得ない。
- **外部フォールバックプラグインは `command_template` と shell メタ文字を拒否する**——v1.4
  以降、認識するのは `argv:` トークン配列のみで、shell を経由しない。`auto_run` は
  デフォルトで実行前に人手の確認を必須とする。
- **`wiki-sync` は `wiki_id` が一致しない時点で abort する**。import 進行中は sync をブロック
  し、force-push も検知される（履歴の書き換えを黙って飲み込むことはない）。
- **spec の自動伝播（Phase 3）は opt-in の preview で、デフォルトでは無効**——ソース spec が
  後で編集されて supersession が取り消された場合に、自動で逆方向に取り消すことがまだできない
  ため。

**正直な制限（美化しない）：**

- **wiki のルートパス解決には天花板（上限）がない。** `SCHEMA.md` + `log.md` を持つ祖先
  ディレクトリを探す場合も、`.llm-wiki.yaml` / `.kata.yaml` のバインドファイルを探す場合も、
  `plugin/scripts/wiki_lib.py` の実装は一貫して `for cur in (start, *start.parents)` で
  あり——ファイルシステムのルートまでずっと歩いて行く。git の `GIT_CEILING_DIRECTORIES` の
  ような上限は存在しない。置き場所を間違えたバインドファイルが、深い階層のプロジェクトを
  黙って別の wiki にリダイレクトしてしまうことがある。これは**書き損じではなく、依存されて
  いる挙動だ**——「同じマシンで複数の wiki を」で説明するネストされたオーバーライドの使い方は、
  まさにこの仕組みによって、どれだけ深いサブディレクトリからでも monorepo ルートのバインドを
  見つけ出している。そのため今回のラウンドでは上限を追加せず、
  `docs/ISSUE-project-binding-unbounded-ancestor-walk.md` に記録するにとどめた。
  代償は現実のものだ：kata 自身のテストスイートは、これが原因で kata をインストールした
  どのマシンでもテストが最後まで走らなかった（v2.16.0 より前）。解決策はテスト fixture を
  プロジェクトの祖先チェーンの外に移すことであり、パーサーに上限を加えることではなかった。
- **dogfood の retrospective は一度も回填されていない。** `docs/dogfood-v1.6.md` /
  `docs/dogfood-v1.8.md` の retrospective、累積指標、GA 判断のセクションはすべて未記入の
  テンプレートプレースホルダのままで、v1.6 から v2.15.5 に至るまで誰も埋めたことがない。
  dogfood の記録は存在するが、それを GA の結論があるものとして読んではいけない。

## 主要な概念

### 階層モデル

| 層 | 内容 |
|---|---|
| **Base** | [Karpathy の LLM-Wiki 構想](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)——一度コンパイルし、最新に保つ；人間がキュレーションし、LLM が保守する；すべてはオプションであり組み合わせ自由。 |
| **Core** | **自己進化する知識システム**：(1) 自己閉ループ——ingest → 相互リンク → 問いのアーカイブ → 複利的に育つページ；(2) auto-dreaming——凍結されたページが関連性の回復時に再浮上する。 |
| **Phase 1**（現在） | **AI とのペアプログラミング。** core wiki を使ってプロジェクトのビジネス意味論——閾値、ライフサイクルの不変条件、ドメイン固有の慣習——をコンパイルし、AI agent が着手する前にプロジェクトの慣習を理解できるようにする。v1.4 → v1.13 はずっとこれに取り組んできた。 |
| **Phase 1+**（リリース済み） | **Spec History Management（v1.13）** と **Work-Loop Bridge（v1.15）**——下の「ワークフローへの組み込み」を参照。 |
| **Phase 2**（設計済み、未実装） | **チームでの spec 起草 + 意見対立の裁定。** 将来の意思決定で、すでに戦った議論をもう一度やり直さなくて済むようにする。 |
| **Phase 3+** | オープン。何が複利的に効くかを掴んでいくにつれて、コアは境界を広げ続ける。 |

**プロダクト**は Core + 各 Phase の延長であり、Phase 1 は最初の具体的な境界にすぎず、kata の
定義そのものではない。

### SCHEMA.md が唯一の権威ある設定

すべての取り決め——ページタイプ、frontmatter フィールド、タグの分類法、ページ作成ポリシー、
相互参照ポリシー、ページサイズの上限、ログのロールオーバー、**カスタム次元**、**メモリ階層の
閾値**——はすべて `{wiki_path}/SCHEMA.md` の中で生きている。プラグインは SCHEMA.md を読み取って
実行するのであって、意見をコードにハードコードしているわけではない。

```text
{wiki_path}/
├── SCHEMA.md          # 取り決め + 次元 + 階層ポリシー（ユーザーが編集可能）
├── index.md           # コンテンツ目次、1 行サマリー
├── log.md             # 追記式の操作ログ
├── raw/                # 不変の原資料（articles/papers/transcripts/assets/imported/external）
└── {categories}/       # SCHEMA.md で定義される、ドメインに合わせたもの
                        # 研究向け: entities/ concepts/ comparisons/ queries/
                        # 業務向け: people/ projects/ decisions/ meetings/
```

`wiki-config` はその汎用的な読み書き窓口（`show`/`get --path`/`set --path --value`/
`explain --path`/`validate`）で、既存のスカラーキーを外科的に置き換えるだけであり、schema
検証に失敗すれば自動でロールバックする。新しいキーや新しい YAML ブロックを追加するには、
依然として SCHEMA.md を手で編集するか `wiki-init` を再実行する必要がある。`wiki-tier`、
`wiki-init` それぞれのドメイン固有のショートカットは引き続き存在し、`wiki-config` は
ロングテールのシナリオを補うものだ。

### メモリ階層（active / archived / frozen）

| 層 | デフォルトウィンドウ | 挙動 |
|---|---|---|
| **active** | 1 年未満 | デフォルトのクエリ対象——すべての skill は active 層の結果を返す |
| **archived** | 1〜2 年 | `--tier=archived` または `--tier=all` でアクセス |
| **frozen** | 2 年超 | コールドストレージ——auto-dreaming が定期的に再訪する |

階層は `published_at`（フォールバックは `ingested_at`）から**その場で計算**され、frontmatter
に書き込まれることは決してない——閾値を変えれば即座に反映される。あるページの層 = そのページが
参照するすべてのソースのうち最も新しい層。`tier_override:` で手動 pin もサポートしている。

```bash
/kata:wiki-tier --show
/kata:wiki-tier --preview --set-active=540d
/kata:wiki-tier --pin=concepts/attention.md:active
```

### カスタム frontmatter 次元

SCHEMA.md の `custom_dimensions:` ブロックは、ドメイン固有の frontmatter フィールドを宣言する
——ソフトウェアプロジェクトの `version:`、研究論文の `venue:` のように。各次元には型、説明、
`refresh_on` スケジュール（いつユーザーにこの値を聞き直すべきか）がある：

```yaml
custom_dimensions:
  - name: version
    type: string
    required: true
    refresh_on: [ingest, import]
```

`wiki-ingest`/`wiki-import` は `refresh_on` に従ってプロンプトを出す（`--set key=value` で
プロンプトをスキップ）；`wiki-digest` は陳腐化した値にマークを付ける；`wiki-lint` は完全性と
列挙値の範囲を検証する；`wiki-graph --query` / Obsidian Dataview はこれらを通常の
frontmatter としてクエリできる。

### auto-dreaming：眠っている間 wiki は何をしているか

凍結されたコンテンツは永遠に凍ったままである必要はない——買収された企業、復活したアーキテクチャ、
再び引用されるようになった古典的な論文。`wiki-dream` は周期的に（あるいはあなたが設定した
ペースで）実行され、読むのは `log.md` + ページの frontmatter の日付（`ingested_at`/`updated`）
だけで、**ファイルの mtime やチャットセッションを読むことは決してない**。そのため `git clone`
すればどのマシンでも同じ dreamer の挙動を再現できる。v1.6 は `co-occurrence` 戦略を使い、
Precision ≥ 0.7、recall ≥ 0.5 が CI で gate されている。他の戦略（citational/structural/
temporal）は v1.8+ に持ち越されている。dogfood の記録は `docs/dogfood-v1.6.md` にあるが、
その retrospective の章は一度も回填されていない——上の「できないこと」を参照。

```bash
/kata:wiki-dream                          # dreaming/{date}.md に出力される
/kata:wiki-dream --apply --pages 1,3,5    # 選んだ候補を復活させる
```

### 外部フォールバックプラグイン

`wiki-query` がローカルで答えを見つけられない場合、`.wiki-plugins.yaml` に登録された外部
ツールを呼び出すことができる：

```yaml
plugins:
  - name: deepwiki-cli
    trigger: on_empty
    auto_run: false          # デフォルトでは argv を表示し、確認を求める
    argv: ["deepwiki-cli", "search", "--repo={repo_path}", "--query={query}"]
```

流れ：query が miss する → プラグインコマンドを実行 → stdout を `raw/external/` に保存 →
`wiki-ingest` が処理 → wiki ページが増える → 以後のクエリはまずローカルにヒットする。マニフェスト
の完全なフォーマットは [`plugin/PLUGINS.md`](plugin/PLUGINS.md) を参照。

### 設計の系譜：Karpathy を出発点に、このプラグインが加えたもの

| 拡張 | 何を加えたか |
|---|---|
| **SCHEMA.md を権威ある設定として** | すべての取り決めを 1 つのファイルに一元化し、agent が読み取って実行する。ハードコードではなく |
| **対話形式のドメイン起動** | `wiki-init` がドメイン（研究/書籍/業務/個人）に応じて適した分類を提案する |
| **一括インポート**（`wiki-import`） | Obsidian/Notion/Confluence/フォルダから 5 段階で移行、レジューム対応 |
| **構造化グラフクエリ**（`wiki-graph`） | frontmatter フィルタ、BFS 近傍探索、最短経路、hub/孤立ページ——永続的なグラフ DB は維持しない |
| **3 層のメモリ経年化** | active/archived/frozen、ソースの日付からその場で計算 |
| **外部フォールバックプラグイン** | 任意の CLI ツールを `wiki-query` のフォールバックとして登録し、閉ループの ingest を通る |
| **多形式のクエリ出力** | markdown / table / slides（Marp）/ chart（matplotlib）/ canvas（Obsidian） |

意図的にやらなかったこと：**永続的なグラフ DB**（ファイルシステムそのものがグラフであり、
数百ページのスキャンはミリ秒単位で済む）；**凍結コンテンツの自動削除**（frozen ＝ 一時保管で
あって削除ではない）；**embedding ベースの意味検索**（qmd に任せる。内蔵の 3-pass スキャンは
Karpathy の言う ~100 ソースというスイートスポットをカバーする）；**マルチユーザー権限制御**
（wiki はただの git リポジトリであり、ブランチと PR で協業する）。

## ワークフローへの組み込み

kata のドキュメント閉ループ（ingest → 相互リンク → query → 回填）はそれ自体で閉じているが、
3 本の延長線がそれぞれ「閉ループの外で何が漏れているか」という問題を解決する。

### セッション後に洞察を chat の中で腐らせない（wiki-session-ingest）

2 時間のデバッグの後、本当に価値のあるもの——根本原因、却下された代替案、意思決定の境界——は
すべてセッションの記録の中にあり、書き留めようと思い出す頃にはもう半分忘れている。
`wiki-session-ingest` は現在のセッションを読み、確信度に応じて知識点の候補をランク付けし、
残したいものを複数選ばせ、標準の `wiki-ingest` パイプラインを 1 つずつ通して wiki に蒸留する。

```bash
/kata:wiki-session-ingest          # 増分：前回キャプチャ以降の新規メッセージのみを見る（v2.14.0+）
/kata:wiki-session-ingest --full   # 最初のメッセージから強制的に再スキャン
```

Claude Code / Codex CLI（JSONL transcript アダプタ、自動）に対応し、Gemini / Copilot /
OpenCode / Kimi など任意の他の CLI にも対応する（LLM-dump フォールバック）。生のセッション
dump は wiki リポジトリ内の markdown であり、`wiki-sync` に乗って運ばれる——セッションに
秘密情報が含まれる場合は、同期する前に自分の目で確認すること。

### spec コーパスを衝突させない（wiki-spec）

Spec-driven development を半年続けると、あるドメインで今どの spec が権威なのか誰も言えなく
なり、新しい spec が気づかぬうちに古いものと重複し、とっくにアーカイブされているべき古い
spec がまだ参照され続けている。`wiki-spec` は ingest フローに 2 つのチェックポイントを
追加する：

```bash
/kata:wiki-spec preflight raw/new-spec.md   # Phase 0：関連する既存 spec をスキャン、advisory
/kata:wiki-ingest raw/new-spec.md           # preflight + Phase 2 enforcement を自動実行
```

著者は新しい spec の frontmatter の中で、一連の語彙——`supersedes`/`refines`/`extends`/
`parallel`/`contradicts`——を使って関係を宣言する。これらの関係はクエリ可能なグラフに入り、
`wiki-graph --mode spec-history` が血統を ASCII ツリー/JSON/Mermaid にレンダリングできる。
**Phase 3（自動伝播）はデフォルトで無効**——上の「できないこと」を参照。wiki 間の spec 関係は
`kata://<peer>/<path>` でフェデレーション peer を指すことができる（次のセクションを参照）。

### kata を実際のコーディングパイプラインに接続する（wiki-skill-create）

kata のドキュメント閉ループはそれ自体で閉じるが、**本当の作業**——ソースコードを検索する、
コードを変更する、テストを走らせる、検証する——は閉ループの外で起きており、kata の知識を
持ち帰るかどうかは個人の自覚まかせになる。`wiki-skill-create` は**プロジェクトローカルの
skill** を生成し、kata の query/ingest をこのプロジェクトの実際の作業パイプラインに溶接する：

```bash
/kata:wiki-skill-create
```

4 つの MVP モードから、プロジェクトで実際に発生している作業の形に合うものを選ぶ：

| モード | 組み込まれるループ |
|---|---|
| `issue-fix` | 問題 → kata クエリ → ソースコード検索 → 最小限の変更 → テスト → 人手による検証 → wiki-ingest |
| `feature-build` | 要件 → kata クエリ → spec 草稿 → `wiki-spec preflight` → 実装 → 検証 → spec と実装の両方の知見を回填する |
| `bug-debug` | Bug → 再現 → kata 検索（症状でもメカニズムでも）→ 根本原因 → 修正+回帰テスト → 根本原因を中心とした知見として回填 |
| `custom` | 自分自身のループを記述する → kata が query / 人手による確認 / 回填の 3 段階でそれを包む |

**補足情報をどこで探すか（v2.15.1）。** プロジェクトのワークフローの途中で調べ物をしていて、
kata のローカルでは答えが出せない場合、`--supplement-action <source-search|web-search|
doc-lookup|custom>` が次にどこを探すかを決める：`source-search` はプロジェクトのソースコード
を調べ、`web-search` はネット検索し、`doc-lookup` はプロジェクトのドキュメントを調べ、
`custom` は `--var` で `CUSTOM_SUPPLEMENT_*` 変数を渡してカスタマイズする必要がある。
指定しない場合は `suggested_supplement_action` のヒューリスティックがデフォルト値を選ぶ——
プログラミング言語スタックを検出すれば `source-search` を推奨し、`docs/` ディレクトリが
あれば `doc-lookup` を推奨し、純粋な markdown プロジェクトなら `web-search` を推奨し、
どれにも当てはまらなければ推奨せずユーザーに選ばせる。このステップが 4 つのモードのどこに
挿入されるかはそれぞれ異なる——orchestrator はこれを **Phase 2.5** と呼んでいる：
`issue-fix` ではステップ 3、`bug-debug` ではステップ 3.5、`feature-build` と `custom` では
ステップ 2.5 で、たいてい kata クエリの後、実際にコードを変更し始める前に位置する。

生成された SKILL.md は `<project>/.claude/skills/<name>/SKILL.md` に置かれ（`--target codex`
を指定すると `~/.codex/skills/` に書き出される）、自動検出された技術スタック（npm/cargo/
pytest/go test など）とプロジェクト名がその 7 ステップループに書き込まれる。レンダリング後は
**9 項目の静的検証**（frontmatter がパース可能、必須フィールドが揃っている、name の書式、
frontmatter が 1024 文字以下、description が "Use when" で始まる、三人称、sentinel
コメントが存在する、未解決の `{{VAR}}` がない、user-invocable の場合 `argument-hint` が
存在する）が走る——検証に通らなくても自動修正はされず、ユーザーが見て直すことになる。

## 複数マシンと wiki 間連携

### 同じ wiki を複数マシンで（wiki-sync）

v1.8 で `wiki-sync` が追加された：`log.md` 用のカスタム merge driver（union+sort、
canonical hash による重複排除）、ローカル同期ロック、force-push 検知（fetch 前後の
`origin/<branch>` の SHA 祖先関係を比較）、wiki 身元検証（`wiki_id` の UUID が一致しなければ
即座に abort）、そしてリポジトリ外に置かれる per-machine 同期レポート
（`~/.kata/sync-reports/`、自己衝突を避けるため決して wiki リポジトリの中には置かない）。

```bash
/kata:wiki-init --path ~/.llm-wiki/myproject --enable-sync
cd ~/.llm-wiki/myproject && git init -b main && git add . && git commit -m "wiki: init"
git remote add origin git@github.com:you/myproject-wiki.git && git push -u origin main

# 2 台目のマシン
git clone git@github.com:you/myproject-wiki.git ~/.llm-wiki/myproject

/kata:wiki-sync              # 対話形式：ロック + driver + fetch + merge + push
/kata:wiki-sync --dry-run    # プレビュー、副作用なし
```

設計プロセスは [`docs/PRD-v1.8-sync.md`](docs/PRD-v1.8-sync.md) を参照（v1 初稿 + v2〜v7
の**6 ラウンド**にわたる LLM 横断レビュー、42 件の finding が収束、2026-05-07 に
MVP ready）。`dreaming/` には現時点でまだ merge driver がない——2 台のマシンが同じ日に
`wiki-dream` を実行すると、通常の git コンフリクトが発生する。避ける方法は、dream の cron
を 1 台のマシンだけで実行することだ。

### 同じマシンで複数の wiki を

```
~/.llm-wiki/
├── common/     # デフォルトのフォールバック
├── necall/     # プロジェクト A
└── research/   # プロジェクト B
```

パス解決の優先順位（高い順から低い順へ）：明示的な `--path`/`--wiki` → `WIKI_PATH` 環境変数
→ カレントディレクトリがすでにどこかの wiki ルート内にある → `LLM_WIKI_PROJECT` →
プロジェクトルートに最も近い `.llm-wiki.yaml`/`.kata.yaml` バインドファイル → グローバルな
`~/.llm-wiki/registry.yaml` → git リポジトリ名によるフォールバック → legacy 設定 →
`~/.llm-wiki/common`。

`.llm-wiki.yaml` は**単一パスのキャッシュ**——1 つのファイルは 1 つの wiki ルートにしか
バインドできず、`wiki_path:` を複数行書いても無効で、最後の 1 行しか認識されない。複数の
wiki を共存させるには次の 2 つのどちらかが推奨される：各プロジェクトリポジトリごとに独自の
`.llm-wiki.yaml` を置く（monorepo に submodule を重ねる場合、cwd により近いバインドが
勝つ）、または全域の `~/.llm-wiki/registry.yaml` を 1 つ保守する。`.llm-wiki.yaml` は
各マシンのローカル状態に属し、git リポジトリの中では `.gitignore` すべきである；
`registry.yaml` も同様にリポジトリの外に置く。

**この解決チェーンには天花板（上限）がない**——上の「できないこと」を参照。

### wiki 間の読み取り専用フェデレーションクエリ（federation）

v1.12 により、kata は MCP server（`wiki-mcp-server`）としても、他の kata に問い合わせる
MCP client（`wiki-federate`）としても機能するようになった。各 wiki は自分のルート
ディレクトリで peer を宣言する：

```yaml
# {wiki_path}/.federation.yaml
peers:
  - name: necallkit
    wiki_id: 7b52f6df-d7cf-47ab-b980-6042cf3a675c
    endpoint: stdio
    command: ["py", "-3", "path/to/kata/plugin/scripts/mcp_server.py", "--wiki", "~/.llm-wiki/NECallKit"]
    enabled: true
    timeout_seconds: 5
```

```bash
/kata:wiki-federate search "F011 merge-back"   # まずローカルを実行し、次に有効化された peer へ並列に fan-out する
/kata:wiki-federate peers                       # 登録された peer を一覧表示する
/kata:wiki-federate resolve "kata://necallkit/decisions/F011.md"
```

結果は `kata://<peer-name-または-wiki_id>/<path>` という URI で参照される。日常的には名前
形式（可読）を使い、マシンをまたいだ長期的な参照（例えば `spec_relationships:` の中など）
には `wiki_id` 形式（peer の改名に対してより頑健）を使う。安全境界：**境界を越えては
読み取り専用**——peer の MCP server が公開するのは `wiki-search`/`wiki-graph` の読み取り
専用サブセットと `wiki-spec-preflight` のみで、書き込み系の skill がフェデレーション越しに
公開されることはない；**接続のたびに身元検証を行う**——peer が申告する `wiki_id` が
`.federation.yaml` に登録されたものと一致しなければ、その peer を拒否する；**推移的な解決は
ない**——A が B を参照し、B がさらに C を参照していても、A は自動で C まで追いかけない；
peer に到達できない/タイムアウトする/`wiki_id` が一致しない、いずれの場合もローカルの
クエリを失敗させることはなく、返される結果の `federation` 診断ブロックにのみ反映される。
クエリの内容はそのまま各 peer に送られる——機密性の高いクエリには `--no-federate` を
使うこと。

## リファレンス

**Works with：** Claude Code（`.claude-plugin/`）、Codex CLI（生成された skills）、任意の
LLM（`SKILL.md` を system prompt として）、GitHub Copilot CLI（ルート直下の `plugin.json`）、
Obsidian（wiki はそのまま vault になる：`[[wikilinks]]`、Graph view、Dataview で
frontmatter をクエリ、Web Clipper が `raw/articles/` に保存、Marp が
`wiki-query --format=slides` をレンダリング）。wiki はデフォルトで git リポジトリであり、
`wiki-init` の最後のステップで `git init` を提案する。

**Scaling：** 100 ページ未満は内蔵の `wiki-search` で十分；100〜500 ページなら `wiki-lint`
をこまめに走らせて `index.md` を新鮮に保つ；500〜2000 ページなら
[qmd](https://github.com/tobi/qmd)（BM25 + ベクトルのハイブリッド + LLM 再ランキング、
`wiki-search` が自動検出して shell out する）を導入；2000 ページ以上は qmd の MCP server
モードを使う。

**ドキュメント索引：**

- [`docs/PRD-v1.8-sync.md`](docs/PRD-v1.8-sync.md) — マルチマシン同期の設計
- [`docs/PRD-v1.12-cross-wiki-federation.md`](docs/PRD-v1.12-cross-wiki-federation.md) — フェデレーションの設計
- [`docs/PRD-v1.13-spec-history-management.md`](docs/PRD-v1.13-spec-history-management.md)、
  [`docs/PRD-v1.14-spec-propagation-reconcile.md`](docs/PRD-v1.14-spec-propagation-reconcile.md) — spec 履歴管理
- [`docs/PRD-v1.15-work-loop-bridge.md`](docs/PRD-v1.15-work-loop-bridge.md) — work-loop bridge
- [`docs/dreaming.md`](docs/dreaming.md)、[`docs/watcher.md`](docs/watcher.md) — auto-dreaming / watcher の設計
- [`plugin/PLUGINS.md`](plugin/PLUGINS.md) — 外部フォールバックプラグインのマニフェスト形式
- 各 skill の完全な挙動はそれぞれの `plugin/skills/<name>/SKILL.md` を正とする——README が扱うのは位置づけとよく使う使い方だけである

**Contributing：**

```bash
git config --local core.hooksPath .githooks   # pre-commit smoke test を有効化する
python tests/run_smoke.py                      # 手動で一度実行する、CI と同じ内容
python scripts/build_skill_md.py               # 新しい skill を追加した後に SKILL.md のまとめ表を再生成する
```

## Origin

コンセプトは [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
（2025 年 5 月）に由来する。プラグインの設計パラダイムは
[SpecTeam](https://github.com/litianyi-007/SpecTeam) を参考にした。

このプラグインの目標は、Karpathy が意図的に余白を残した構想に対する**忠実で、主張のある実装**
を作ることだ。原文は「上記のすべてはオプションであり組み合わせ自由」と述べている。私たちは
具体的な選択をした（SCHEMA.md を単一の設定として、対話形式のドメイン起動、3 層のメモリ
経年化）一方で、核となる不変条件は保持した：ファイルシステムが唯一の真実源であること、raw は
不変であること、人間がキュレーションし LLM が保守すること、知識は一度コンパイルされたら
継続的に複利で育つこと。

License: MIT. [LICENSE](LICENSE) を参照。
