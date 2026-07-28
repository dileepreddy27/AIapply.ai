from career_autopilot import plans


def test_all_tiers_present():
    for key in ("basic", "starter", "pro", "power"):
        assert key in plans.PLAN_DEFINITIONS


def test_monthly_limits_increase_with_tier():
    starter = plans.get_plan_definition("starter").monthly_application_limit
    pro = plans.get_plan_definition("pro").monthly_application_limit
    power = plans.get_plan_definition("power").monthly_application_limit
    assert starter == 600 and pro == 1500 and power == 4500
    assert starter < pro < power


def test_basic_cannot_auto_apply():
    assert plans.get_plan_definition("basic").can_auto_apply is False
    assert plans.get_plan_definition("pro").can_auto_apply is True


def test_normalize_plan_falls_back_to_basic():
    assert plans.normalize_plan("nonsense") == "basic"
    assert plans.normalize_plan("power") == "power"


def test_resolve_plan_from_price_id(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_PRICE_POWER", "price_power")
    assert plans.resolve_plan_from_price_id("price_power") == "power"
    assert plans.resolve_plan_from_price_id("price_starter") == "starter"
    assert plans.resolve_plan_from_price_id("unknown") == "pro"  # default
    assert plans.resolve_plan_from_price_id("") == "pro"


def test_paid_plan_keys():
    assert plans.PAID_PLAN_KEYS == {"starter", "pro", "power"}
