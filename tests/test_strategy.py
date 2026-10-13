from adultcam.strategy import build_ten_hour_plan, build_month_plan


def test_ten_hour_plan_has_slots_and_recovery_windows():
    plan=build_ten_hour_plan()
    assert len(plan)==10
    assert [p['hour'] for p in plan] == list(range(1,11))
    assert len({p['goal'] for p in plan}) >= 5
    assert any(p['category']=='RECOVERY' for p in plan)
    assert all(p['source']=='TEMPLATE_NOT_LIVE' for p in plan)


def test_month_plan_does_not_fabricate_revenue():
    days=build_month_plan()
    assert len(days)==30
    assert [d['day'] for d in days]==list(range(1,31))
    assert days[0]['phase']=='MARKET_ENTRY'
    assert days[-1]['phase']=='RETENTION'
    assert all(d['estimated_revenue'] is None for d in days)
