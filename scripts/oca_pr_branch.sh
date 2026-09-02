#!/usr/bin/env bash
# Create or update a one-module PR branch from the local 18.0 source of truth.
#
# Official OCA is read-only: fetch it to know the PR base (oca/18.0) and
# MIG history (oca/17.0, oca/16.0). Never git push to github.com/OCA/*.
# --push only goes to the fork (origin).
#
# Rules this encodes:
#   - One module per PR branch.
#   - PR branch is based on official OCA 18.0 (scaffold), never on our full 18.0.
#   - [ADD] for modules that did not exist on 16.0/17.0.
#   - [MIG] keeps 16.0/17.0 history via format-patch | git am, then overlays 18.0
#     in place (no delete+rewrite of the same scrape/logic).
#   - Do not add oca_dependencies.txt (unused).
#   - Do not rewrite history on --update. Do not filter-branch (rename is manual).
#   - Do not push --force. Do not touch branch 18.0.
#   - Do not push to OCA. --push only goes to the fork remote.
#
# Usage:
#   ./scripts/oca_pr_branch.sh l10n_ve_seniat
#   ./scripts/oca_pr_branch.sh l10n_ve_seniat --update
#   ./scripts/oca_pr_branch.sh currency_rate_update_bcv --type mig \
#       --old-name res_currency_rate_provider_BCV
#   ./scripts/oca_pr_branch.sh l10n_ve_seniat --dry-run

set -euo pipefail

SERIES="18.0"
SOURCE_REF="${SOURCE_REF:-18.0}"
SOURCE_SET=0
OCA_REMOTE="${OCA_REMOTE:-oca}"
OCA_URL="${OCA_URL:-https://github.com/OCA/l10n-venezuela.git}"
FORK_REMOTE="${FORK_REMOTE:-origin}"
MODULE=""
TYPE=""
OLD_NAME=""
FROM_SERIES=""
DO_UPDATE=0
DO_COMMIT=1
DO_PUSH=0
DO_FETCH=1
DRY_RUN=0
REBASE_BASE=0
COMMIT_MSG=""
START_BRANCH=""

