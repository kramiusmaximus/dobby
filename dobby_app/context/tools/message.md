Message executor contract:

Purpose:

- Produce Telegram text for Mark.
- Use this for final replies, acknowledgements, clarification questions, and failure summaries.

Supported operation:

- `send`

Accepted fields:

- `content`
- `query`
- `title`

Use the first non-empty value in that order.

If no text field is present, return `needs_clarification`.
