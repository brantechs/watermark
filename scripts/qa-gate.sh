#!/usr/bin/env bash
# qa-gate.sh — 試験資産ライフサイクル方針の機械チェック(change-test-gate の自動化部分)
#
# 正本: docs/development/test-asset-lifecycle-policy.md(この repo)/ brantechs/SQA checklists/change-test-gate.md
# 依存: bash + git のみ。言語・フレームワークに依存しない。
#
# 使い方:
#   scripts/qa-gate.sh change [--base <ref>] [--ticket <id>] [--branch <name>] [--staged] [--write]
#   scripts/qa-gate.sh major  [--version vX.Y.Z]
#   scripts/qa-gate.sh security-stamp [--base <ref>] [--ticket <id>] [--staged]
#   scripts/qa-gate.sh code-digest    [--base <ref>] [--staged]
#
#   change : ブランチ(または index)の差分に対して、コード変更があるなら
#            DRBFM(version_tier 付き)/ 開発意図ログ / evidence / test-case master 差分 / セキュリティレビュー があり、
#            既存テストの削除・skip 化がないことを確認する。docs だけの変更は gate 対象外(PASS)。
#   major  : vX.0.0 の直前に、試験棚卸(観点台帳・棚卸報告)/ フルテスト evidence / 全体セキュリティレビュー / release judgement があることを確認する。
#   security-stamp : セキュリティレビュー(Claude Code /security-review、Codex は SQA prompts/security-review.md)を実施した後に実行する。
#            evidence/<ticket>/security-review.md が無ければ雛形を作り、front matter に reviewed_code_digest(今回の差分に含まれる
#            コードファイルの blob digest)/ reviewed_at / reviewed_head を刻印する。レビュー後にコードが変わると digest がずれ、
#            change モードが「レビューが古い」として FAIL する。status: reviewed は人間(または実施したモデル)が所見を書いた上で付ける。
#   code-digest : 現在の差分の digest を表示するだけ(確認用)。
#
# 終了コード: 0 = PASS, 1 = FAIL, 2 = 使い方エラー
# 環境変数:
#   QA_GATE_SKIP=1              ゲートを通さず exit 0(WIP 用。stderr に警告。CI では使わない)
#   QA_GATE_ALLOW_TEST_REMOVAL=1 既存テストの削除・skip 化を許可(棚卸 docs/development/test-inventory/ の差分が同時にあること)
#   QA_GATE_BASE=<ref>          --base の既定値
#   TICKET_ID=<id>              --ticket の既定値
set -uo pipefail

MODE="${1:-}"; shift || true
BASE="${QA_GATE_BASE:-}"; TICKET="${TICKET_ID:-}"; BRANCH=""; STAGED=0; WRITE=0; VERSION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;
    --ticket) TICKET="$2"; shift 2;;
    --branch) BRANCH="$2"; shift 2;;
    --version) VERSION="$2"; shift 2;;
    --staged) STAGED=1; shift;;
    --write) WRITE=1; shift;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
case "$MODE" in change|major|security-stamp|code-digest) ;; *) echo "usage: qa-gate.sh change|major|security-stamp|code-digest [options]" >&2; exit 2;; esac

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 2; }
cd "$ROOT"
FAIL=0; REPORT=()
pass() { REPORT+=("[PASS] $*"); echo "[PASS] $*"; }
fail() { REPORT+=("[FAIL] $*"); echo "[FAIL] $*"; FAIL=1; }
note() { REPORT+=("[INFO] $*"); echo "[INFO] $*"; }

if [ "${QA_GATE_SKIP:-0}" = "1" ]; then
  echo "[WARN] QA_GATE_SKIP=1: gate bypassed (WIP). CI では通らない。" >&2; exit 0
fi

