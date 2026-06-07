---
title: Use Markdown Wiki As Second Brain
type: decision
created: 2026-05-23
updated: 2026-05-23
status: active
tags: [decision, second-brain, markdown]
sources:
  - ../sources/llm-wiki-idea-file.md
---

# Use Markdown Wiki As Second Brain

## Decision

Use a local markdown wiki at `/Users/kramiusmaximus/projects/dobby/wiki` as the user's LLM-maintained second brain.

## Rationale

Markdown files are easy for the LLM to edit, easy for the user to browse, compatible with Obsidian, and simple to search with command-line tools. The structure follows the LLM Wiki pattern: immutable raw sources, compiled wiki pages, and schema rules in `AGENTS.md`.

## Consequences

- The assistant should update wiki pages when durable personal context appears.
- Raw sources should remain unchanged after capture.
- Index and log maintenance are required wiki operations.
- The wiki can later be moved into git or enhanced with search tooling.
