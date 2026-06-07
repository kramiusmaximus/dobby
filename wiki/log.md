---
title: LLM Wiki Log
type: log
created: 2026-05-23
updated: 2026-06-07
status: active
tags: [log, second-brain]
sources: []
---

# LLM Wiki Log

Append-only chronological record of wiki activity.

## [2026-05-23] setup | Initialize LLM Wiki Second Brain

- Added LLM Wiki operating rules to `/Users/kramiusmaximus/projects/dobby/AGENTS.md`.
- Created the `wiki/` directory structure.
- Created `index.md` and `log.md`.
- Established folders for raw sources, assets, source summaries, concepts, projects, goals, calendar notes, decisions, questions, templates, and temporary work.

## [2026-05-23] ingest | LLM Wiki Idea File

- Stored the first raw source at `wiki/raw/sources/2026-05-23-llm-wiki-idea.md`.
- Created source page [[LLM Wiki Idea File]].
- Created concept page [[LLM Wiki Pattern]].
- Created project page [[Second Brain Operating Model]].
- Created goal page [[Personal Assistant Goals]].
- Created decision page [[Use Markdown Wiki As Second Brain]].
- Created question page [[Second Brain Open Questions]].

## [2026-05-23] ingest | Telegram Goals And Commitments

- Stored Telegram messages 1865 and 1866 as `wiki/raw/sources/2026-05-23-telegram-goals-and-commitments.md`.
- Created source page [[Telegram Goals And Commitments]].
- Created project page [[TouchDesigner Installation Art Portfolio]] for Mark's current main creative goal.
- Created goal page [[Mother Birthday Gift]] for the June 8 birthday present commitment.
- Created calendar page [[June 2026 Commitments]] for time-bound June items.
- Updated `wiki/index.md` with the new source, project, goal, and calendar links.

## [2026-05-23] query | Mother Birthday Gift Reminder Sync

- Attempted to create an Apple Reminders item for [[Mother Birthday Gift]].
- Apple Reminders access was denied for the local reminder tool, so no Apple reminder was created.
- Updated [[Mother Birthday Gift]] with the blocked sync status.

## [2026-05-23] query | Mother Birthday Gift Reminder Created

- Created Apple Reminders item `Buy/create mom's birthday present` in the `Reminders` list.
- Set due date to 2026-06-07 09:00 so the present is handled before the 2026-06-08 birthday.
- Synced the Apple Reminders ID into [[Mother Birthday Gift]].

## [2026-05-23] ingest | Telegram Orthodontist Reminder

- Retrieved Telegram voice message 1868 and saved it at `telegram_bot_cli/voice_messages/voice_1868.oga`.
- Stored the transcript as `wiki/raw/sources/2026-05-23-telegram-orthodontist-reminder.md`.
- Created source page [[Telegram Orthodontist Reminder]].
- Created calendar page [[May 2026 Commitments]] with the requested 2026-05-24 orthodontist appointment task.
- Attempted to use Apple Reminders, but macOS denied Reminders access to the local reminder tool, so no notification was created.
- Sent Telegram message 1869 to tell Mark the request was captured and that Apple Reminders notification creation is blocked until Reminders permission is enabled.

## [2026-05-23] query | Orthodontist Reminder Debug

- Rechecked `/opt/homebrew/bin/rem` and found Reminders access was now `full-access`.
- Confirmed no existing reminder had been created for 2026-05-24.
- Created Apple Reminders item `Book Yamas Clinic orthodontist appointment` in the `Reminders` list.
- Set due/alarm to 2026-05-24 09:00 MSK.
- Synced the Apple Reminders ID `388A4656-9938-4827-A169-4F1C4EF3AB66` into [[Telegram Orthodontist Reminder]] and [[May 2026 Commitments]].
- Sent Telegram message 1870 to tell Mark the reminder is now fixed and scheduled.

## [2026-05-24] ingest | Telegram Narjiss, Tasks, And Birthday Correction