# ---------- 共通: ブランチ名 / チケット ID ----------
[ -n "$BRANCH" ] || BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
derive_ticket() {
  local b="$1" t=""
  if [[ "$b" =~ ^[a-z]+/([A-Za-z][A-Za-z0-9]*-[0-9]+) ]]; then t="${BASH_REMATCH[1]}"
  elif [[ "$b" == */* ]]; then t="${b#*/}"; t="$(echo "$t" | sed -E 's/-[0-9]{8}$//')"
  else t="$b"; fi
  echo "$t"
}
[ -n "$TICKET" ] || TICKET="$(derive_ticket "$BRANCH")"
# ticket は evidence / dev-intent のパスに使うので、英数・._- 以外(/ や ..)は受け付けない(パス外への書き込み防止)
if [ "$MODE" != "code-digest" ] && ! [[ "$TICKET" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && "$TICKET" != *..* ]]; then
  echo "ticket id が不正: '$TICKET'(英数と . _ - のみ。ブランチ名から導けないときは --ticket <id> で指定)" >&2; exit 2
fi

TEST_PATH_RE='(^|/)(tests?|__tests__|e2e|spec)/|(^|/)test_[^/]*\.py$|_test\.(py|go|rs)$|\.(spec|test)\.(ts|tsx|js|jsx|mjs|cjs)$'
# docs と gate 基盤(hook / CI 設定 / qa-gate 自身)はプロダクトコードではないので gate 対象外
DOCS_ONLY_RE='^(docs|checklists|prompts|snippets)/|\.(md|txt)$|^LICENSE|^\.githooks/|^\.github/|^scripts/(qa-gate|install-githooks)\.sh$'
# セキュリティレビューの鮮度 digest からは docs だけを除く。gate 基盤(hook / CI 設定 / qa-gate 自身)は commit ごとに実行されるコードなので、
# レビュー後に書き換えられたら「古い」と判定させる(artifact 要求の対象外でも digest には含める)
DIGEST_EXCLUDE_RE='^(docs|checklists|prompts|snippets)/|\.(md|txt)$|^LICENSE'
SKIP_MARK_RE='pytest\.mark\.(skip|xfail)|@unittest\.skip|unittest\.SkipTest|\b(it|test|describe)\.skip\(|\b(xit|xtest|xdescribe)\(|@pytest\.mark\.skipif|#\[ignore\]'

# ---------- 共通: 差分の取得とコード digest ----------
MB=""; DIFFARGS=()
resolve_diff() {  # BASE を決め、MB / DIFFARGS を設定する(change / security-stamp / code-digest 共通)
  if [ -z "$BASE" ]; then
    for c in origin/dev origin/develop origin/main origin/master dev develop main master; do
      [ "$c" = "$BRANCH" ] && continue
      git rev-parse --verify -q "$c" >/dev/null && { BASE="$c"; break; }
    done
  fi
  [ -n "$BASE" ] || { echo "base ref が見つからない(--base で指定)" >&2; exit 2; }
  MB="$(git merge-base "$BASE" HEAD 2>/dev/null)" || MB="$BASE"
  DIFFARGS=("$MB"); [ "$STAGED" = 1 ] && DIFFARGS=("--cached" "$MB")
}
# 差分に含まれるコードファイル(docs を除く。gate 基盤は含む)の内容 digest。
# commit hash ではなく blob で取るので、git am / rebase / cherry-pick で hash が変わっても内容が同じなら一致する。
# --staged なら index の内容、それ以外は作業ツリーの内容(= git diff が見ているもの)。削除は "deleted" で表す。
code_digest() {
  local status f blob lines=""
  status="$(git diff --name-status -M "${DIFFARGS[@]}" 2>/dev/null)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    f="$(echo "$line" | awk '{print $NF}')"
    echo "$f" | grep -Eq "$DIGEST_EXCLUDE_RE" && continue
    if [ "$STAGED" = 1 ]; then blob="$(git rev-parse -q --verify ":$f" 2>/dev/null || echo deleted)"
    elif [ -f "$f" ]; then blob="$(git hash-object "$f")"
    else blob="deleted"; fi
    lines+="$blob $f"$'\n'
  done <<< "$status"
  [ -n "$lines" ] || { echo none; return; }
  printf '%s' "$lines" | LC_ALL=C sort | git hash-object --stdin
}
sec_file() { echo "docs/development/evidence/$TICKET/security-review.md"; }
fm_value() {  # file key -> front matter の値(先頭 --- ブロック内)
  awk -v k="$2" 'NR==1&&$0!="---"{exit} NR>1&&$0=="---"{exit} NR>1{ if (index($0,k":")==1){sub("^"k":[[:space:]]*",""); print; exit} }' "$1" 2>/dev/null | sed 's/[[:space:]]*$//'
}

# ---------- change ----------
run_change() {
  resolve_diff
  local mb="$MB"; local diffargs=("${DIFFARGS[@]}")
  local status; status="$(git diff --name-status -M "${diffargs[@]}" 2>/dev/null)"
  note "mode=change base=$BASE ($mb) branch=$BRANCH ticket=$TICKET staged=$STAGED"
  if [ -z "$status" ]; then pass "差分なし"; return; fi

  local files; files="$(echo "$status" | awk '{print $NF}')"
  local code_files; code_files="$(echo "$files" | grep -Ev "$DOCS_ONLY_RE" || true)"
  # 1. 既存テストの削除・リネーム(from 側)
  local removed; removed="$(echo "$status" | awk '$1 ~ /^(D|R)/ {print $2}' | grep -E "$TEST_PATH_RE" || true)"
  # 2. skip 化(テストファイルへの追加行)
  # skip マーカーの走査は試験ソース(py/js/ts/go/rs)だけ。tests/ 配下の shell ランナーはマーカー文字列を生成し得るので除く
  local test_changed; test_changed="$(echo "$files" | grep -E "$TEST_PATH_RE" | grep -E '\.(py|go|rs|ts|tsx|js|jsx|mjs|cjs)$' || true)"
  local skips=""
  if [ -n "$test_changed" ]; then
    skips="$(git diff "${diffargs[@]}" -- $test_changed 2>/dev/null | grep -E '^\+' | grep -Ev '^\+\+\+' | grep -E "$SKIP_MARK_RE" || true)"
  fi
  local inventory_changed; inventory_changed="$(echo "$files" | grep -E '^docs/development/test-inventory/' || true)"
  if [ -n "$removed" ] || [ -n "$skips" ]; then
    if [ "${QA_GATE_ALLOW_TEST_REMOVAL:-0}" = "1" ] && [ -n "$inventory_changed" ]; then
      note "既存テストの削除・skip 化を棚卸として許可(test-inventory 差分あり): $(echo $removed | tr '\n' ' ')"
    else
      [ -n "$removed" ] && fail "既存テストの削除・リネーム(棚卸でのみ可。QA_GATE_ALLOW_TEST_REMOVAL=1 + test-inventory 差分): $(echo $removed | tr '\n' ' ')"
      [ -n "$skips" ] && fail "テストの skip / xfail 化を追加(棚卸でのみ可): $(echo "$skips" | head -3 | tr '\n' ' ')"
    fi
  else
    pass "既存テストの削除・skip 化なし"
  fi

  if [ -z "$code_files" ]; then
    pass "docs / gate 基盤のみの変更: DRBFM / evidence の gate 対象外"
    return
  fi
  note "コード変更 $(echo "$code_files" | wc -l) ファイル(例: $(echo "$code_files" | head -3 | tr '\n' ' '))"

  # 3. DRBFM + version_tier
  local drbfm; drbfm="$(echo "$status" | awk '$1 ~ /^(A|M|R)/ {print $NF}' | grep -E '^docs/development/drbfm/.*\.md$' || true)"
  local tier=""
  if [ -z "$drbfm" ]; then
    fail "DRBFM がない(docs/development/drbfm/<YYYYMMDD>-$TICKET-<title>.md を追加・更新する。雛形: SQA templates/drbfm.md)"
  else
    local f; f="$(echo "$drbfm" | grep -F -- "$TICKET" | sort | tail -1)"; [ -n "$f" ] || f="$(echo "$drbfm" | sort | tail -1)"
    tier="$(git show "HEAD:$f" 2>/dev/null || cat "$f" 2>/dev/null)"; tier="$(echo "$tier" | grep -E '^version_tier:' | head -1 | sed -E 's/^version_tier: *//; s/[[:space:]]*$//')"
    case "$tier" in
      patch|minor|major) pass "DRBFM あり: $f (version_tier=$tier)";;
      *) fail "DRBFM $f に version_tier: patch|minor|major がない(現在: '${tier:-なし}')";;
    esac
  fi
  # 4. 開発意図ログ
  local intent="docs/development/dev-intent/$TICKET.md"
  if echo "$files" | grep -qxF "$intent"; then pass "開発意図ログあり: $intent"
  else fail "開発意図ログがない: $intent(雛形: SQA templates/dev-intent-log.md。人間の指示・判断・訂正・却下を残す)"; fi
  # 5. evidence
  if echo "$files" | grep -qE "^docs/development/evidence/$TICKET/"; then pass "evidence あり: docs/development/evidence/$TICKET/"
  else fail "evidence がない: docs/development/evidence/$TICKET/(evidence-index.md + 結果。雛形: SQA templates/evidence-index.md)"; fi
  # 6. test-case master / artifacts
  if echo "$files" | grep -qE "^docs/development/test-cases/(master/|artifacts/$TICKET/)"; then pass "test-case master / artifacts の差分あり(資産化)"
  else fail "test-case master の差分がない(docs/development/test-cases/master/<feature>.yaml に登録、または artifacts/$TICKET/ に理由付きで残す)"; fi
  # 7. セキュリティレビュー(存在・鮮度・握りつぶしなし)
  check_security_review "$(sec_file)" "$(code_digest)"
  # 8. major なら棚卸チェックへ
  if [ "$tier" = "major" ]; then note "version_tier=major: 棚卸・フルテストの確認を追加"; run_major; fi
}

