Wiki executor contract:

Purpose:

- Read, create, update, and delete durable memory in the Obsidian wiki.
- For broad memory questions, use the wiki memory agent rather than a single deterministic file read.

Supported operations:

- `read`
- `create`
- `update`
- `delete`

Read accepted fields:

- `query`

Default to Mark's latest message when `query` is missing.

Create accepted fields:

- `content`
- `query`

Default to Mark's latest message when both are missing.

Update required fields:

- `path`: vault-relative wiki path
- `exact_line`
- `replacement`

Delete required fields:

- `path`: vault-relative wiki path
- `exact_line`

Do not perform arbitrary wiki rewrites. Exact-line wiki mutations must fail if the line is missing or appears more than once.

Missing required mutation fields must return `needs_clarification`.
