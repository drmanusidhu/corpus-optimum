"""
oura.py — Fetch relevant Oura data for the agent's daily briefing.
"""
import os
import requests
from datetime import date, timedelta


BASE_URL = "https://api.ouraring.com/v2/usercollection"


def _headers():
    return {"Authorization": f"Bearer {os.environ['OURA_PERSONAL_ACCESS_TOKEN']}"}


def _get(endpoint: str, params: dict) -> dict:
    r = requests.get(f"{BASE_URL}/{endpoint}", headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_daily_snapshot(for_date: date | None = None) -> dict:
    """
    Return a compact dict of Oura metrics for the given date (defaults to today).
    Used as the biometric backbone of every agent message.
    """
    target = for_date or date.today()
    d_str = target.isoformat()
    # Oura sleep scores refer to the morning of the day being scored,
    # but the sleep session itself is the prior night.
    prior = (target - timedelta(days=1)).isoformat()

    snapshot = {"date": d_str}

    # ── Readiness ─────────────────────────────────────────────────────────────
    try:
        r = _get("daily_readiness", {"start_date": d_str, "end_date": d_str})
        if r.get("data"):
            rd = r["data"][0]
            c = rd.get("contributors", {})
            snapshot["readiness"] = {
                "score": rd.get("score"),
                "hrv_balance": c.get("hrv_balance"),
                "sleep_balance": c.get("sleep_balance"),
                "recovery_index": c.get("recovery_index"),
                "resting_hr": c.get("resting_heart_rate"),
                "body_temp_dev": rd.get("temperature_deviation"),
            }
    except Exception as e:
        snapshot["readiness_error"] = str(e)

    # ── Sleep ─────────────────────────────────────────────────────────────────
    try:
        r = _get("daily_sleep", {"start_date": d_str, "end_date": d_str})
        if r.get("data"):
            sd = r["data"][0]
            c = sd.get("contributors", {})
            snapshot["sleep_summary"] = {
                "score": sd.get("score"),
                "deep_sleep": c.get("deep_sleep"),
                "rem_sleep": c.get("rem_sleep"),
                "efficiency": c.get("efficiency"),
                "restfulness": c.get("restfulness"),
                "timing": c.get("timing"),
                "total_sleep": c.get("total_sleep"),
                "latency": c.get("latency"),
            }
    except Exception as e:
        snapshot["sleep_error"] = str(e)

    # ── Detailed sleep (bedtimes, HRV, durations) ─────────────────────────────
    try:
        r = _get("sleep", {"start_date": prior, "end_date": d_str})
        long_sleeps = [s for s in r.get("data", []) if s.get("type") == "long_sleep"
                       and s.get("day") == d_str]
        if long_sleeps:
            ls = long_sleeps[0]
            snapshot["sleep_detail"] = {
                "bedtime_start": ls.get("bedtime_start"),
                "bedtime_end": ls.get("bedtime_end"),
                "total_minutes": round((ls.get("total_sleep_duration") or 0) / 60),
                "deep_minutes": round((ls.get("deep_sleep_duration") or 0) / 60),
                "rem_minutes": round((ls.get("rem_sleep_duration") or 0) / 60),
                "avg_hrv": ls.get("average_hrv"),
                "lowest_hr": ls.get("lowest_heart_rate"),
                "avg_hr": round(ls.get("average_heart_rate") or 0, 1),
                "restless_periods": ls.get("restless_periods"),
                "efficiency_pct": ls.get("efficiency"),
            }
    except Exception as e:
        snapshot["sleep_detail_error"] = str(e)

    # ── HRV / Stress / Resilience ─────────────────────────────────────────────
    try:
        r = _get("daily_stress", {"start_date": d_str, "end_date": d_str})
        if r.get("data"):
            st = r["data"][0]
            snapshot["stress"] = {
                "stress_high": st.get("stress_high"),
                "recovery_high": st.get("recovery_high"),
                "day_summary": st.get("day_summary"),
            }
    except Exception as e:
        snapshot["stress_error"] = str(e)

    try:
        r = _get("daily_resilience", {"start_date": d_str, "end_date": d_str})
        if r.get("data"):
            res = r["data"][0]
            snapshot["resilience"] = {
                "level": res.get("level"),
                "contributors": res.get("contributors", {}),
            }
    except Exception as e:
        snapshot["resilience_error"] = str(e)

    # ── Activity ──────────────────────────────────────────────────────────────
    try:
        r = _get("daily_activity", {"start_date": d_str, "end_date": d_str})
        if r.get("data"):
            act = r["data"][0]
            snapshot["activity"] = {
                "score": act.get("score"),
                "steps": act.get("steps"),
                "active_calories": act.get("active_calories"),
                "high_activity_time": round((act.get("high_activity_time") or 0) / 60),  # mins
                "medium_activity_time": round((act.get("medium_activity_time") or 0) / 60),
                "sedentary_time": round((act.get("sedentary_time") or 0) / 60),
                "target_calories": act.get("target_calories"),
            }
    except Exception as e:
        snapshot["activity_error"] = str(e)

    return snapshot


def fetch_7day_trend() -> list[dict]:
    """Return last 7 days of readiness + sleep scores for trend context."""
    today = date.today()
    start = (today - timedelta(days=7)).isoformat()
    end = today.isoformat()
    trend = {}

    try:
        r = _get("daily_readiness", {"start_date": start, "end_date": end})
        for item in r.get("data", []):
            d = item["day"]
            trend.setdefault(d, {})["readiness"] = item.get("score")
            trend[d]["hrv_balance"] = (item.get("contributors") or {}).get("hrv_balance")
    except Exception:
        pass

    try:
        r = _get("daily_sleep", {"start_date": start, "end_date": end})
        for item in r.get("data", []):
            d = item["day"]
            trend.setdefault(d, {})["sleep"] = item.get("score")
    except Exception:
        pass

    return [{"date": d, **v} for d, v in sorted(trend.items())]
