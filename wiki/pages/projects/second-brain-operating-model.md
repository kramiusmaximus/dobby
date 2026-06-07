---
title: Second Brain Operating Model
type: project
created: 2026-05-23
updated: 2026-05-23
status: active
tags: [second-brain, personal-assistant, llm-wiki]
sources:
  - ../sources/llm-wiki-idea-file.md
---

# Second Brain Operating Model

## Purpose

Use `/Users/kramiusmaximus/projects/dobby/wiki` as a personal second brain maintained by the LLM. The wiki should help the user track thoughts, organize ideas, make reminders, set goals, track schedule context, and preserve useful synthesis from conversations.

## Operating Rules

- Read `index.md` first when answering from the wiki.
- Use `rg` to search the wiki before assuming context.
- Update existing pages before creating duplicates.
- Add wikilinks whenever pages materially relate.
- Record durable changes in `log.md`.
- Keep raw sources immutable.
- Use actual automations for reminders that require notification.

## Current Folder Model

- `raw/sources`: source documents.
- `raw/assets`: attachments and local media.
- `pages/sources`: compiled source pages.
- `pages/concepts`: reusable ideas and frameworks.
- `pages/projects`: active work and project state.
- `pages/goals`: goals and habits.
- `pages/calendar`: plans and schedule context.
- `pages/decisions`: decisions and rationale.
- `pages/questions`: open loops.

## Next Setup Steps

- Add the user's current active projects.
- Add current goals and recurring commitments.
- Add preferred reminder and scheduling conventions.
- Add personal context only when explicitly provided by the user.
