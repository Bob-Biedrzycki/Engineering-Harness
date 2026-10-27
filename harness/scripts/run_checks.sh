#!/usr/bin/env bash
# run_checks.sh - run every harness/checks/*.py and decide whether the PR goes red.
#
# Called by .github/workflows/checks.yml ("Run checks"); runs the same way locally:
#   PYTHON=harness/tools/venv/Scripts/python.exe bash harness/scripts/run_checks.sh
# (on Windows: MinGit's usr\bin\sh.exe, with that usr\bin folder on PATH for grep/sed/tr/head)
#
# Policy (Bob, chat, 2026-10-07: "The PR should not be flagging design findings."):
# design findings are reported as warnings and never fail the PR. The PR fails only
# when the tooling is broken, or a repo-integrity check fails. Unit tests
# (harness/tests) are their own workflow step and fail the CI job on their own.
# ("CI job" = the GitHub Actions run, not the CPME job.)
#
#   exit 0                                   PASS
#   exit 2                                   NOT IMPLEMENTED   ::warning, passes
#   exit 1 + "<name>: FAIL ..." summary      FINDINGS          ::warning, passes
#            (check in HARD_FAIL_CHECKS)     FAIL              ::error,   CI job fails
#   exit 1 without that summary line,        ERROR (broken)    ::error,   CI job fails
#   any other exit code (a check prints
#   "<name>: ERROR - ..." and exits 3 when
#   it could not run), or a Python traceback
#
# HARD_FAIL_CHECKS: repo-integrity checks, whose findings are not design findings.
#   drive_pointers.py - a large file committed to git or a malformed Drive pointer
#                       (CPME practice); the repo itself is wrong, not the design.
# Every other check measures the design or its output (sanitary, pipe_supports,
# interference, envelope, pid_consistency, portal_terms, tag_crosscheck, component_register) and reports.
#
# Environment (all optional): PYTHON (default python), CHECKS_DIR (default
# harness/checks), GITHUB_STEP_SUMMARY (default /dev/null).
set +e

HARD_FAIL_CHECKS="drive_pointers.py"

PYTHON="${PYTHON:-python}"
CHECKS_DIR="${CHECKS_DIR:-harness/checks}"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

# GitHub workflow-command data: % CR LF must be escaped.
esc() { printf '%s' "$1" | sed -e 's/%/%25/g' | tr -d '\r'; }

is_hard() {
  for h in $HARD_FAIL_CHECKS; do [ "$h" = "$1" ] && return 0; done
  return 1
}

broken=0; failed=0; findings=0; not_implemented=0
{
  echo "## harness/checks/ results"
  echo ""
  echo "Design findings are warnings and never fail the PR (Bob, 2026-10-07). Hard-fail (repo integrity): \`$HARD_FAIL_CHECKS\`."
  echo ""
  echo "| check | exit | status | summary |"
  echo "|---|---|---|---|"
} >> "$SUMMARY"

for f in "$CHECKS_DIR"/*.py; do
  [ -e "$f" ] || continue
  base="${f##*/}"; name="${base%.py}"
  out=$("$PYTHON" "$f" 2>&1); rc=$?
  out=$(printf '%s' "$out" | tr -d '\r')
  # Summary line: the first line that starts with "<name>: " (the contract puts it
  # first; this tolerates a library warning on stderr ahead of it).
  # A check that prints one summary per target (portal_terms) is summarised by its
  # first FAIL line when there is one.
  line=$(printf '%s\n' "$out" | grep -m 1 "^$name: FAIL")
  [ -n "$line" ] || line=$(printf '%s\n' "$out" | grep -m 1 "^$name: ")
  [ -n "$line" ] || line=$(printf '%s\n' "$out" | head -n 1)
  traceback=0
  printf '%s\n' "$out" | grep -q '^Traceback (most recent call last)' && traceback=1

  if [ "$traceback" -eq 1 ]; then
    status="ERROR"; broken=$((broken+1))
    last=$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1)
    echo "::error file=$f::$name crashed (Python traceback, exit $rc): $(esc "$last")"
  else
    case $rc in
      0) status="PASS" ;;
      2) status="NOT IMPLEMENTED"; not_implemented=$((not_implemented+1))
         echo "::warning file=$f::$(esc "$line")" ;;
      1) case "$line" in
           "$name: FAIL"*)
             if is_hard "$base"; then
               status="FAIL"; failed=$((failed+1))
               echo "::error file=$f::$(esc "$line")"
             else
               status="FINDINGS"; findings=$((findings+1))
               echo "::warning file=$f::$(esc "$line")"
             fi ;;
           *) status="ERROR"; broken=$((broken+1))
              echo "::error file=$f::$name exited 1 without its '$name: FAIL' summary line: $(esc "$line")" ;;
         esac ;;
      *) status="ERROR"; broken=$((broken+1))
         echo "::error file=$f::$name could not run (exit $rc): $(esc "$line")" ;;
    esac
  fi
  cell=$(printf '%s' "$line" | sed -e 's/|/\\|/g')
  echo "| \`$f\` | $rc | $status | $cell |" >> "$SUMMARY"
  echo "::group::$f (exit $rc, $status)"; printf '%s\n' "$out"; echo "::endgroup::"
done

{
  echo ""
  echo "Broken: $broken. Repo-integrity failures: $failed. Design findings (warnings): $findings. Not implemented: $not_implemented."
  if [ "$findings" -gt 0 ]; then
    echo ""
    echo "> **$findings check(s) reported design findings.** They do not fail the PR; the details are in the log groups. Weigh them at review."
  fi
  if [ "$not_implemented" -gt 0 ]; then
    echo ""
    echo "> **$not_implemented check(s) NOT IMPLEMENTED.** The CI job passes, but those checks verified nothing. Weigh this at review."
  fi
} >> "$SUMMARY"

echo "run_checks: broken $broken, integrity failures $failed, findings $findings, not implemented $not_implemented"
if [ $((broken + failed)) -gt 0 ]; then
  echo "::error::$broken check(s) broken, $failed repo-integrity check(s) failed"
  exit 1
fi
exit 0
