#!/bin/bash
# 恢复 workspace 到有 bug 的原始版本（实验前执行）
DIR="$(cd "$(dirname "$0")" && pwd)"
for f in "$DIR"/*_original.py; do
    base=$(basename "$f" | sed 's/_original//')
    cp "$f" "$DIR/workspace/$base"
done
rm -f "$DIR/workspace/"*.bak
rm -rf "$DIR/workspace/__pycache__"
echo "Workspace restored to original (buggy) state."
