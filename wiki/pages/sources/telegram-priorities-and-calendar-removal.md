---
title: Telegram Priorities And Calendar Removal
type: source
created: 2026-05-26
updated: 2026-05-26
status: active
tags: [telegram, priorities, calendar]
sources:
  - ../../raw/sources/2026-05-26-telegram-priorities-and-calendar-removal.md
---

# Telegram Priorities And Calendar Removal

## Summary

Mark sent a short current-focus list:

- Build a data fusion handtracking MVP.
- Finish Neo Shopper.
- Add a new recurring activity to the schedule: BJJ, acting, choir, or something more extreme.

Mark also asked DOBBY to remove the May 28, 2026 all-day calendar event `Принимая ПП`, which had alarms.

## Calendar Handling

The event was found on 2026-05-26 in the `Личный` calendar:

- Title: `Принимая ПП`
- Date: 2026-05-28 all-day
- Alarms visible through the calendar connector: 30 and 900 minutes before
- Event ID: `FB1BE607-1654-46B9-85FF-AC5FBB01E0AB:6B67FAE7-E20B-4A55-B79E-17A11C224786`

DOBBY could update the event note, but the available calendar connector did not expose deletion, and direct EventKit scripting was not authorized in the current sandbox. Mark suggested using the `/opt/homebrew/bin/ical` binary.

On 2026-05-26, DOBBY triggered Calendar access for `ical` by running an `ical` calendar command. After access became available, DOBBY deleted the exact event by ID and verified that no matching all-day `Принимая ПП` event remained on 2026-05-28 in the `Личный` calendar.

## Related Pages

- [[Current Creative Project Priorities]]
- [[Activity Schedule Expansion]]
- [[May 2026 Commitments]]