# ---------- セキュリティレビュー証跡の判定 ----------
# $1 = security-review.md、$2 = 期待する digest(空なら鮮度は見ない: major の全体監査)
check_security_review() {
  local f="$1" want="$2" st dg open rr
  if [ ! -f "$f" ]; then
    fail "セキュリティレビューがない: $f(/security-review(Claude Code)または SQA prompts/security-review.md を差分に実施 → 所見を書く → scripts/qa-gate.sh security-stamp)"
    return
  fi
  st="$(fm_value "$f" status)"; dg="$(fm_value "$f" reviewed_code_digest)"
  open="$(fm_value "$f" open_findings)"; rr="$(fm_value "$f" review_required)"
  if [ -n "$want" ]; then
    if [ -z "$dg" ]; then fail "セキュリティレビューに reviewed_code_digest がない: $f(scripts/qa-gate.sh security-stamp で刻印)"; return; fi
    if [ "$dg" != "$want" ]; then fail "セキュリティレビューが古い: $f の reviewed_code_digest=${dg:0:12} ≠ 現在のコード差分 ${want:0:12}(レビュー後にコードが変わった。再実施して security-stamp)"; return; fi
  fi
  if [ "$st" != "reviewed" ]; then fail "セキュリティレビューが未完了: $f の status が '${st:-なし}'(所見を書いて status: reviewed にする)"; return; fi
  case "$open" in ''|*[!0-9]*) fail "セキュリティレビューの open_findings が数値でない: $f('${open:-なし}')"; return;; esac
  if [ "$open" != "0" ] && [ "$rr" != "true" ]; then
    fail "セキュリティレビューに未解消の所見 $open 件があるのに review_required: true がない: $f(握りつぶし禁止。security_or_permission_sensitive で QA Review へ)"; return
  fi
  if [ "$open" = "0" ]; then pass "セキュリティレビューあり: $f (status=reviewed, 所見は全て解消${want:+, digest 一致})"
  else pass "セキュリティレビューあり: $f (open_findings=$open → review_required: true で QA Review へ${want:+, digest 一致})"; fi
}