- Retrieved Telegram messages 1875 through 1878.
- Stored the messages as `wiki/raw/sources/2026-05-24-telegram-narjiss-tasks-birthday-correction.md`.
- Copied Narjiss's Telegram profile photo to `wiki/raw/assets/telegram/narjiss-photo-telegram-1877.jpg`.
- Created source page [[Telegram Narjiss, Tasks, And Birthday Correction]].
- Created person page [[Narjiss]] with Mark-provided relationship context and profile photo reference.
- Added Mark's current task list to [[May 2026 Commitments]].
- Created [[July 2026 Commitments]] for Narjiss's early July departure and mom's corrected July 8 birthday.
- Updated [[Mother Birthday Gift]], [[June 2026 Commitments]], [[Telegram Goals And Commitments]], and `wiki/index.md` to reflect that Mark's mom's birthday is July 8, not June 8.

## [2026-05-24] lint | Obsidian Root Stubs And Project Suggestions

- Deleted empty root-level Obsidian stubs for `LLM Wiki Pattern`, `Personal Assistant Goals`, `Second Brain Open Questions`, and `Second Brain Operating Model`; canonical pages remain under `wiki/pages/`.
- Updated initial source and index links to use explicit Obsidian paths with aliases where canonical filenames differ from display titles.
- Created [[pages/projects/wiki-project-improvement-suggestions|Wiki Project Improvement Suggestions]] and added Mark's requested improvements plus Codex suggestions.
- Attempted Apple Reminders sync, but `rem` reported Reminders access as unavailable, so the existing June 7 reminder could not be moved in Apple Reminders.

## [2026-05-24] ingest | Telegram Motorcycle And Shoes Reminders

- Retrieved Telegram messages 1881 and 1882.
- Stored the messages as `wiki/raw/sources/2026-05-24-telegram-motorcycle-shoes-reminders.md`.
- Created source page [[Telegram Motorcycle And Shoes Reminders]].
- Added this week's motorcycle alarm and shoe cleaning/patch errands to [[May 2026 Commitments]].
- Attempted Apple Reminders authorization, but `rem` reported Reminders access as denied, so no Apple Reminders notifications were created.

## [2026-05-24] query | Reminders Access Debug

- Investigated why Telegram reminder sync was blocked.
- Confirmed old EventKit CLI 0.2.0 was installed at `/opt/homebrew/bin/rem`.
- Ran the AppleScript probe `tell application "Reminders" to get name of reminders`; after this, old EventKit CLI status reported `full-access`.
- Created Apple Reminders items for [[Telegram Motorcycle And Shoes Reminders]]:
  - `Get motorcycle alarm fixed`, due/alarm 2026-05-30 09:00 MSK, ID `9B9B7C69-4181-4BF2-BADE-D1BE100BE9B1`.
  - `Get shoes cleaned and patched`, due/alarm 2026-05-30 09:00 MSK, ID `D7CA5BE5-E7E4-4288-9EEF-7F074AC86A05`.
- Moved the existing mom birthday reminder `58DAE514-A94C-421B-8F6B-F51D4DEE05DC` to 2026-07-07 09:00 MSK for [[Mother Birthday Gift]].

## [2026-05-25] ingest | Telegram Daily Task Reminder Preference

- Retrieved Telegram message 1893.
- Stored the message as `wiki/raw/sources/2026-05-25-telegram-daily-task-reminder-preference.md`.
- Created source page [[Telegram Daily Task Reminder Preference]].
- Updated [[Personal Assistant Goals]] to clarify that daily task-list items should not automatically become Apple Reminders unless Mark explicitly asks for a reminder, notification, due date, or alert.

## [2026-05-25] ingest | Telegram Apartment Receiving Reminder

- Retrieved Telegram voice message 1895 and saved it at `telegram_bot_cli/voice_messages/voice_1895.oga`.
- Stored the transcript as `wiki/raw/sources/2026-05-25-telegram-apartment-receiving-reminder.md`.
- Created source page [[Telegram Apartment Receiving Reminder]].
- Added the 2026-05-29 11:00 MSK apartment receiving event to [[May 2026 Commitments]].
- Attempted Apple Reminders initialization and authorization with the old EventKit CLI, but it still reported Reminders access as `not-determined`, so no Apple Reminders notification was created.

## [2026-05-25] query | Reminders Authorization Fix

