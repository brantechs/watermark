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
- 手順・テンプレート・チェックリストは `brantechs/SQA`(`checklists/change-test-gate.md` / `checklists/pre-major-test-inventory.md`)。
