---
title: LLM Wiki Idea File
type: source
created: 2026-05-23
updated: 2026-05-23
status: active
tags: [llm-wiki, second-brain, source]
sources:
  - ../../raw/sources/2026-05-23-llm-wiki-idea.md
---

# LLM Wiki Idea File

## Summary

This source proposes a personal knowledge-base pattern where an LLM incrementally builds and maintains a persistent markdown wiki instead of only retrieving raw documents at query time. The wiki compounds over time: summaries, cross-references, contradictions, concepts, entity pages, and durable answers are stored and maintained.

## Key Claims

- Query-time RAG is useful but does not naturally accumulate synthesis.
- A persistent wiki lets knowledge be compiled once and maintained.
- The LLM should own the wiki maintenance layer while the user curates sources and asks questions.
- `index.md` and `log.md` are the two core navigation files.
- Ingest, query, and lint are the three primary operations.
- Durable answers from conversations should be filed back into the wiki when valuable.

## Implications For This Assistant

This assistant should use the wiki as persistent memory for personal context, ideas, goals, reminders, schedule notes, projects, and decisions. It should update the wiki when user-provided information has durable value.

## Links

- [[pages/concepts/llm-wiki-pattern|LLM Wiki Pattern]]
- [[pages/projects/second-brain-operating-model|Second Brain Operating Model]]
- [[pages/goals/personal-assistant-goals|Personal Assistant Goals]]
- [[pages/decisions/use-markdown-wiki-as-second-brain|Use Markdown Wiki As Second Brain]]
- [[pages/questions/second-brain-open-questions|Second Brain Open Questions]]
