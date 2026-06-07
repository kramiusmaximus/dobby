---
title: LLM Wiki Pattern
type: concept
created: 2026-05-23
updated: 2026-05-23
status: active
tags: [llm-wiki, knowledge-management, second-brain]
sources:
  - ../sources/llm-wiki-idea-file.md
---

# LLM Wiki Pattern

The LLM Wiki pattern is a way to build a personal or team knowledge base where an LLM maintains a persistent markdown wiki from raw sources and conversations.

## Core Model

- Raw sources are immutable and remain the source of truth.
- The wiki is the compiled, interlinked knowledge layer.
- The schema tells the LLM how to maintain the wiki.

## Difference From RAG

RAG usually retrieves relevant chunks at query time and synthesizes answers on demand. The LLM Wiki pattern keeps synthesis as a durable artifact. New sources update the wiki, so future questions start from accumulated structure rather than raw fragments.

## Main Operations

- Ingest: integrate a new source into the wiki.
- Query: answer from the wiki and optionally file reusable answers.
- Lint: check health, consistency, stale claims, orphan pages, and missing links.

## Personal Assistant Use

For this project, the pattern is used as a second brain. The wiki should preserve goals, decisions, project state, schedule notes, reminders, and open questions.
