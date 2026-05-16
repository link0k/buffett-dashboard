from typing import Dict

def score_roic(roic: float) -> float:
    if roic >= 0.20: return 100.0
    elif roic >= 0.15: return 80.0 + (roic - 0.15) / 0.05 * 20
    elif roic >= 0.10: return 60.0 + (roic - 0.10) / 0.05 * 20
    elif roic >= 0.05: return 30.0 + (roic - 0.05) / 0.05 * 30
    else: return max(0, roic / 0.05 * 30)

def score_moat_rules(metrics: Dict) -> float:
    score = 0
    gm = metrics.get("gross_margin", 0)
    score += 25 if gm >= 0.50 else (15 if gm >= 0.30 else (5 if gm >= 0.15 else 0))
    nm = metrics.get("net_margin", 0)
    score += 25 if nm >= 0.20 else (15 if nm >= 0.10 else (5 if nm >= 0.05 else 0))
    roic = metrics.get("roic", 0)
    score += 25 if roic >= 0.15 else (15 if roic >= 0.08 else (5 if roic >= 0.05 else 0))
    rg = metrics.get("revenue_growth", 0)
    score += 25 if rg >= 0.10 else (15 if rg >= 0.05 else (5 if rg >= 0 else 0))
    return score

def calculate_overall_score(dcf_margin: float, roic: float, moat_score: float, revenue_growth: float) -> Dict:
    dcf_score = min(100, max(0, 50 + dcf_margin * 200))
    roic_score = score_roic(roic)
    growth_score = min(100, max(0, revenue_growth * 500))
    overall = dcf_score * 0.30 + roic_score * 0.25 + moat_score * 0.30 + growth_score * 0.15
    grade = "A" if overall >= 80 else ("B" if overall >= 60 else "C")
    return {
        "overall": round(overall, 1),
        "grade": grade,
        "dcf_score": round(dcf_score, 1),
        "roic_score": round(roic_score, 1),
        "moat_score": round(moat_score, 1),
        "growth_score": round(growth_score, 1),
    }
