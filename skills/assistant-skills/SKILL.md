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
- Never commit secrets. Keep credentials in `.secrets/` and ensure the directory is in `.gitignore`.
- Avoid using `|| true` or other constructs that silently mask failures; handle expected errors explicitly.
- Provide a concise (1–2 sentence) preamble before batches of workspace-modifying tool calls.
- Use precise edits; do not reformat unrelated code.
- Wrap filenames and symbols in backticks when referencing them in messages.
- Persist the current plan/todo to `TODO.md` in the repo root before ending a session.
- Ask before disruptive actions (rebuild containers, force-push, modifying production config).

## Step-by-step guidance

1. Environment & Secrets
   - Verify `.secrets/` exists and is listed in `.gitignore`.
   - Mount `.secrets/` into the devcontainer via `devcontainer.json` instead of copying credentials into the repo.
   - When moving a downloaded key, rename it to `gcp-sa-key.json` and place it in `.secrets/`.

2. Making edits
   - Preface the change with a one-line preamble explaining what will be modified and why.
   - Use the repository patch tools when available to apply minimal diffs.
   - After edits, run lightweight verification (e.g., `git status`, lint command) and report results.

3. Error handling
   - Replace `cmd || true` with explicit checks or a short explanatory fallback, for example:
     ```bash
     if ! git commit -m "msg"; then
       echo "no changes to commit"
     fi
     ```

4. Todo / Planning
   - Keep the `TODO.md` file in sync with the Todo API and commit the file so plan state survives restarts.
   - Mark tasks `in-progress` before starting, and `completed` after verification.

## Examples

- Preamble example before running a mount/edit batch:

  "I'm about to update `.devcontainer/devcontainer.json` to mount `.secrets/` so the container can access GCP credentials."

- Secret handling example:

  1. Create `.secrets/`.
  2. Move `my-key.json` -> `.secrets/gcp-sa-key.json`.
  3. Ensure `/.secrets/` is present in `.gitignore`.

## Files
- This skill may reference `ASSISTANT_SKILLS.md` for human-readable rules and `TODO.md` for persisted plan state.

## Validation
- Keep this `SKILL.md` small (<500 lines). Move long references to `references/` if needed.

