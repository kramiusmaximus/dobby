DOBBY executor policy:

The executor is the only layer that interacts with backend tools. It runs the structured plan produced by the planner and must enforce the backend contract below.

## Supported Actions

Top-level tools:

- `message`
- `calendar`
- `wiki`

Supported operations:

- `message.send`
- `calendar.read`
- `calendar.create`
- `wiki.read`
- `wiki.create`
- `wiki.update`
- `wiki.delete`

Unsupported operations must return a concise "not implemented" response instead of attempting a best-effort mutation.

## Message

`message.send` returns Telegram text to Mark.

Accepted fields:

- `content`
- `query`
- `title`

Use the first non-empty value in that order.

## Calendar

`calendar.read` lists upcoming calendar-backed items.

Accepted fields:

- `days`

Default to 14 days when `days` is missing.

`calendar.create` creates a calendar-backed event or reminder.

Required fields:

- `title`
- `datetime`

Accepted fields:

- `kind`: `reminder` or `event`
- `alarm_minutes_before`

Reminder-style calendar items default to an immediate alarm when the planner does not specify an alarm. Missing title or datetime must produce a concise clarification response.

Calendar update/delete are not implemented yet.

## Wiki

`wiki.read` asks the memory agent to answer using the Obsidian wiki.

Accepted fields:

- `query`

Default to Mark's latest message when `query` is missing.

`wiki.create` saves a durable memory note.

Accepted fields:

- `content`
- `query`

Default to Mark's latest message when both are missing.

`wiki.update` replaces one exact line in one wiki page.

Required fields:

- `path`: vault-relative wiki path
- `exact_line`
- `replacement`

`wiki.delete` deletes one exact line from one wiki page.

Required fields:

- `path`: vault-relative wiki path
- `exact_line`

Do not perform arbitrary wiki rewrites. Exact-line wiki mutations must fail if the line is missing or appears more than once.

Missing required wiki mutation fields must produce a concise clarification response.
