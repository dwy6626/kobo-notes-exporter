#!/usr/bin/env bash

set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly EXPORTER_REPO="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
readonly NOTES_REPO="$(cd -- "${EXPORTER_REPO}/.." && pwd -P)/kobo-notes"
readonly REMOTE="origin"
readonly BASE_BRANCH="main"
readonly NOTES_PATHSPEC=':(top,glob)*.md'

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

notes_git() {
    git -C "${NOTES_REPO}" "$@"
}

require_command git
require_command gh
require_command uv

[[ -d "${NOTES_REPO}" ]] || fail "Notes repository not found: ${NOTES_REPO}"
[[ "$(notes_git rev-parse --is-inside-work-tree 2>/dev/null)" == "true" ]] || \
    fail "Not a Git repository: ${NOTES_REPO}"
notes_git remote get-url "${REMOTE}" >/dev/null 2>&1 || \
    fail "Git remote '${REMOTE}' is not configured in ${NOTES_REPO}"

if [[ -n "$(notes_git status --porcelain)" ]]; then
    fail "Notes repository has uncommitted changes: ${NOTES_REPO}"
fi

readonly ORIGINAL_BRANCH="$(notes_git branch --show-current)"
[[ -n "${ORIGINAL_BRANCH}" ]] || fail "Notes repository is in detached HEAD state"

gh auth status >/dev/null 2>&1 || \
    fail "GitHub CLI is not authenticated. Run: gh auth login -h github.com"

notes_git fetch "${REMOTE}" "${BASE_BRANCH}"

readonly TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
readonly BRANCH="kobo-notes/${TIMESTAMP}"
readonly COMMIT_DATE="$(date '+%Y-%m-%d %H:%M:%S %Z')"
readonly PR_TITLE="Update Kobo notes (${COMMIT_DATE})"

notes_git switch --create "${BRANCH}" "${REMOTE}/${BASE_BRANCH}"

(
    cd -- "${EXPORTER_REPO}"
    uv run export "$@" --out-dir "${NOTES_REPO}" --out-exists overwrite
)

notes_git add -- "${NOTES_PATHSPEC}"

if notes_git diff --cached --quiet -- "${NOTES_PATHSPEC}"; then
    notes_git switch "${ORIGINAL_BRANCH}"
    if ! notes_git branch --delete "${BRANCH}"; then
        printf 'No Markdown changes; empty branch retained: %s\n' "${BRANCH}" >&2
    else
        printf 'No Markdown changes; no commit, push, or PR created.\n'
    fi
    exit 0
fi

notes_git commit -m "${PR_TITLE}"
notes_git push --set-upstream "${REMOTE}" "${BRANCH}"

(
    cd -- "${NOTES_REPO}"
    gh pr create \
        --base "${BASE_BRANCH}" \
        --head "${BRANCH}" \
        --title "${PR_TITLE}" \
        --body "Automated Kobo notes export from ../kobo-notes-exporter."
)
