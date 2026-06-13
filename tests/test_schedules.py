from dobby_app.scheduling.schedules import parse_schedule, rrule_to_cron


def test_parse_daily_schedule():
    parsed = parse_schedule("every day at 8:30")
    assert parsed.cron == {"hour": 8, "minute": 30}


def test_parse_weekly_schedule():
    parsed = parse_schedule("Sundays at 11")
    assert parsed.cron == {"day_of_week": "sun", "hour": 11, "minute": 0}


def test_parse_hourly_schedule():
    parsed = parse_schedule("every 2 hours")
    assert parsed.cron == {"hour": "*/2", "minute": 0}


def test_rrule_to_cron():
    parsed = rrule_to_cron("RRULE:FREQ=WEEKLY;BYHOUR=9;BYMINUTE=0;BYDAY=SU,MO")
    assert parsed.cron == {"hour": 9, "minute": 0, "day_of_week": "sun,mon"}