usage() {
    cat <<'EOF'
oca_pr_branch.sh - create/update a one-module PR branch from 18.0

  18.0                 source of truth (all your code)
  oca/18.0             official OCA base of the PR (read only)
  origin               fork: the only push destination
  18.0-add-<module>    new module
  18.0-mig-<module>    module that already existed on 16.0/17.0

Examples
  ./scripts/oca_pr_branch.sh l10n_ve_seniat
  ./scripts/oca_pr_branch.sh l10n_ve_seniat --update
  ./scripts/oca_pr_branch.sh currency_rate_update_bcv --type mig \
      --old-name res_currency_rate_provider_BCV
  ./scripts/oca_pr_branch.sh l10n_ve_igtf --dry-run

Options
  --type add|mig     Force type. Auto: MIG if the module (or --old-name)
                     exists on oca/17.0 or oca/16.0.
  --old-name NAME    Directory name on 16.0/17.0 when the module was renamed.
                     The script will NOT run filter-branch.
  --from 16.0|17.0   Series to format-patch from (MIG create only). Auto.
  --source REF       Local/source ref with your code. Default: current
                     branch if it is 18.0 or 18.0-oca-push, else 18.0.
  --update           Refresh an existing PR branch from --source. Never
                     re-runs format-patch (that would duplicate history).
  --rebase-base      Before update, rebase the PR branch onto oca/18.0.
  --message TEXT     Commit message. Default depends on ADD/MIG/update.
  --no-commit        Stage only.
  --push             git push -u <fork> <branch> (no force). Never pushes
                     to github.com/OCA/*.
  --no-fetch         Skip git fetch (use after a previous run).
  --dry-run          Print the plan, do not change refs.
  -h, --help         This help.

Safety
  Does not switch 18.0, does not force-push, does not amend, does not
  change other modules, does not write oca_dependencies.txt.
  Fetches official OCA only to know the base. Never pushes to OCA.
  After each commit it rewrites HEAD with commit-tree if a hook added
  Cursor (trailer or author). If Cursor is still present, it exits
  without pushing.
EOF
}

die() {
    echo "error: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

run() {
    if ((DRY_RUN)); then
        printf 'DRY: '
        printf '%q ' "$@"
        printf '\n'
        return 0
    fi
    "$@"
}

need_cmd() {
    command -v "$1" >/dev/null || die "missing command: $1"
}

parse_args() {
    while (($#)); do
        case "$1" in
            --type)
                TYPE="${2:-}"
                shift 2
                ;;
            --old-name)
                OLD_NAME="${2:-}"
                shift 2
                ;;
            --from)
                FROM_SERIES="${2:-}"
                shift 2
                ;;
            --source)
                SOURCE_REF="${2:-}"
                SOURCE_SET=1
                shift 2
                ;;
            --update)
                DO_UPDATE=1
                shift
                ;;
            --rebase-base)
                REBASE_BASE=1
                shift
                ;;
            --message)
                COMMIT_MSG="${2:-}"
                shift 2
                ;;
            --no-commit)
                DO_COMMIT=0
                shift
                ;;
            --push)
                DO_PUSH=1
                shift
                ;;
            --no-fetch)
                DO_FETCH=0
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            --*)
                die "unknown option: $1"
                ;;
            *)
                if [[ -n $MODULE ]]; then
                    die "unexpected argument: $1"
                fi
                MODULE="$1"
                shift
                ;;
        esac
    done
    [[ -n $MODULE ]] || {
        usage
        die "module name is required"
    }
    [[ $MODULE =~ ^[a-zA-Z0-9_]+$ ]] || die "invalid module name: $MODULE"
    if [[ -n $TYPE && $TYPE != add && $TYPE != mig ]]; then
        die "--type must be add or mig"
    fi
}

repo_root() {
    git rev-parse --show-toplevel
}

ensure_repo() {
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "run this from the git repo"
    cd "$(repo_root)"
    START_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
        die "tracked files are dirty on ${START_BRANCH}. Commit or stash before running the script"
    fi
}

ref_exists() {
    git rev-parse --verify --quiet "$1" >/dev/null
}

remote_ref_exists() {
    git rev-parse --verify --quiet "$1" >/dev/null
}

tree_has_dir() {
    local ref="$1" path="$2"
    git ls-tree -d --name-only "$ref" -- "$path" 2>/dev/null | grep -qx "$path"
}

is_oca_url() {
    local url="${1:-}"
    [[ $url == *github.com/OCA/* || $url == *github.com:OCA/* ]]
}

remote_url() {
    git remote get-url "$1" 2>/dev/null || true
}

assert_push_remote_is_not_oca() {
    local remote="$1"
    local url
    if [[ $remote == "$OCA_REMOTE" ]]; then
        die "nunca se hace push a '$remote' (remoto oficial de OCA). Usa el fork ($FORK_REMOTE)."
    fi
    url="$(remote_url "$remote")"
    if is_oca_url "$url"; then
        die "remote '$remote' apunta a OCA ($url). Nunca se sube a OCA. Usa tu fork."
    fi
}

history_series_ref() {
    local series="$1"
    if remote_ref_exists "${OCA_REMOTE}/${series}"; then
        echo "${OCA_REMOTE}/${series}"
        return 0
    fi
    if remote_ref_exists "${FORK_REMOTE}/${series}"; then
        echo "${FORK_REMOTE}/${series}"
        return 0
    fi
    if ref_exists "$series"; then
        echo "$series"
        return 0
    fi
    return 1
}

ensure_remotes() {
    if ! git remote get-url "$FORK_REMOTE" >/dev/null 2>&1; then
        die "fork remote '$FORK_REMOTE' is missing"
    fi
    assert_push_remote_is_not_oca "$FORK_REMOTE"
    if ! git remote get-url "$OCA_REMOTE" >/dev/null 2>&1; then
        info "adding remote $OCA_REMOTE -> $OCA_URL (read only, never push)"
        git remote add "$OCA_REMOTE" "$OCA_URL"
    fi
    if ! ((DO_FETCH)); then
        info "skip fetch (--no-fetch)"
        return 0
    fi
    info "fetch $OCA_REMOTE (read only)"
    git fetch --prune "$OCA_REMOTE"
    info "fetch $FORK_REMOTE"
    git fetch --prune "$FORK_REMOTE"
}

resolve_source() {
    if ! ((SOURCE_SET)); then
        if [[ $START_BRANCH == "$SERIES" || $START_BRANCH == "${SERIES}-oca-push" ]]; then
            SOURCE_REF="$START_BRANCH"
        fi
    fi
    if ref_exists "$SOURCE_REF"; then
        return 0
    fi
    if ref_exists "${FORK_REMOTE}/${SOURCE_REF}"; then
        SOURCE_REF="${FORK_REMOTE}/${SOURCE_REF}"
        return 0
    fi
    die "source ref not found: $SOURCE_REF (need local 18.0, 18.0-oca-push, or ${FORK_REMOTE}/18.0)"
}

resolve_base() {
    BASE_REF="${OCA_REMOTE}/${SERIES}"
    remote_ref_exists "$BASE_REF" || die "missing $BASE_REF - fetch official OCA 18.0 (read only)"
}

detect_history_series() {
    local name="${OLD_NAME:-$MODULE}"
    local hist_ref=""
    HIST_NAME="$name"
    HIST_REF=""
    if [[ -n $FROM_SERIES ]]; then
        if hist_ref="$(history_series_ref "$FROM_SERIES")"; then
            HIST_REF="$hist_ref"
            return 0
        fi
        die "MIG --from $FROM_SERIES but ${OCA_REMOTE}/${FROM_SERIES} is missing"
    fi
    if hist_ref="$(history_series_ref 17.0)" && tree_has_dir "$hist_ref" "$name"; then
        FROM_SERIES="17.0"
        HIST_REF="$hist_ref"
        return 0
    fi
    if hist_ref="$(history_series_ref 16.0)" && tree_has_dir "$hist_ref" "$name"; then
        FROM_SERIES="16.0"
        HIST_REF="$hist_ref"
        return 0
    fi
    FROM_SERIES=""
}

pr_branch_exists() {
    local branch="$1"
    ref_exists "$branch" || remote_ref_exists "${FORK_REMOTE}/${branch}"
}

detect_type() {
    if [[ -n $TYPE ]]; then
        return 0
    fi
    if pr_branch_exists "${SERIES}-mig-${MODULE}"; then
        TYPE="mig"
        return 0
    fi
    if pr_branch_exists "${SERIES}-add-${MODULE}"; then
        TYPE="add"
        return 0
    fi
    detect_history_series
    if [[ -n $FROM_SERIES ]]; then
        TYPE="mig"
    else
        TYPE="add"
    fi
}

branch_name() {
    if [[ $TYPE == mig ]]; then
        echo "${SERIES}-mig-${MODULE}"
    else
        echo "${SERIES}-add-${MODULE}"
    fi
}

current_branch() {
    git rev-parse --abbrev-ref HEAD
}

assert_source_has_module() {
    tree_has_dir "$SOURCE_REF" "$MODULE" || die "$MODULE is not a directory on $SOURCE_REF"
}

warn_personal_bank_files() {
    local f
    shopt -s nullglob
    for f in \
        "${MODULE}/"*Bancaribe* \
        "${MODULE}/"*Banesco* \
        "${MODULE}/"*BFC*.xlsx \
        "${MODULE}/"*BFC*.xls \
        "${MODULE}/"*BFC*.csv; do
        echo "warning: possible personal bank file: $f (review the commit)" >&2
    done
    shopt -u nullglob
}

drop_oca_dependencies() {
    if [[ -f oca_dependencies.txt ]]; then
        echo "warning: removing oca_dependencies.txt (OCA no longer uses it)" >&2
        if ((DRY_RUN)); then
            echo "DRY: git rm -f --ignore-unmatch oca_dependencies.txt"
            return 0
        fi
        git rm -f --ignore-unmatch oca_dependencies.txt || rm -f oca_dependencies.txt
    fi
}

list_module_files() {
    git ls-tree -r --name-only "$1" -- "$2" | sort
}

sync_module_from_source() {
    local mode="$1"
    local extra
    extra="$(comm -23 <(list_module_files HEAD "$MODULE") <(list_module_files "$SOURCE_REF" "$MODULE") || true)"
    if [[ $mode == add && -n $extra ]]; then
        info "removing files gone from $SOURCE_REF"
        while IFS= read -r path; do
            [[ -z $path ]] && continue
            run git rm -f -- "$path"
        done <<<"$extra"
    elif [[ $mode == mig && -n $extra ]]; then
        echo "note: files only on the PR branch (not on $SOURCE_REF):" >&2
        echo "$extra" >&2
        echo "note: if one of these was renamed, stop and run: git mv <old> <new>" >&2
        echo "note: MIG overlay does not delete them (keeps history)." >&2
    fi
    info "checkout $SOURCE_REF -- $MODULE"
    run git checkout "$SOURCE_REF" -- "$MODULE"
    drop_oca_dependencies
    warn_personal_bank_files
}

default_commit_message() {
    local action="$1"
    if [[ -n $COMMIT_MSG ]]; then
        printf '%s\n' "$COMMIT_MSG"
        return 0
    fi
    case "$action" in
        add)
            cat <<EOF
[ADD] ${MODULE}: add Venezuelan localization module

Port the module from the project 18.0 branch as a standalone
OCA pull request (one module per PR).
EOF
            ;;
        mig)
            cat <<EOF
[MIG] ${MODULE}: Migration to 18.0

Adapt the ${FROM_SERIES:-16.0} module in place for Odoo 18.0 using
the current code from the project 18.0 branch.
EOF
            ;;
        update)
            cat <<EOF
[IMP] ${MODULE}: sync from 18.0

Refresh this OCA PR branch with the current module from the
project 18.0 branch.
EOF
            ;;
        *)
            die "internal: unknown commit action $action"
            ;;
    esac
}

# Drop Cursor trailers and Cursor author/committer. Uses commit-tree so
# prepare-commit-msg / commit-msg hooks cannot inject them again.
sanitize_head_commit() {
    local body tree parent new
    local author_name author_email author_date
    local committer_name committer_email committer_date
    local changed=0

    body="$(git log -1 --format='%B')"
    author_name="$(git log -1 --format='%an')"
    author_email="$(git log -1 --format='%ae')"
    author_date="$(git log -1 --format='%aI')"
    committer_name="$(git log -1 --format='%cn')"
    committer_email="$(git log -1 --format='%ce')"
    committer_date="$(git log -1 --format='%cI')"

    body="$(
        printf '%s' "$body" | python3 -c '
import re
import sys

lines = sys.stdin.read().splitlines()
keep = [
    line
    for line in lines
    if not re.match(r"^\s*Co-authored-by:\s*.*cursor", line, flags=re.I)
]
while keep and keep[-1] == "":
    keep.pop()
sys.stdout.write("\n".join(keep) + ("\n" if keep else ""))
'
    )"

    if git log -1 --format='%B' | grep -qiE 'Co-authored-by:[[:space:]]*.*cursor'; then
        changed=1
    fi
    if printf '%s %s %s %s' \
        "$author_name" "$author_email" "$committer_name" "$committer_email" \
        | grep -qiE 'cursor|cursoragent'; then
        changed=1
        author_name="${GIT_AUTHOR_NAME:-andyengit}"
        author_email="${GIT_AUTHOR_EMAIL:-anderson.armeya@gmail.com}"
        committer_name="${GIT_COMMITTER_NAME:-andyengit}"
        committer_email="${GIT_COMMITTER_EMAIL:-anderson.armeya@gmail.com}"
    fi

    if ! ((changed)); then
        assert_commit_has_no_cursor HEAD
        return 0
    fi

    tree="$(git rev-parse 'HEAD^{tree}')"
    parent="$(git rev-parse 'HEAD^')"
    new="$(
        GIT_AUTHOR_NAME="$author_name" \
            GIT_AUTHOR_EMAIL="$author_email" \
            GIT_AUTHOR_DATE="$author_date" \
            GIT_COMMITTER_NAME="$committer_name" \
            GIT_COMMITTER_EMAIL="$committer_email" \
            GIT_COMMITTER_DATE="$committer_date" \
            git commit-tree "$tree" -p "$parent" -m "$body"
    )"
    git reset --soft "$new"
    assert_commit_has_no_cursor HEAD
    info "rewrote HEAD without Cursor authorship"
}

assert_commit_has_no_cursor() {
    local rev="${1:-HEAD}"
    if git log -1 --format='%B%n%an%n%ae%n%cn%n%ce' "$rev" \
        | grep -qiE 'cursoragent|Co-authored-by:[[:space:]]*.*cursor|^[Cc]ursor$'; then
        die "commit $rev still mentions Cursor; refusing to continue"
    fi
}

commit_if_needed() {
    local action="$1"
    if ((DRY_RUN)); then
        info "would commit [$action] if the index is dirty"
        return 0
    fi
    drop_oca_dependencies
    if git diff --cached --quiet && git diff --quiet; then
        info "no changes to commit"
        return 0
    fi
    run git add -- "$MODULE"
    if ! ((DO_COMMIT)); then
        info "staged $MODULE (--no-commit)"
        git status --short -- "$MODULE"
        return 0
    fi
    local msg
    msg="$(default_commit_message "$action")"
    git commit -m "$msg"
    sanitize_head_commit
}

push_branch() {
    local branch="$1"
    assert_push_remote_is_not_oca "$FORK_REMOTE"
    if ! ((DO_PUSH)); then
        info "not pushing (pass --push when you want: git push -u $FORK_REMOTE $branch)"
        info "never: git push $OCA_REMOTE"
        return 0
    fi
    if ((DRY_RUN)); then
        info "would push $FORK_REMOTE $branch (no force; never $OCA_REMOTE)"
        return 0
    fi
    assert_commit_has_no_cursor HEAD
    git push -u "$FORK_REMOTE" "$branch"
}

branch_exists_anywhere() {
    local branch="$1"
    ref_exists "$branch" || remote_ref_exists "${FORK_REMOTE}/${branch}"
}

checkout_pr_branch() {
    local branch="$1"
    if ref_exists "$branch"; then
        run git checkout "$branch"
        return 0
    fi
    if remote_ref_exists "${FORK_REMOTE}/${branch}"; then
        run git checkout -B "$branch" --track "${FORK_REMOTE}/${branch}"
        return 0
    fi
    return 1
}

create_add() {
    local branch="$1"
    info "create $branch from $BASE_REF"
    run git checkout -B "$branch" "$BASE_REF"
    sync_module_from_source add
    commit_if_needed add
}

create_mig() {
    local branch="$1"
    detect_history_series
    [[ -n $FROM_SERIES && -n $HIST_REF ]] || die "MIG requested but $HIST_NAME is not on ${OCA_REMOTE}/17.0 nor ${OCA_REMOTE}/16.0"
    info "create $branch from $BASE_REF"
    info "replay history: $BASE_REF..${HIST_REF} -- $HIST_NAME"
    if [[ -n $OLD_NAME && $OLD_NAME != "$MODULE" ]]; then
        echo "note: history path is $OLD_NAME, current name is $MODULE." >&2
        echo "note: this script will overlay $MODULE from $SOURCE_REF after am." >&2
        echo "note: to rename the whole history, run once:" >&2
        echo "  git filter-branch --tree-filter 'if [ -d $OLD_NAME ]; then mv $OLD_NAME $MODULE; fi' HEAD" >&2
        echo "  git rebase $BASE_REF" >&2
    fi
    if ((DRY_RUN)); then
        info "would: format-patch | git am -3 --keep"
        info "would: overlay $SOURCE_REF -- $MODULE"
        return 0
    fi
    git checkout -B "$branch" "$BASE_REF"
    if ! git format-patch --keep-subject --stdout \
        "${BASE_REF}..${HIST_REF}" -- "$HIST_NAME" \
        | git am -3 --keep; then
        echo "error: git am failed. Fix conflicts, then:" >&2
        echo "  git add --all && git am --continue" >&2
        echo "or: git am --abort" >&2
        echo "whitespace issues: add --ignore-whitespace to git am" >&2
        exit 1
    fi
    if [[ -n $OLD_NAME && $OLD_NAME != "$MODULE" && -d $OLD_NAME && ! -d $MODULE ]]; then
        die "history still uses $OLD_NAME. Run filter-branch or git mv, then re-run with --update"
    fi
    sync_module_from_source mig
    commit_if_needed mig
}

update_existing() {
    local branch="$1"
    checkout_pr_branch "$branch" || die "PR branch $branch does not exist (create it first without --update)"
    if ((REBASE_BASE)); then
        info "rebase onto $BASE_REF"
        run git rebase "$BASE_REF"
    fi
    if [[ $TYPE == add ]]; then
        sync_module_from_source add
    else
        sync_module_from_source mig
    fi
    commit_if_needed update
}

print_plan() {
    cat <<EOF
plan
  module:     $MODULE
  type:       $TYPE
  branch:     $BRANCH
  source:     $SOURCE_REF
  base:       $BASE_REF
  history:    ${FROM_SERIES:-n/a} path=${HIST_NAME:-$MODULE}
  mode:       $( ((DO_UPDATE)) && echo update || echo create-or-update)
  commit:     $( ((DO_COMMIT)) && echo yes || echo no)
  push:       $( ((DO_PUSH)) && echo "$FORK_REMOTE $BRANCH" || echo no)
  rebase:     $( ((REBASE_BASE)) && echo yes || echo no)
EOF
}

main() {
    parse_args "$@"
    need_cmd git
    ensure_repo
    trap restore_start_branch EXIT
    ensure_remotes
    resolve_source
    resolve_base
    detect_history_series
    detect_type
    BRANCH="$(branch_name)"
    assert_source_has_module
    print_plan

    if ((DRY_RUN)); then
        if branch_exists_anywhere "$BRANCH" || ((DO_UPDATE)); then
            info "dry-run: would update $BRANCH from $SOURCE_REF"
        else
            info "dry-run: would create $BRANCH from $BASE_REF ($TYPE)"
        fi
        exit 0
    fi

    local cur
    cur="$(current_branch)"
    if [[ $cur == "$SERIES" ]]; then
        info "leaving $SERIES; checking out $BRANCH"
    fi

    if ((DO_UPDATE)); then
        update_existing "$BRANCH"
    elif checkout_pr_branch "$BRANCH"; then
        info "branch exists; treating as --update (history is kept)"
        if [[ $TYPE == add ]]; then
            sync_module_from_source add
        else
            sync_module_from_source mig
        fi
        commit_if_needed update
    elif [[ $TYPE == mig ]]; then
        create_mig "$BRANCH"
    else
        create_add "$BRANCH"
    fi

    push_branch "$BRANCH"
    info "done. HEAD=$(git rev-parse --abbrev-ref HEAD) $(git log -1 --oneline)"
    info "push only to the fork ($FORK_REMOTE). Never: git push $OCA_REMOTE"
}

restore_start_branch() {
    if ((DRY_RUN)); then
        return 0
    fi
    if [[ -z ${START_BRANCH:-} || $START_BRANCH == HEAD ]]; then
        return 0
    fi
    if [[ $(current_branch) != "$START_BRANCH" ]]; then
        info "returning to $START_BRANCH"
        git checkout "$START_BRANCH"
    fi
}

main "$@"
