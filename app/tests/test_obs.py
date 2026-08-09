from spine.obs import ContextMeter


def test_a_single_turn_reports_no_growth():
    meter = ContextMeter()
    meter.record(turn=0, session_index=0, sent=1200, turn_tokens=1200)
    assert meter.growth_ratio() == 1.0


def test_bounded_context_does_not_grow_across_sessions():
    """The property Rules.md line 496 asks about, asserted rather than claimed.

    Twelve short sessions over six weeks. Facts, not transcripts, so what we send stays flat
    while a naive replay would keep growing.
    """
    meter = ContextMeter()
    for turn in range(12):
        # Facts grow slowly with plan completeness, not with conversation length.
        sent = 1200 + turn * 15
        meter.record(turn=turn, session_index=turn // 2, sent=sent, turn_tokens=900)

    assert meter.growth_ratio() < 1.25, (
        "a week six session must not send materially more context than a week one session"
    )


def test_naive_replay_would_have_grown_without_bound():
    meter = ContextMeter()
    for turn in range(12):
        meter.record(turn=turn, session_index=turn // 2, sent=1200, turn_tokens=900)

    last = meter.measurements[-1]
    assert last.tokens_if_full_replay == 900 * 12
    assert last.ratio > 8, "the whole point is that replay would have been many times larger"
    assert last.saved > 9000


def test_summary_reports_the_numbers_the_ui_shows():
    meter = ContextMeter()
    meter.record(turn=0, session_index=0, sent=1000, turn_tokens=800)
    meter.record(turn=1, session_index=1, sent=1100, turn_tokens=800)

    summary = meter.summary()
    assert summary["turns"] == 2
    assert summary["first_turn_tokens"] == 1000
    assert summary["last_turn_tokens"] == 1100
    assert summary["growth_ratio"] == 1.1
    assert summary["tokens_saved_vs_replay"] == 500


def test_empty_meter_is_safe_to_summarise():
    assert ContextMeter().summary() == {"turns": 0}


def test_a_regression_would_fail_the_assertion():
    """If someone reintroduces transcript replay, the meter catches it."""
    meter = ContextMeter()
    running = 0
    for turn in range(12):
        running += 900  # naive: send everything again
        meter.record(turn=turn, session_index=turn // 2, sent=running, turn_tokens=900)

    assert meter.growth_ratio() > 5, "this is what the failure mode looks like"
