---
name: assistant-skills
description: Repository-specific assistant behavior rules and operational conventions for working in this workspace. Use when performing edits, running tools, or interacting with credentials and devcontainer configuration.
license: CC-BY-4.0
compatibility: Requires access to repository files; intended for agents running inside contributor devcontainers or CI with filesystem access.
metadata:
  version: "1.0"
  author: repo-assistant
allowed-tools: Read Bash(git:*)
---

## Summary

This skill codifies how the assistant should behave when working in this repository. It enforces safe handling of secrets, minimal and precise edits, preambles for workspace-changing actions, and todo-tracking persistence.

## When to use
- Before making any workspace-modifying tool calls.
- When editing files, configuration, or devcontainer settings.
- When interacting with secrets, credentials, or CI configuration.

## Rules (short)

- Avoid using `|| true` or other constructs that silently mask failures; handle expected errors explicitly

- Ask before disruptive actions (rebuild containers, force-push, modifying production config)

- After changes to `.devcontainer/`, run `sudo devcontainer build --workspace-folder .` to verify the container builds before asking the user to reload VS Code.

- Keep this `SKILL.md` small (<500 lines). Move long references to `references/` if needed.
