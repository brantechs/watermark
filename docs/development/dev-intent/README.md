# dev-intent(開発意図ログ)

チケットごとに、開発中に人間がプロンプトで与えた指示・判断・訂正・却下・回答を証跡として残す。
ファイル名は `<ticket-id>.md`、雛形は SQA `templates/dev-intent-log.md`。方針は [../test-asset-lifecycle-policy.md](../test-asset-lifecycle-policy.md) §5。

- 会話ログ限りにしない。要旨と「読み取った意図」、反映先(DRBFM 行 / test case / 観点)を書く。
- secret・個人情報・顧客名は書かない。
- メジャー前の棚卸で全ログを蒸留し、繰り返し現れる意図を指針として `../test-inventory/intent-register.md` に書く。
