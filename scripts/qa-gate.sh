#!/usr/bin/env bash
# qa-gate.sh — 試験資産ライフサイクル方針の機械チェック(change-test-gate の自動化部分)
#
# 正本: docs/development/test-asset-lifecycle-policy.md(この repo)/ brantechs/SQA checklists/change-test-gate.md
# 依存: bash + git のみ。言語・フレームワークに依存しない。
#
# 使い方:
#   scripts/qa-gate.sh change [--base <ref>] [--ticket <id>] [--branch <name>] [--staged] [--write]
#   scripts/qa-gate.sh major  [--version vX.Y.Z]
#
#   change : ブランチ(または index)の差分に対して、コード変更があるなら
#            DRBFM(version_tier 付き)/ 開発意図ログ / evidence / test-case master 差分 があり、
#            既存テストの削除・skip 化がないことを確認する。docs だけの変更は gate 対象外(PASS)。
#   major  : vX.0.0 の直前に、試験棚卸(観点台帳・棚卸報告)/ フルテスト evidence / release judgement があることを確認する。
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
case "$MODE" in change|major) ;; *) echo "usage: qa-gate.sh change|major [options]" >&2; exit 2;; esac

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

TEST_PATH_RE='(^|/)(tests?|__tests__|e2e|spec)/|(^|/)test_[^/]*\.py$|_test\.(py|go|rs)$|\.(spec|test)\.(ts|tsx|js|jsx|mjs|cjs)$'
# docs と gate 基盤(hook / CI 設定 / qa-gate 自身)はプロダクトコードではないので gate 対象外
DOCS_ONLY_RE='^(docs|checklists|prompts|snippets)/|\.(md|txt)$|^LICENSE|^\.githooks/|^\.github/|^scripts/(qa-gate|install-githooks)\.sh$'
SKIP_MARK_RE='pytest\.mark\.(skip|xfail)|@unittest\.skip|unittest\.SkipTest|\b(it|test|describe)\.skip\(|\b(xit|xtest|xdescribe)\(|@pytest\.mark\.skipif|#\[ignore\]'

# ---------- change ----------
run_change() {
  if [ -z "$BASE" ]; then
    for c in origin/dev origin/develop origin/main origin/master dev develop main master; do
      [ "$c" = "$BRANCH" ] && continue
      git rev-parse --verify -q "$c" >/dev/null && { BASE="$c"; break; }
    done
  fi
  [ -n "$BASE" ] || { echo "base ref が見つからない(--base で指定)" >&2; exit 2; }
  local mb; mb="$(git merge-base "$BASE" HEAD 2>/dev/null)" || mb="$BASE"
  local diffargs=("$mb")
  if [ "$STAGED" = 1 ]; then diffargs=("--cached" "$mb"); fi
  local status; status="$(git diff --name-status -M "${diffargs[@]}" 2>/dev/null)"
  note "mode=change base=$BASE ($mb) branch=$BRANCH ticket=$TICKET staged=$STAGED"
  if [ -z "$status" ]; then pass "差分なし"; return; fi

  local files; files="$(echo "$status" | awk '{print $NF}')"
  local code_files; code_files="$(echo "$files" | grep -Ev "$DOCS_ONLY_RE" || true)"
  # 1. 既存テストの削除・リネーム(from 側)
  local removed; removed="$(echo "$status" | awk '$1 ~ /^(D|R)/ {print $2}' | grep -E "$TEST_PATH_RE" || true)"
  # 2. skip 化(テストファイルへの追加行)
  local test_changed; test_changed="$(echo "$files" | grep -E "$TEST_PATH_RE" || true)"
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
    local f; f="$(echo "$drbfm" | grep -F -- "$TICKET" | head -1)"; [ -n "$f" ] || f="$(echo "$drbfm" | head -1)"
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
  # 7. major なら棚卸チェックへ
  if [ "$tier" = "major" ]; then note "version_tier=major: 棚卸・フルテストの確認を追加"; run_major; fi
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
  ls docs/operations/release-judgement/*v"$major".0.0*.md >/dev/null 2>&1 && pass "release judgement あり" \
    || fail "release judgement がない: docs/operations/release-judgement/<YYYYMMDD>-v$major.0.0.md(SQA checklists/release-judgement.md)"
  if [ -f docs/development/test-inventory/intent-register.md ]; then
    local gaps; gaps="$(grep -cE '\|[[:space:]]*gap[[:space:]]*\|' docs/development/test-inventory/intent-register.md || true)"
    [ "${gaps:-0}" = "0" ] && pass "観点台帳に gap(試験なしの観点)なし" || fail "観点台帳に gap が $gaps 行(観点はあるが試験がない)"
  fi
}

case "$MODE" in change) run_change;; major) run_major;; esac

echo; if [ "$FAIL" = 0 ]; then echo "QA GATE: PASS"; else echo "QA GATE: FAIL (詳細は上記。方針: docs/development/test-asset-lifecycle-policy.md)"; fi

if [ "$WRITE" = 1 ] && [ "$MODE" = "change" ]; then
  local_dir="docs/development/evidence/$TICKET"; mkdir -p "$local_dir"
  out="$local_dir/qa-gate.md"
  { echo "## qa-gate $(date +%Y-%m-%d) ($(git rev-parse --short HEAD 2>/dev/null)) — $([ "$FAIL" = 0 ] && echo PASS || echo FAIL)"; echo; printf -- '- %s\n' "${REPORT[@]}"; echo; } >> "$out"
  echo "report appended: $out"
fi
exit "$FAIL"
