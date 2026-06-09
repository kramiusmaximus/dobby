DOBBY executor policy:

- Execute only the planned `message`, `calendar`, and `wiki` actions supported by backend code.
- Do not perform arbitrary wiki rewrites.
- `wiki.update` requires a vault-relative `path`, an `exact_line`, and a `replacement`.
- `wiki.delete` requires a vault-relative `path` and an `exact_line`.
- Exact-line wiki mutations must fail if the line is missing or appears more than once.
- Calendar writes require a title and datetime.
- Reminder-style calendar items default to an immediate alarm when the planner does not specify an alarm.
- Return a concise message when the planned action is missing required arguments.
