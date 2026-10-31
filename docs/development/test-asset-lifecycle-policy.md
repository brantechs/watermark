# 試験資産ライフサイクル方針

## 1. この repo の前提

| 項目 | 内容 |
|---|---|
| repo | Watermark Discord Bot(`watermark`) |
| base branch | `main` |
| バージョン正本 | git tag `vX.Y.Z`(未採番) |
| テスト実行手段 | `python -m pytest tests` |
| QA 成果物の置き場 | `docs/development/` 配下(drbfm / test-cases / evidence / qa-review / dev-intent / test-inventory)。配置規約は SQA `docs/integrations/target-repositories.md` |

手順・テンプレート・チェックリスト・プロンプトは `brantechs/SQA`(sqa-agent)が正本。雛形の適用方針は `brantechs/templete-project` の `docs/development/test-asset-lifecycle-policy.md`。本書はこの repo への適用条件だけを定める。

## 2. 原則

```text
1. 開発途中で作成するテストは、捨てずに資産(test-case master + テストコード + 証跡)として積み上げる。
2. メジャーバージョンアップではフルテスト(全 active 試験)を実施する。
3. マイナーアップデートを含む機能追加・仕様変更では、故障モードを想定して DRBFM を作成し、
   DRBFM から全通り試験(故障モード × 条件)を導出し、証跡を残しながらクリアすることを確認する。
4. メジャーアップデート直前に試験を棚卸する。各試験の「思想・観点」を蒸留してから再構成し、抜け漏れを防ぐ。
5. これまでの開発思想と異なる観点からの実装・更新が必要になったら、設計者に問い合わせる。
6. 開発中に人間がプロンプトで与えた指示・判断・訂正・却下は開発意図ログとして残し、意図を蒸留して指針・試験の方向性にする。
```

## 3. バージョン区分と必須成果物

| 区分 | 典型 | 必須 |
|---|---|---|
| patch | 不具合修正・文言・依存更新 | DRBFM(軽量可)→ 変更由来の全通り試験 + 既存テスト全件 + evidence + QA Review |
| minor | 機能追加・仕様変更・互換を保つ変更 | DRBFM → 全通り試験 + 既存テスト全件 + 関連 manual / semi_auto + test-case master 差分 + evidence + QA Review |
| major | 互換性を壊す変更・大規模刷新・`0.x` → `1.0.0` | 試験棚卸(蒸留 → 再構成)→ フルテスト(全 active 項目)→ evidence(`v<MAJOR>.0.0`)→ release judgement |

- 区分は DRBFM 作成前に高級モデル(Fable 等)が決め、DRBFM front matter `version_tier` と実装指示書に書く。決められないときは devuser に確認する(STOP)。
- `0.x` の間は `0.Y` 上げを minor とする。破壊的変更を含むときは設計者判断で major 扱いにできる。

## 4. チケット実装フロー

```text
1. Issue / docs 確認
2. バージョン区分(patch / minor / major)を決める。major なら §6 へ
3. 高級モデル(Fable 等)が DRBFM を作成(docs/development/drbfm/<YYYYMMDD>-<ticket>-<title>.md)
4. 高級モデルが DRBFM から全通り試験を設計し、指示書に test_case_id 一覧として含める
5. 作業ブランチ作成(main 起点)
6. 実装(人間の指示・判断・訂正・却下は docs/development/dev-intent/<ticket>.md に記録)
7. test: 全通り試験 + 既存テスト全件(`python -m pytest tests`)。失敗は STOP
8. 開発中に書いたテストを docs/development/test-cases/master/<feature>.yaml に登録(資産化)。削除・skip 化はしない
9. evidence(docs/development/evidence/<ticket>/)を残し、開発意図ログの指針を DRBFM 行 / test case に結ぶ
10. QA Review(SQA checklists/change-test-gate.md で自己点検。未達は review_required)
11. commit → devuser が push / PR
```

## 5. 試験資産の積み上げ

- 実装中に書いたテスト・再現スクリプト・確認手順は、チケット完了時に test-case master へ登録する。登録しないものは `docs/development/test-cases/artifacts/<ticket>/` に理由付きで残す。
- 既存テストの削除・`skip` / `xfail` 化・コメントアウトはチケット作業中に行わない。必要なら棚卸(§6)に回し、`status: deprecated` + 理由にする。
- `test_case_id`(`TC-WMK-<連番>`)は再利用しない。再構成で置き換えたときは `supersedes` で旧IDへ結ぶ。
- 開発意図ログ(SQA `templates/dev-intent-log.md`): 人間の入力を要旨で記録し、読み取った意図と反映先を書く。secret・個人情報・顧客名は書かない。

## 6. メジャー直前の棚卸と最適化

```text
1. 凍結: test-case master / テスト / DRBFM / dev-intent のコミットを固定
2. 蒸留: 各試験の思想・観点・由来を1行ずつ書き出す(SQA prompts/test-intent-distill.md)。
   全チケットの開発意図ログを読み、繰り返し現れる人間の意図を指針として書き出す
   → docs/development/test-inventory/intent-register.md(観点 + 指針)
   高級モデル(Fable 等)のレビューと人間入力の蒸留の両方を入力にする
3. 分析: 重複・欠落・陳腐化・偏り、指針に対して手薄な領域(試験の方向性)
4. 再構成: 観点ごとに最小の試験集合へ。旧IDは deprecated、新IDは supersedes
5. フルテスト: 全 active 項目を must。evidence を docs/development/evidence/v<MAJOR>.0.0/ へ
6. release judgement(SQA checklists/release-judgement.md)
```

チェックリスト: SQA `checklists/pre-major-test-inventory.md`。報告: `docs/development/test-inventory/<YYYYMMDD>-v<MAJOR>-inventory.md`。

## 7. 開発思想と異なる観点が出たとき(設計者への問い合わせ)

次に当たる変更は着手前に STOP し、設計者(docs に明記がなければ devuser)へ問い合わせる。

```text
- この repo の docs(requirements / architecture / DESIGN.md / 運用方針)の原則と異なる方針を取る
- 既存の試験観点や指針を否定・無効化する
- 既存 test case を失敗のまま deprecated にしようとする
- 外部仕様(API 契約 / 帳票 / 出力物 / 配布物の動作条件)の互換を壊すのに major 判定になっていない
```

乖離点を「現行の思想 / 提案する観点 / 影響する試験・観点」で書き、`review_required: true` + `design_philosophy_deviation` を付け、回答を docs と開発意図ログに反映してから再開する。回答が思想を変えるなら major 候補として §3 で再判定する。

## 8. 関連

- SQA 正本: `docs/development/test-asset-lifecycle-policy.md`、`checklists/change-test-gate.md`、`checklists/pre-major-test-inventory.md`、`prompts/test-intent-distill.md`、`templates/dev-intent-log.md`、`templates/test-intent-register.md`、`templates/test-inventory-report.md`
- 本 repo: [dev-intent/](dev-intent/README.md)(開発意図ログ)、[test-inventory/](test-inventory/README.md)(試験観点台帳・棚卸報告)