# ---------- security-stamp ----------
run_security_stamp() {
  resolve_diff
  local f dg now head
  f="$(sec_file)"; dg="$(code_digest)"; now="$(date +%Y-%m-%d)"; head="$(git rev-parse --short HEAD 2>/dev/null)"
  if [ "$dg" = "none" ]; then echo "差分にコードファイルがない(docs / gate 基盤のみ)。security-stamp は不要。" >&2; exit 2; fi
  mkdir -p "$(dirname "$f")"
  if [ ! -f "$f" ]; then
    cat > "$f" <<EOT
---
type: security_review
repo: $(basename "$ROOT")
ticket_id: $TICKET
status: draft
reviewed_at: $now
reviewed_head: $head
reviewed_code_digest: $dg
reviewer: <Claude Code /security-review | Codex (SQA prompts/security-review.md) | 人間>
scope: $BASE..HEAD$([ "$STAGED" = 1 ] && echo " + index")
open_findings: 0
review_required: false
canonical_path: $f
tags: [security-review, evidence, $TICKET]
---

# Security Review: $TICKET

> 雛形: SQA templates/security-review.md / 手順: SQA docs/development/test-asset-lifecycle-policy.md §4.2
> 所見を書いたら status: reviewed にする。未解消の所見が残るなら open_findings に件数、review_required: true(握りつぶし禁止)。

## 1. 対象と観点

- 差分: (レビューしたファイル・機能)
- 観点: 入力検証 / injection(SQL・コマンド・パス・テンプレート)/ 認証・認可 / secret・個人情報の露出 / SSRF・外部呼び出し / 依存・設定(compose・nginx・workflow)

## 2. 所見

| finding_id | severity(high/medium/low/info) | 箇所 | 内容 | 対応(fixed / accepted / open) | 対応先(DRBFM 行 / test_case_id / issue) |
|---|---|---|---|---|---|
| (所見なしなら「なし」と書く) | | | | | |

## 3. DRBFM / 試験への反映

- DRBFM に追加した故障モード行:
- 追加した回帰試験(test_case_id):

## 4. 残リスク

- (accepted / open の所見と受容者)
EOT
    echo "created: $f (status: draft。所見を書いて status: reviewed にする)"
  else
    # 既存ファイルの front matter を更新(reviewed_at / reviewed_head / reviewed_code_digest)。無いキーは追記する。
    local tmp; tmp="$(mktemp "$ROOT/.qa-gate.XXXXXX")"
    awk -v now="$now" -v head="$head" -v dg="$dg" '
      BEGIN{infm=0; done=0}
      NR==1&&$0=="---"{infm=1; print; next}
      infm&&$0=="---"{ if(!seen_at)print "reviewed_at: "now; if(!seen_head)print "reviewed_head: "head; if(!seen_dg)print "reviewed_code_digest: "dg; infm=0; print; next}
      infm&&/^reviewed_at:/{print "reviewed_at: "now; seen_at=1; next}
      infm&&/^reviewed_head:/{print "reviewed_head: "head; seen_head=1; next}
      infm&&/^reviewed_code_digest:/{print "reviewed_code_digest: "dg; seen_dg=1; next}
      {print}' "$f" > "$tmp" && mv "$tmp" "$f" || { rm -f "$tmp"; echo "front matter の更新に失敗: $f" >&2; exit 1; }
    echo "stamped: $f (reviewed_code_digest=${dg:0:12}, head=$head)"
  fi
  echo "digest: $dg"
}

