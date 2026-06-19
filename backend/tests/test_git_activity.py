"""Pure git-activity summarizer."""

from datetime import datetime, timedelta, timezone

from app.core.domain.git_insights import summarize_activity

_NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)  # a Thursday


def test_weeks_are_fixed_length_and_recent_bucket_counts():
    commits = [
        (_NOW, "Alice"),
        (_NOW - timedelta(days=1), "Bob"),  # same week
        (_NOW - timedelta(days=8), "Alice"),  # previous week
        (_NOW - timedelta(days=40), "Carol"),  # ~6 weeks ago
    ]
    s = summarize_activity(commits, _NOW)
    assert len(s.weeks) == 12
    assert s.weeks[-1].commits == 2  # this week
    assert s.weeks[-2].commits == 1  # last week
    assert s.weeks[0].period_start < s.weeks[-1].period_start


def test_weekday_histogram_and_active_authors():
    commits = [
        (_NOW, "Alice"),  # Thursday
        (_NOW - timedelta(days=1), "Bob"),  # Wednesday
        (_NOW - timedelta(days=8), "Alice"),  # Wednesday
    ]
    s = summarize_activity(commits, _NOW)
    assert len(s.by_weekday) == 7
    assert s.by_weekday[2] == 2  # two Wednesday commits
    assert s.by_weekday[3] == 1  # one Thursday commit
    assert s.active_contributors == 2
    assert s.author_commits_90d["Alice"] == 2
    assert s.author_last_active["Alice"] == _NOW.date().isoformat()


def test_empty_window_is_safe():
    s = summarize_activity([], _NOW)
    assert len(s.weeks) == 12
    assert all(w.commits == 0 for w in s.weeks)
    assert s.by_weekday == [0, 0, 0, 0, 0, 0, 0]
    assert s.active_contributors == 0
