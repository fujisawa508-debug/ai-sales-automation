#!/usr/bin/env python3
"""PreToolUse Hook: git commit 実行前に mail.Send() の追加を検出してブロックする。"""
import json
import re
import subprocess
import sys


def main():
    # Windows上でのデフォルト標準出力エンコーディング(cp932等)による
    # 日本語の文字化けを防ぐため、明示的にUTF-8へ固定する
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # 入力が不正な場合はチェックせず許可する(Hook自体の不具合でコミットを止めない)
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")

    # git commit 系のコマンドでなければ何もせず終了(許可)
    if not re.search(r"git\s+commit", command):
        sys.exit(0)

    result = subprocess.run(
        ["git", "diff", "--cached", "--", "*.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    violations = [
        line for line in result.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
        and "mail.Send(" in line
    ]

    if violations:
        reason = (
            "ステージされたPythonファイルに mail.Send() の追加が検出されたため、"
            "コミットをブロックしました。このリポジトリは Outlook 下書き保存のみ"
            "(mail.Save())が不変条件であり、CLAUDE.md で自動送信処理の追加が"
            "明示的に禁止されています。該当行:\n" + "\n".join(violations)
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, ensure_ascii=False))

    sys.exit(0)


if __name__ == "__main__":
    main()
