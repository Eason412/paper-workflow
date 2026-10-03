#!/bin/sh
# 把本仓库 skills/ 下的每个 Skill 软链到 Codex 与 Claude Code 的个人 Skill 目录。
# 已指向本仓库的链接跳过，旧链接直接替换；目标位置已有的真实目录或文件先移到同级的 skills-backup/ 再链接。
# 用法：scripts/link-skills.sh [--dry-run]
set -eu
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1
repo=$(cd "$(dirname "$0")/.." && pwd -P)
stamp=$(date +%Y%m%d%H%M%S)
run() { if [ "$dry" = 1 ]; then echo "would: $*"; else "$@"; fi; }
for target in "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.claude/skills"; do
  run mkdir -p "$target"
  for skill in "$repo"/skills/*/; do
    src=${skill%/}
    name=$(basename "$src")
    dest="$target/$name"
    if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
      echo "ok      $dest"
      continue
    fi
    if [ -L "$dest" ]; then
      # 旧链接不含内容，直接换成指向本仓库
      old=$(readlink "$dest")
      run rm "$dest"
      echo "relink  $dest (was $old)"
    elif [ -e "$dest" ]; then
      backup="$(dirname "$target")/skills-backup/$name-$stamp"
      run mkdir -p "$(dirname "$backup")"
      run mv "$dest" "$backup"
      echo "backup  $dest -> $backup"
    fi
    run ln -s "$src" "$dest"
    echo "linked  $dest -> $src"
  done
done
