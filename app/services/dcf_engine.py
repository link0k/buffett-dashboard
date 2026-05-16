from typing import List

def calculate_dcf(
    fcf_history: List[float],
    wacc: float = 0.065,
    terminal_growth: float = 0.025,
    projection_years: int = 5,
) -> float:
    if not fcf_history:
        return 0.0
    base_fcf = sum(fcf_history[-3:]) / min(3, len(fcf_history))
    growth_rate = 0.08
    projected_fcfs = []
    for year in range(1, projection_years + 1):
        fcf = base_fcf * (1 + growth_rate) ** year
        discounted = fcf / (1 + wacc) ** year
        projected_fcfs.append(discounted)
    terminal_fcf = projected_fcfs[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    discounted_tv = terminal_value / (1 + wacc) ** projection_years
    return sum(projected_fcfs) + discounted_tv

def get_dcf_margin(current_price: float, dcf_value: float) -> float:
    if current_price <= 0:
        return 0.0
    return (dcf_value - current_price) / current_price
