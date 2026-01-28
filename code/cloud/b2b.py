# b2b.py
# b2b.py
import time, math
from typing import Dict, Any
from flask import Blueprint, request, jsonify, render_template
from extensions import db

b2b_bp = Blueprint("b2b", __name__)

class B2BLead(db.Model):
    __tablename__ = "b2b_leads"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.Float, default=lambda: time.time())
    company_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    payload = db.Column(db.JSON)
    estimate = db.Column(db.JSON)

def compute_b2b_estimate(p: Dict[str, Any]) -> Dict[str, Any]:
    # -------- Inputs (frontend keys) --------
    places = max(1, int(p.get("places", 10)))
    lanes = max(1, int(p.get("lanes", 1)))

    sensors = max(0, int(p.get("sensors_count", places)))
    anpr = max(0, int(p.get("anpr_cams", 2)))
    displays = max(0, int(p.get("displays", 1)))

    billing = (p.get("billing_model") or "hourly").lower()  # hourly / annual / lifetime
    rate = float(p.get("rate", 2.0))
    occupancy = min(1.0, max(0.0, float(p.get("occupancy", 60)) / 100.0))
    usage = float(p.get("usage", 2.5))  # hours/day/place OR subscribers OR customers/year

    security = (p.get("security_level") or "standard").lower()  # basic/standard/high
    hosting = (p.get("hosting") or "cloud").lower()             # cloud/hybrid/onprem
    integrations = (p.get("integrations") or "api").lower()     # none/api/erp/sso

    kwh_price = float(p.get("kwh_price", 0.22))

    # -------- Unit costs (tune later) --------
    unit_sensor = {"ground": 65, "overhead": 90, "camera_occupancy": 220}.get(p.get("sensor_type"), 65)
    unit_anpr = 550
    unit_display = 750
    unit_lane_hw = 1600  # barrier + controller per lane (rough)

    base_backend = 2200  # server + network + setup
    base_soft = 1200     # dashboards + basic software

    mult_security = {"basic": 1.0, "standard": 1.15, "high": 1.35}.get(security, 1.15)
    mult_hosting = {"cloud": 1.0, "hybrid": 1.10, "onprem": 1.25}.get(hosting, 1.0)
    mult_integr = {"none": 1.0, "api": 1.10, "erp": 1.25, "sso": 1.20}.get(integrations, 1.10)

    # -------- CAPEX breakdown --------
    cap_sensors = sensors * unit_sensor
    cap_anpr = anpr * unit_anpr
    cap_displays = displays * unit_display
    cap_lanes = lanes * unit_lane_hw
    cap_base = base_backend + base_soft

    capex_raw = cap_sensors + cap_anpr + cap_displays + cap_lanes + cap_base
    capex_total = capex_raw * mult_security * mult_hosting * mult_integr

    # install days: baseline + scale with places + lanes
    install_days = 3 + int(math.ceil(places / 80.0)) + max(0, lanes - 1)
    install_cost = install_days * 750
    capex_total += install_cost

    # -------- Power / energy --------
    # rough averages
    power_w = sensors * 0.25 + anpr * 7.0 + displays * 10.0 + 25.0
    energy_kwh_month = (power_w / 1000.0) * 24.0 * 30.0
    energy_cost_month = energy_kwh_month * kwh_price

    # -------- OPEX --------
    # maintenance as % of CAPEX + connectivity/support base
    maintenance_month = capex_total * 0.045 / 12.0 + 140.0

    # -------- Revenue model (client final) --------
    if billing == "hourly":
        # usage = paid hours/day/place
        revenue_month = places * occupancy * max(0.0, usage) * rate * 30.0
    elif billing == "annual":
        # usage = subscribers count
        subs = max(0.0, usage)
        revenue_month = subs * rate / 12.0
    else:  # lifetime
        # usage = customers/year
        customers_year = max(0.0, usage)
        revenue_month = (customers_year * rate) / 12.0

    profit_month = revenue_month - maintenance_month - energy_cost_month
    payback_months = (capex_total / profit_month) if profit_month > 0 else None

    breakdown_lines = [
        {"label": "Capteurs d’occupation", "value": round(cap_sensors, 2)},
        {"label": "Caméras ANPR", "value": round(cap_anpr, 2)},
        {"label": "Afficheurs", "value": round(cap_displays, 2)},
        {"label": "Barrières / voies", "value": round(cap_lanes, 2)},
        {"label": "Backend + logiciel", "value": round(cap_base, 2)},
        {"label": "Installation (estim.)", "value": round(install_cost, 2)},
    ]

    summary_text = (
        f"B2B Estimate\n"
        f"- Places: {places}\n"
        f"- CAPEX: {capex_total:.2f} EUR\n"
        f"- Maintenance/mois: {maintenance_month:.2f} EUR\n"
        f"- Energie/mois: {energy_cost_month:.2f} EUR ({energy_kwh_month:.1f} kWh)\n"
        f"- Revenus/mois: {revenue_month:.2f} EUR\n"
        f"- Profit/mois: {profit_month:.2f} EUR\n"
        f"- Payback: {payback_months:.1f} mois\n" if payback_months else
        f"B2B Estimate\n"
        f"- Places: {places}\n"
        f"- CAPEX: {capex_total:.2f} EUR\n"
        f"- Profit/mois: {profit_month:.2f} EUR (payback n/a)\n"
    )

    return {
        "capex_total": round(capex_total, 2),
        "install_days": int(install_days),
        "maintenance_month": round(maintenance_month, 2),
        "power_w_avg": round(power_w, 1),
        "energy_kwh_month": round(energy_kwh_month, 2),
        "energy_cost_month": round(energy_cost_month, 2),
        "revenue_month": round(revenue_month, 2),
        "profit_month": round(profit_month, 2),
        "payback_months": round(payback_months, 1) if payback_months else None,
        "breakdown_lines": breakdown_lines,
        "summary_text": summary_text,
    }

@b2b_bp.route("/b2b")
def b2b_page():
    return render_template("b2b_quote.html")

@b2b_bp.route("/api/b2b/estimate", methods=["POST"])
def api_b2b_estimate():
    data = request.get_json(force=True) or {}
    estimate = compute_b2b_estimate(data)

    if data.get("email") or data.get("company_name"):
        lead = B2BLead(
            company_name=data.get("company_name", ""),
            email=data.get("email", ""),
            payload=data,
            estimate=estimate,
        )
        db.session.add(lead)
        db.session.commit()

    return jsonify({"status": "ok", "estimate": estimate})
