Calendar executor contract:

Purpose:

- Read and write calendar-backed events and reminder-style notifications.
- Use CalDAV as the notification transport.

Supported operations:

- `read`
- `create`

Read accepted fields:

- `days`

Default to 14 days when `days` is missing.

Create required fields:

- `title`
- `datetime`

Create accepted fields:

- `kind`: `reminder` or `event`
- `alarm_minutes_before`

Reminder-style calendar items default to an immediate alarm when no alarm is specified.

Calendar update/delete are not implemented yet and must return `unsupported`.