- Confirmed the working AppleScript access probe is `tell application "Reminders" to get name of every list`.
- Confirmed `old EventKit CLI status check` now reports `authorized: true` and `status: full-access`.
- Created `/Users/kramiusmaximus/projects/dobby/scripts/reminders_preflight.sh` so future runs use the working probe before reminder operations.
- Updated `AGENTS.md` with the Apple Reminders CLI rule and the known-bad probe to avoid.
- Created Apple Reminders item `Receive apartment`, due 2026-05-29 11:00 MSK, alarm 2026-05-29 09:00 MSK, priority high, ID `BF262E81-256D-43C7-B12C-994253559D4C`.
- Synced the Apple Reminders ID into [[Telegram Apartment Receiving Reminder]] and [[May 2026 Commitments]].

## [2026-05-26] ingest | Telegram Priorities And Calendar Removal

- Retrieved Telegram messages 1902 and 1903.
- Stored the messages as `wiki/raw/sources/2026-05-26-telegram-priorities-and-calendar-removal.md`.
- Created source page [[Telegram Priorities And Calendar Removal]].
- Created [[Current Creative Project Priorities]] for Mark's data fusion handtracking MVP, Neo Shopper, and activity expansion focus list.
- Created [[Activity Schedule Expansion]] for candidate recurring activities: BJJ, acting, choir, or something more extreme.
- Found the 2026-05-28 all-day `Принимая ПП` event in the `Личный` calendar and recorded the deletion request in [[May 2026 Commitments]].
- Calendar deletion remains blocked because the current connector exposes listing/updating but not deletion, and direct EventKit scripting was not authorized in the sandbox.
- After Mark suggested the binary tool, tried `/opt/homebrew/bin/ical list --from 2026-05-28 --to 2026-05-28 --calendar 'Личный' --all-day --search 'Принимая ПП' --output json`; `ical` reported Calendar access denied, so it could not delete the event.
- Mark clarified that DOBBY should request Calendar access for `ical`; after running an access-triggering `ical` command, `ical calendars --output json` succeeded.
- Deleted the exact `Принимая ПП` event with `/opt/homebrew/bin/ical delete --id 'FB1BE607-1654-46B9-85FF-AC5FBB01E0AB:6B67FAE7-E20B-4A55-B79E-17A11C224786' --force` and verified the May 28 search returned `[]`.

## [2026-05-28] maintenance | Apple Reminders CLI Replacement

- Installed `BRO3886/tap/rem-cli`, providing `/opt/homebrew/bin/rem`.
- Verified `rem lists --output json --no-color` can read Apple Reminders lists.
- Smoke-tested `rem add` and `rem delete` with a temporary reminder, then verified the temporary reminder was removed.
- Updated DOBBY operating guidance and automation instructions to use `rem` for Apple Reminders work.

## [2026-06-04] ingest | Telegram Task List And Birthday Gift Idea

- Retrieved Telegram messages 1938 and 1939.
- Stored the messages and transcript as `wiki/raw/sources/2026-06-04-telegram-task-list-and-birthday-gift-idea.md`.
- Created source page [[Telegram Task List And Birthday Gift Idea]].
- Updated [[Mother Birthday Gift]] with Mark's initial concept: an engraving-like drawing featuring his mom, Sonya, Vanya, and a motorcycle.
- Preserved the previously corrected birthday date, July 8, 2026, despite the voice note mentioning June 8.
- Did not create Apple Reminders: ordinary daily task lists should not automatically become reminders, and Reminders access also failed after warm-up, preflight, and direct `rem` read retry.

## [2026-06-07] lint | Wiki Structure And Reminder Audit

- Read `wiki/index.md` first and audited the compiled wiki structure under `wiki/pages/`.
- Verified there are no unresolved wikilinks, no empty root-level Obsidian stub notes, and no missing required frontmatter fields in the compiled wiki.
- Normalized `wiki/index.md` to use explicit canonical `wiki/pages/...` wikilinks for source, project, people, goal, and calendar entries whose filenames differ from their display titles.
- Reviewed project improvement notes and added new Codex suggestions about historical page lifecycle review and recurring Reminders access drift.
- Attempted reminder sync verification with `scripts/reminders_preflight.sh`, but EventKit/Reminders access was denied in this run, so Apple Reminders state could not be re-verified against wiki reminder IDs.
