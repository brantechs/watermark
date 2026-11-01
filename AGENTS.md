# AGENTS.md

`watermark`(Watermark Discord Bot)で作業するコーディングエージェント向けの作業ルール。

## 基本

- ユーザーへの報告は日本語で行う。
- 作業前に `docs/README.md` を読む。推測だけで実装せず、実際の repo 内容を読む。
- `.env` 実ファイルを読まない。secret / token / credential を chat・Git・ログに出さない。
- `git add .` を使わない。push / PR 作成はユーザーが明示的に求めた場合のみ。

## 試験資産ライフサイクル(Testing)

`docs/development/test-asset-lifecycle-policy.md` に従う。

- 変更のバージョン区分(patch / minor / major)を先に決める。patch / minor は DRBFM(故障モード想定)→ 全通り試験 → 証跡、major は試験棚卸(思想・観点の蒸留 → 再構成)→ フルテスト。
- DRBFM と全通り試験の設計は高級モデル(Fable 等)が担当する。DRBFM なしで仕様変更を実装しない。
- 開発中に書いたテストは test-case master に登録して捨てない。既存テストの削除・skip 化は棚卸でのみ行う。
- 人間がプロンプトで与えた指示・判断・訂正・却下は `docs/development/dev-intent/<ticket-id>.md` に証跡として残し、読み取った意図を試験へ結ぶ。
- 既存の開発思想・設計原則と異なる観点が必要になったら STOP し、設計者(明記がなければ devuser)に問い合わせてから進める。
- 作業開始時に `scripts/install-githooks.sh` を1回実行する(pre-commit で `scripts/qa-gate.sh` が DRBFM・開発意図ログ・evidence・test-case master の有無とテスト削除なしを判定)。コード確定後に `/security-review`(Codex は SQA `prompts/security-review.md`)→ `docs/development/evidence/<ticket>/security-review.md` → `scripts/qa-gate.sh security-stamp`、commit 前に `scripts/qa-gate.sh change --write` を通す。`--no-verify` は使わない。
- 手順・テンプレート・チェックリストは `brantechs/SQA`(`checklists/change-test-gate.md` / `checklists/pre-major-test-inventory.md`)。

## AI開発フロー(三層オーケストレーション)

`docs/development/ai-workflow.md` に従う(正本: `brantechs/templete-project` の `docs/pm/model_orchestration_rules.md` §2.1)。

- 構想は未整理でも全部出す。段取り役(現行: Opus)が論点に整理してたたき台を作る。
- minor 以上・複数 repo・ルール変更・安全規則に触れる変更は、設計レビュー役(現行: Fable)のレビューを経て設計指示書を確定する。上位モデルが使えない環境では、設計ファイルを渡して結果を受け取るレビュー依頼 handoff で代える。
- 構築役(現行: Sonnet。大量の定型作業は Haiku)は確定した指示書の範囲だけを実装し、段取り役が統合検証する。
- 上位モデルにはたたき台・論点・根拠の抜粋(path:行)だけを渡し、全文や全文差分を渡さない。
- 何を・なぜ・どの優先度で作るかの最終決定は owner(人間)が持つ。
