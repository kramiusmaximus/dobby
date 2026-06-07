# LLM Wiki

Source captured from the user's message on 2026-05-23.

## Core idea

Most RAG systems retrieve chunks from raw documents at query time, so the model rediscovers knowledge from scratch on every question. The LLM Wiki pattern instead has the LLM incrementally build and maintain a persistent markdown wiki between the user and the raw sources.

When a new source is added, the LLM reads it, extracts important information, updates entity and concept pages, flags contradictions, and strengthens the current synthesis. The wiki is a persistent, compounding artifact: cross-references, contradictions, and summaries are kept current instead of being re-derived each time.

The user does not usually write the wiki. The LLM maintains it. The user curates sources, explores, asks questions, and reviews the output. Obsidian can act as the IDE, the LLM as the programmer, and the wiki as the codebase.

## Architecture

There are three layers:

- Raw sources: immutable source documents, articles, papers, images, and data files.
- The wiki: LLM-generated markdown pages, including summaries, entity pages, concept pages, comparisons, overviews, and synthesis.
- The schema: an agent instruction file that defines structure, conventions, and workflows.

## Operations

Ingest means adding a source, reading it, writing a source page, updating the index, updating relevant pages, and logging the change.

Query means asking questions against the wiki, searching and reading relevant pages, synthesizing answers with citations, and filing durable answers back into the wiki when useful.

Lint means periodically checking for contradictions, stale claims, orphan pages, missing cross-references, missing concept pages, and data gaps.

## Indexing and logging

`index.md` is content-oriented: a catalog of wiki pages with links and one-line summaries.

`log.md` is chronological and append-only. Log headings should use a parseable prefix such as:

```markdown
## [2026-04-02] ingest | Article Title
```

## Optional tools and practices

Markdown search is enough at moderate scale. For larger wikis, qmd can provide local markdown search with BM25, vector search, and LLM reranking. Obsidian Web Clipper, local image downloads, Obsidian graph view, Marp, Dataview, and git are useful optional tools.

## Why it works

Humans abandon wikis because maintenance is tedious. LLMs can update cross-references, summaries, contradictions, and many files in one pass. The user handles source curation and high-level thinking; the LLM handles bookkeeping.

## User instruction

The user asked: "You are now my LLM Wiki agent and you shall use this wiki to help you be my perfect personal assistant. Use it to Track my thoughts, organize my ideas, make reminders, help set goals, track my schedule, etc. Implement this exact idea file as my complete second brain. Guide me step-by-step: create the AGENT.md schem file with full rules (or add to it if it already exists), setup index.md and log.md, define folder conventions, and show me the first ingest example."
