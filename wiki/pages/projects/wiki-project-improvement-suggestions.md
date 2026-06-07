---
title: Wiki Project Improvement Suggestions
type: project
created: 2026-05-24
updated: 2026-06-07
status: active
tags: [wiki, maintenance, project-improvement]
sources: []
---

# Wiki Project Improvement Suggestions

Use this page to collect suggested improvements for the DOBBY wiki and project operating model. Keep suggestions grouped by who proposed them.

## Mark


## Codex

- Use explicit Obsidian path links with aliases for pages whose filenames do not match their display titles, such as `[[pages/concepts/llm-wiki-pattern|LLM Wiki Pattern]]`, to avoid accidental root-level note stubs.
- Add a maintenance checklist for orphan pages, unresolved wikilinks, duplicate titles, stale dates, missing frontmatter, and reminder/wiki sync drift.
- Consider either matching canonical filenames to page titles or standardizing all internal links to explicit paths; mixing title links with slugged filenames makes Obsidian behavior less predictable.
- Add a short `wiki/README.md` or Obsidian home note explaining that canonical compiled pages live under `wiki/pages/`, while `wiki/raw/` is immutable source material.
- Add a lightweight recurring review rule for past-dated calendar/reminder pages so completed historical commitments can be archived or explicitly marked historical instead of remaining indefinitely `active`.
- Investigate why Reminders access is drifting between runs even when `scripts/reminders_preflight.sh` is used; maintenance can inspect sync drift, but verification stays incomplete whenever EventKit access is denied.
