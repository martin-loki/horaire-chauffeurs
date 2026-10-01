#!/usr/bin/env python3
"""Génère une page HTML statique (lecture seule) de l'horaire d'un chauffeur
à partir de data.json, pour publication sur GitHub Pages.

Usage: python3 generate.py data.json index.html
"""
import json
import sys
from datetime import datetime, timezone, date

TYPE_LABELS = {
    "production": "Production",
    "marketing": "Marketing",
    "livraison": "Livraison",
    "transport": "Transport",
    "conge": "Congé / OFF",
}

STATUS_LABELS = {
    "confirme": "Confirmé",
    "provisoire": "Provisoire",
    "annule": "Annulé",
}


def fmt_date_fr(d):
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    return "%s %d %s %d" % (jours[dt.weekday()], dt.day, mois[dt.month - 1], dt.year)


def esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_html(payload):
    driver = payload.get("driver", {})
    driver_name = driver.get("name", "Chauffeur")
    assignments = payload.get("assignments", [])

    today = date.today()

    # Garde les affectations d'aujourd'hui moins 2 jours (contexte récent) et au-delà.
    def keep(a):
        try:
            d = datetime.strptime(a["startDate"], "%Y-%m-%d").date()
        except Exception:
            return True
        return (d - today).days >= -2

    assignments = [a for a in assignments if keep(a)]
    assignments.sort(key=lambda a: (a.get("startDate", ""), a.get("startTime", "")))

    # Regroupe par date
    groups = []
    last_date = None
    for a in assignments:
        if a["startDate"] != last_date:
            groups.append((a["startDate"], []))
            last_date = a["startDate"]
        groups[-1][1].append(a)

    rows_html = []
    if not groups:
        rows_html.append(
            '<p class="empty">Aucune affectation à venir pour le moment.</p>'
        )
    for d, items in groups:
        try:
            is_today = datetime.strptime(d, "%Y-%m-%d").date() == today
        except Exception:
            is_today = False
        today_tag = ' <span class="today-tag">Aujourd\'hui</span>' if is_today else ""
        rows_html.append('<div class="day-group%s">' % (" is-today" if is_today else ""))
        rows_html.append('<h2>%s%s</h2>' % (esc(fmt_date_fr(d)), today_tag))
        for a in items:
            status = a.get("status", "confirme")
            status_label = STATUS_LABELS.get(status, status)
            type_label = TYPE_LABELS.get(a.get("type"), a.get("type", ""))
            time_str = "Toute la journée" if a.get("allDay") else (
                "%s" % a.get("startTime", "")
                + (" – %s" % a["endTime"] if a.get("endTime") else "")
            )
            route = ""
            if a.get("routeFrom") or a.get("routeTo"):
                route = '<div class="route">%s → %s</div>' % (
                    esc(a.get("routeFrom") or "?"), esc(a.get("routeTo") or "?")
                )
            notes = (
                '<div class="notes">%s</div>' % esc(a["notes"])
                if a.get("notes") else ""
            )
            unit = (' · <span class="unit">%s</span>' % esc(a["unit"])) if a.get("unit") else ""
            rows_html.append(
                '<div class="assignment status-%s">'
                '<div class="a-time">%s</div>'
                '<div class="a-body">'
                '<div class="a-title">%s%s</div>'
                '<div class="a-meta">%s · %s%s</div>'
                '%s%s'
                '</div>'
                '</div>' % (
                    esc(status),
                    esc(time_str),
                    esc(a.get("title", "")),
                    unit,
                    esc(type_label),
                    esc(a.get("location", "")) and (" · " + esc(a["location"])) or "",
                    esc(status_label),
                    route,
                    notes,
                )
            )
        rows_html.append('</div>')

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return HTML_TEMPLATE.format(
        driver_name=esc(driver_name),
        rows="\n".join(rows_html),
        generated_at=generated_at,
    )


HTML_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Horaire — {driver_name}</title>
<style>
  :root {{
    --navy: #2c6e8f; --gold: #8a6413; --ink: #181c1f; --muted: #5b646c;
    --bg: #faf9f6; --card: #ffffff; --border: #e4e0d4;
    --ok: #2f6d47; --prov: #b8891a; --cancel: #9aa3aa;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0 0 40px; background: var(--bg); color: var(--ink);
    font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.4;
  }}
  header {{
    background: var(--navy); color: #fff; padding: 20px 16px 18px;
  }}
  header h1 {{ margin: 0; font-size: 1.3rem; }}
  header .sub {{ font-size: 0.85rem; opacity: 0.85; margin-top: 4px; }}
  main {{ max-width: 640px; margin: 0 auto; padding: 16px; }}
  .day-group {{ margin-bottom: 22px; }}
  .day-group h2 {{
    font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.3px;
    color: var(--muted); border-bottom: 1px solid var(--border);
    padding-bottom: 6px; margin: 0 0 10px;
  }}
  .day-group.is-today h2 {{ color: var(--navy); }}
  .today-tag {{
    background: var(--navy); color: #fff; font-size: 0.7rem; padding: 2px 8px;
    border-radius: 10px; text-transform: none; letter-spacing: 0;
  }}
  .assignment {{
    display: flex; gap: 12px; background: var(--card); border: 1px solid var(--border);
    border-left: 4px solid var(--ok); border-radius: 6px; padding: 10px 12px; margin-bottom: 8px;
  }}
  .assignment.status-provisoire {{ border-left-color: var(--prov); }}
  .assignment.status-annule {{ border-left-color: var(--cancel); opacity: 0.6; }}
  .assignment.status-annule .a-title {{ text-decoration: line-through; }}
  .a-time {{ min-width: 70px; font-weight: 600; font-size: 0.85rem; color: var(--navy); }}
  .a-title {{ font-weight: 600; margin-bottom: 2px; }}
  .unit {{ font-weight: 400; color: var(--muted); }}
  .a-meta {{ font-size: 0.8rem; color: var(--muted); }}
  .route {{ font-size: 0.8rem; color: var(--muted); margin-top: 3px; }}
  .notes {{ font-size: 0.8rem; color: var(--muted); margin-top: 3px; font-style: italic; }}
  .empty {{ color: var(--muted); text-align: center; padding: 40px 0; }}
  footer {{
    max-width: 640px; margin: 20px auto 0; padding: 12px 16px 0; border-top: 1px solid var(--border);
    font-size: 0.75rem; color: var(--muted); text-align: center;
  }}
</style>
</head>
<body>
<header>
  <h1>Horaire — {driver_name}</h1>
  <div class="sub">Loki Coach · Consultation seule · Mis à jour automatiquement plusieurs fois par jour</div>
</header>
<main>
{rows}
</main>
<footer>
  Généré automatiquement depuis Feuille de Route — dernière mise à jour : {generated_at}.<br>
  Pour toute modification, contacte Martin Goizioux ou Maxime Boulianne.
</footer>
</body>
</html>
"""

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "index.html"
    with open(src, "r", encoding="utf-8") as f:
        payload = json.load(f)
    html = build_html(payload)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote %s (%d bytes)" % (dst, len(html)))