# ---------- major ----------
run_major() {
  local major=""
  if [ -n "$VERSION" ]; then major="$(echo "$VERSION" | sed -E 's/^v?([0-9]+)\..*/\1/')"
  else
    local tag; tag="$(git describe --tags --exact-match 2>/dev/null || true)"
    [ -n "$tag" ] && major="$(echo "$tag" | sed -E 's/^v?([0-9]+)\..*/\1/')"
  fi
  if [ -z "$major" ]; then
    # 棚卸報告のファイル名から推定(最新)
    local latest; latest="$(ls docs/development/test-inventory/*-v*-inventory.md 2>/dev/null | sort | tail -1)"
    [ -n "$latest" ] && major="$(echo "$latest" | sed -E 's/.*-v([0-9]+)-inventory\.md$/\1/')"
  fi
  note "mode=major version=${VERSION:-"(推定 v$major)"}"
  [ -n "$major" ] || { fail "対象 MAJOR を決められない(--version vX.0.0 を指定)"; return; }
  [ -f docs/development/test-inventory/intent-register.md ] && pass "試験観点台帳あり: docs/development/test-inventory/intent-register.md" \
    || fail "試験観点台帳がない: docs/development/test-inventory/intent-register.md(雛形: SQA templates/test-intent-register.md)"
  ls docs/development/test-inventory/*-v"$major"-inventory.md >/dev/null 2>&1 && pass "棚卸報告あり: $(ls docs/development/test-inventory/*-v"$major"-inventory.md | tail -1)" \
    || fail "棚卸報告がない: docs/development/test-inventory/<YYYYMMDD>-v$major-inventory.md(雛形: SQA templates/test-inventory-report.md)"
  [ -f "docs/development/evidence/v$major.0.0/evidence-index.md" ] && pass "フルテスト evidence あり: docs/development/evidence/v$major.0.0/" \
    || fail "フルテスト evidence がない: docs/development/evidence/v$major.0.0/evidence-index.md"
  check_security_review "docs/development/evidence/v$major.0.0/security-review.md" ""
  ls docs/operations/release-judgement/*v"$major".0.0*.md >/dev/null 2>&1 && pass "release judgement あり" \
    || fail "release judgement がない: docs/operations/release-judgement/<YYYYMMDD>-v$major.0.0.md(SQA checklists/release-judgement.md)"
  if [ -f docs/development/test-inventory/intent-register.md ]; then
    local gaps; gaps="$(grep -cE '\|[[:space:]]*gap[[:space:]]*\|' docs/development/test-inventory/intent-register.md || true)"
    [ "${gaps:-0}" = "0" ] && pass "観点台帳に gap(試験なしの観点)なし" || fail "観点台帳に gap が $gaps 行(観点はあるが試験がない)"
  fi
}

case "$MODE" in
  change) run_change;;
  major) run_major;;
  security-stamp) run_security_stamp; exit 0;;
  code-digest) resolve_diff; code_digest; exit 0;;
esac

echo; if [ "$FAIL" = 0 ]; then echo "QA GATE: PASS"; else echo "QA GATE: FAIL (詳細は上記。方針: docs/development/test-asset-lifecycle-policy.md)"; fi

if [ "$WRITE" = 1 ] && [ "$MODE" = "change" ]; then
  local_dir="docs/development/evidence/$TICKET"; mkdir -p "$local_dir"
  out="$local_dir/qa-gate.md"
  # 区切りの空行は追記時に先頭へ置く(末尾空行を残すと git diff --check が "new blank line at EOF" を出す)
  { [ -s "$out" ] && echo; echo "## qa-gate $(date +%Y-%m-%d) ($(git rev-parse --short HEAD 2>/dev/null)) — $([ "$FAIL" = 0 ] && echo PASS || echo FAIL)"; echo; printf -- '- %s\n' "${REPORT[@]}" | sed 's/[[:space:]]*$//'; } >> "$out"
  echo "report appended: $out"
fi
exit "$FAIL"
