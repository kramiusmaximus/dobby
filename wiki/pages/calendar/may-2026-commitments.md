---
title: May 2026 Commitments
type: calendar
created: 2026-05-23
updated: 2026-05-26
status: active
tags: [calendar, reminders, health]
sources:
  - ../sources/telegram-orthodontist-reminder.md
  - ../sources/telegram-narjiss-tasks-birthday-correction.md
  - ../sources/telegram-motorcycle-shoes-reminders.md
  - ../sources/telegram-apartment-receiving-reminder.md
  - ../sources/telegram-priorities-and-calendar-removal.md
---

# May 2026 Commitments

## 2026-05-24

### Book Yamas Clinic Orthodontist Appointment

- Action: Book an appointment with Yamas Clinic orthodontist.
- Context: Mark needs help fixing a problem with his braces.
- Source: [[Telegram Orthodontist Reminder]]
- Apple Reminders sync: created on 2026-05-23 after Reminders access became available.
  - List: `Reminders`
  - Due/alarm: 2026-05-24 09:00 MSK
  - Apple Reminders ID: `388A4656-9938-4827-A169-4F1C4EF3AB66`

### Telegram Task List

- Move all of Narjiss' stuff into Mark's room.
- Find a helmet solution for the bike.
- Ceramics.
- Church.
- Gym? Mark marked this as tentative.
- Unfinished placeholder item: `...`.

Source: [[Telegram Narjiss, Tasks, And Birthday Correction]]

## 2026-05-29

### Receive Apartment

- Event: Mark needs to receive his apartment.
- Time: 2026-05-29 11:00 MSK.
- Requested reminder: morning of 2026-05-29.
- Importance: Mark described this as a very important event.
- Source: [[Telegram Apartment Receiving Reminder]]
- Apple Reminders sync: blocked on 2026-05-25 because `rem` reported Reminders access as `not-determined` after the requested Reminders initialization check and authorization attempt.
- Apple Reminders sync: created on 2026-05-25 after the working Reminders access probe restored access.
  - List: `Reminders`
  - Due: 2026-05-29 11:00 MSK
  - Alarm: 2026-05-29 09:00 MSK
  - Priority: high
  - Apple Reminders ID: `BF262E81-256D-43C7-B12C-994253559D4C`

## Calendar Cleanup Requests

### Remove `Принимая ПП`

- Requested by Mark via Telegram on 2026-05-26.
- Target event: `Принимая ПП`, all-day event on 2026-05-28 in the `Личный` calendar.
- Alarms visible through the calendar connector: 30 and 900 minutes before.
- DOBBY found the event and added a note recording the deletion request.
- Mark suggested using `/opt/homebrew/bin/ical`; DOBBY triggered Calendar access for `ical`, then deleted the exact event by ID on 2026-05-26.
- Deletion status: completed and verified with `/opt/homebrew/bin/ical list --from 2026-05-28 --to 2026-05-28 --calendar 'Личный' --all-day --search 'Принимая ПП' --output json`, which returned an empty list.
- Source: [[Telegram Priorities And Calendar Removal]]

## Week Ending 2026-05-30

### Motorcycle Alarm

- Action: Get the alarm fixed on Mark's motorcycle.
- Requested timing: This week.
- Source: [[Telegram Motorcycle And Shoes Reminders]]
- Apple Reminders sync: blocked on 2026-05-24 because `rem` reported Reminders access as denied.
- Apple Reminders sync: created on 2026-05-24 after Reminders access became available.
  - List: `Reminders`
  - Due/alarm: 2026-05-30 09:00 MSK
  - Apple Reminders ID: `9B9B7C69-4181-4BF2-BADE-D1BE100BE9B1`

### Shoes Cleaning And Patch

- Action: Get Mark's shoes cleaned and patched.
- Requested timing: This week.
- Source: [[Telegram Motorcycle And Shoes Reminders]]
- Apple Reminders sync: blocked on 2026-05-24 because `rem` reported Reminders access as denied.
- Apple Reminders sync: created on 2026-05-24 after Reminders access became available.
  - List: `Reminders`
  - Due/alarm: 2026-05-30 09:00 MSK
  - Apple Reminders ID: `D7CA5BE5-E7E4-4288-9EEF-7F074AC86A05`
