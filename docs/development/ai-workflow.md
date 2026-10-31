# AI開発フロー(三層オーケストレーション)

この repo の AI 開発の役割分担と固有値だけを置く薄い doc。

## 役割

| 役割 | 担当 | 現行割当(2026-10-31、差し替え可) |
|---|---|---|
| 設計レビュー役 | 構想レビュー、設計指示書の確定、DRBFM・全通り試験の設計、最終レビュー | Fable |
| 段取り役 | 壁打ち、たたき台、設計レビュー役への依頼、構築役への分配、統合検証 | Opus |
| 構築役 | 確定した指示書どおりの実装・横展開・テスト | Sonnet(定型・大量作業は Haiku) |

何を・なぜ・どの優先度で作るかの最終決定は owner(devuser)が持つ。

## 流れ

構想(未整理でも全部出す) → たたき台 → 設計レビュー → 設計指示書 → 構築 → 統合検証

## この repo の固有値

| 項目 | 内容 |
|---|---|
| base branch | `main` |
| テスト実行 | `python -m pytest tests` |
| docs 言語 | 日本語 |
| 承認者 | devuser |
| エージェントの書込権限 | read-only 扱い(codex の ACL はあるが、.git に書くと devuser の権限が壊れるため使わない)。patch handoff で渡し、適用・push は devuser |

## 正本

詳細・改訂は `brantechs/templete-project` の `docs/development/ai-workflow.md` と `docs/pm/model_orchestration_rules.md` §2.1 に従う。

<!-- canon: brantechs/templete-project docs/development/ai-workflow.md v=20261031 -->
