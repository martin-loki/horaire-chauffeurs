#!/usr/bin/env python3
"""Génère une page HTML statique (lecture seule) de l'horaire d'un chauffeur
à partir de data.json, pour publication sur GitHub Pages.

Vues : Agenda (liste chronologique), Semaine, Mois — navigation en JS côté client,
sans rechargement ni appel réseau (toutes les données sont déjà dans la page).

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

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


def fmt_date_fr(d):
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    return "%s %d %s %d" % (JOURS_FR[dt.weekday()], dt.day, MOIS_FR[dt.month - 1], dt.year)


def esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_html(payload):
    driver = payload.get("driver", {})
    driver_name = driver.get("name", "Chauffeur")
    first_name = driver_name.strip().split(" ")[0] if driver_name.strip() else "Chauffeur"
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

    # ---- Vue Agenda (rendue côté serveur, identique à avant) ----
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

    # ---- Données brutes pour les vues Semaine / Mois (construites en JS) ----
    # On ne garde que les champs utiles au rendu, pour une page plus légère.
    slim = []
    for a in assignments:
        slim.append({
            "startDate": a.get("startDate", ""),
            "endDate": a.get("endDate") or a.get("startDate", ""),
            "startTime": a.get("startTime", ""),
            "endTime": a.get("endTime", ""),
            "allDay": bool(a.get("allDay")),
            "title": a.get("title", ""),
            "status": a.get("status", "confirme"),
            "type": a.get("type", ""),
            "location": a.get("location", ""),
            "unit": a.get("unit", ""),
        })
    data_json = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")
    today_json = json.dumps(today.strftime("%Y-%m-%d"))

    return HTML_TEMPLATE.format(
        driver_name=esc(first_name),
        rows=esc_keep_tags("\n".join(rows_html)),
        generated_at=generated_at,
        data_json=data_json,
        today_json=today_json,
    )


def esc_keep_tags(s):
    # rows_html est déjà du HTML construit (pas besoin de ré-échapper) ;
    # fonction conservée pour lisibilité du point d'assemblage.
    return s


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
  main {{ max-width: 720px; margin: 0 auto; padding: 16px; }}

  /* Onglets de vue */
  .tabs {{
    display: flex; gap: 6px; margin-bottom: 18px; background: var(--card);
    border: 1px solid var(--border); border-radius: 8px; padding: 4px;
  }}
  .tab-btn {{
    flex: 1; border: none; background: transparent; color: var(--muted);
    font-size: 0.85rem; font-weight: 600; padding: 8px 10px; border-radius: 6px;
    cursor: pointer; font-family: inherit;
  }}
  .tab-btn.active {{ background: var(--navy); color: #fff; }}
  .view {{ display: none; }}
  .view.active {{ display: block; }}

  /* Agenda */
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

  /* Navigation Semaine / Mois */
  .nav-bar {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 14px; gap: 8px;
  }}
  .nav-bar .nav-label {{ font-weight: 600; font-size: 0.95rem; text-transform: capitalize; }}
  .nav-btn {{
    border: 1px solid var(--border); background: var(--card); color: var(--navy);
    border-radius: 6px; padding: 6px 10px; font-size: 0.85rem; cursor: pointer; font-family: inherit;
  }}
  .nav-today {{
    border: 1px solid var(--navy); background: var(--navy); color: #fff;
    border-radius: 6px; padding: 6px 10px; font-size: 0.78rem; cursor: pointer; font-family: inherit;
  }}
  .nav-group {{ display: flex; gap: 6px; }}

  /* Semaine */
  .week-grid {{ display: flex; flex-direction: column; gap: 8px; }}
  .week-day {{
    background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px;
  }}
  .week-day.is-today {{ border-color: var(--navy); border-width: 2px; }}
  .week-day .wd-head {{
    font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .week-day.is-today .wd-head {{ color: var(--navy); }}
  .wd-event {{
    font-size: 0.8rem; padding: 4px 8px; margin-bottom: 4px; border-left: 3px solid var(--ok);
    background: var(--bg); border-radius: 4px;
  }}
  .wd-event.status-provisoire {{ border-left-color: var(--prov); }}
  .wd-event.status-annule {{ border-left-color: var(--cancel); opacity: 0.6; text-decoration: line-through; }}
  .wd-empty {{ font-size: 0.78rem; color: var(--muted); padding: 2px 0; }}

  /* Mois */
  .month-grid {{
    display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px;
  }}
  .month-dow {{
    font-size: 0.7rem; text-transform: uppercase; color: var(--muted); text-align: center;
    padding-bottom: 4px; font-weight: 600;
  }}
  .month-cell {{
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    min-height: 64px; padding: 4px; font-size: 0.72rem;
  }}
  .month-cell.outside {{ opacity: 0.35; }}
  .month-cell.is-today {{ border-color: var(--navy); border-width: 2px; }}
  .month-cell .mc-num {{ font-weight: 600; margin-bottom: 2px; }}
  .mc-chip {{
    display: block; background: var(--bg); border-left: 2px solid var(--ok); border-radius: 3px;
    padding: 1px 4px; margin-bottom: 2px; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .mc-chip.status-provisoire {{ border-left-color: var(--prov); }}
  .mc-chip.status-annule {{ border-left-color: var(--cancel); opacity: 0.6; }}
  .mc-more {{ color: var(--muted); font-size: 0.68rem; }}

  footer {{
    max-width: 720px; margin: 20px auto 0; padding: 12px 16px 0; border-top: 1px solid var(--border);
    font-size: 0.75rem; color: var(--muted); text-align: center;
  }}

  @media (min-width: 560px) {{
    .week-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Horaire — {driver_name}</h1>
  <div class="sub">Loki Coach · Consultation seule · Mis à jour automatiquement plusieurs fois par jour</div>
</header>
<main>
  <div class="tabs">
    <button class="tab-btn active" data-view="agenda" type="button">Agenda</button>
    <button class="tab-btn" data-view="semaine" type="button">Semaine</button>
    <button class="tab-btn" data-view="mois" type="button">Mois</button>
  </div>

  <div id="view-agenda" class="view active">
{rows}
  </div>

  <div id="view-semaine" class="view">
    <div class="nav-bar">
      <div class="nav-group">
        <button class="nav-btn" id="week-prev" type="button">◀</button>
        <button class="nav-today" id="week-today" type="button">Aujourd'hui</button>
        <button class="nav-btn" id="week-next" type="button">▶</button>
      </div>
      <div class="nav-label" id="week-label"></div>
    </div>
    <div class="week-grid" id="week-grid"></div>
  </div>

  <div id="view-mois" class="view">
    <div class="nav-bar">
      <div class="nav-group">
        <button class="nav-btn" id="month-prev" type="button">◀</button>
        <button class="nav-today" id="month-today" type="button">Aujourd'hui</button>
        <button class="nav-btn" id="month-next" type="button">▶</button>
      </div>
      <div class="nav-label" id="month-label"></div>
    </div>
    <div class="month-grid" id="month-grid"></div>
  </div>
</main>
<footer>
  Généré automatiquement depuis Feuille de Route — dernière mise à jour : {generated_at}.<br>
  Pour toute modification, contacte Martin Goizioux ou Maxime Boulianne.
</footer>
<script>
(function() {{
  var DATA = {data_json};
  var TODAY_STR = {today_json};
  var JOURS = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"];
  var JOURS_COURT = ["lun","mar","mer","jeu","ven","sam","dim"];
  var MOIS = ["janvier","février","mars","avril","mai","juin","juillet",
              "août","septembre","octobre","novembre","décembre"];
  var STATUS_LABELS = {{"confirme":"Confirmé","provisoire":"Provisoire","annule":"Annulé"}};

  function pad(n) {{ return (n < 10 ? "0" : "") + n; }}
  function iso(d) {{ return d.getFullYear() + "-" + pad(d.getMonth()+1) + "-" + pad(d.getDate()); }}
  function parseISO(s) {{
    var p = s.split("-");
    return new Date(parseInt(p[0],10), parseInt(p[1],10)-1, parseInt(p[2],10));
  }}
  var TODAY = parseISO(TODAY_STR);

  function activeOn(a, dateStr) {{
    var end = a.endDate || a.startDate;
    return a.startDate <= dateStr && dateStr <= end;
  }}

  function eventLabel(a) {{
    var t = a.allDay ? "Toute la journée" : (a.startTime || "");
    return t;
  }}

  // ---------- Onglets ----------
  var tabBtns = document.querySelectorAll(".tab-btn");
  var views = document.querySelectorAll(".view");
  tabBtns.forEach(function(btn) {{
    btn.addEventListener("click", function() {{
      tabBtns.forEach(function(b) {{ b.classList.remove("active"); }});
      views.forEach(function(v) {{ v.classList.remove("active"); }});
      btn.classList.add("active");
      document.getElementById("view-" + btn.dataset.view).classList.add("active");
    }});
  }});

  // ---------- Vue Semaine ----------
  var weekOffset = 0;
  function mondayOf(d) {{
    var day = d.getDay(); // 0=dim..6=sam
    var diff = (day === 0 ? -6 : 1 - day);
    var m = new Date(d);
    m.setDate(d.getDate() + diff);
    return m;
  }}
  function renderWeek() {{
    var base = new Date(TODAY);
    base.setDate(base.getDate() + weekOffset * 7);
    var monday = mondayOf(base);
    var grid = document.getElementById("week-grid");
    grid.innerHTML = "";
    var days = [];
    for (var i = 0; i < 7; i++) {{
      var d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push(d);
    }}
    document.getElementById("week-label").textContent =
      days[0].getDate() + " " + MOIS[days[0].getMonth()] + " – " +
      days[6].getDate() + " " + MOIS[days[6].getMonth()] + " " + days[6].getFullYear();

    days.forEach(function(d) {{
      var dStr = iso(d);
      var isToday = dStr === TODAY_STR;
      var col = document.createElement("div");
      col.className = "week-day" + (isToday ? " is-today" : "");
      var head = document.createElement("div");
      head.className = "wd-head";
      head.textContent = JOURS_COURT[d.getDay() === 0 ? 6 : d.getDay() - 1] + " " + d.getDate();
      col.appendChild(head);
      var dayEvents = DATA.filter(function(a) {{ return activeOn(a, dStr); }});
      if (dayEvents.length === 0) {{
        var empty = document.createElement("div");
        empty.className = "wd-empty";
        empty.textContent = "—";
        col.appendChild(empty);
      }} else {{
        dayEvents.forEach(function(a) {{
          var ev = document.createElement("div");
          ev.className = "wd-event status-" + a.status;
          ev.textContent = eventLabel(a) + " — " + a.title;
          col.appendChild(ev);
        }});
      }}
      grid.appendChild(col);
    }});
  }}
  document.getElementById("week-prev").addEventListener("click", function() {{ weekOffset--; renderWeek(); }});
  document.getElementById("week-next").addEventListener("click", function() {{ weekOffset++; renderWeek(); }});
  document.getElementById("week-today").addEventListener("click", function() {{ weekOffset = 0; renderWeek(); }});

  // ---------- Vue Mois ----------
  var monthOffset = 0;
  function renderMonth() {{
    var base = new Date(TODAY.getFullYear(), TODAY.getMonth() + monthOffset, 1);
    var year = base.getFullYear(), month = base.getMonth();
    document.getElementById("month-label").textContent = MOIS[month] + " " + year;

    var grid = document.getElementById("month-grid");
    grid.innerHTML = "";
    JOURS_COURT.forEach(function(j) {{
      var dow = document.createElement("div");
      dow.className = "month-dow";
      dow.textContent = j;
      grid.appendChild(dow);
    }});

    var firstOfMonth = new Date(year, month, 1);
    var startOffset = (firstOfMonth.getDay() === 0 ? 6 : firstOfMonth.getDay() - 1);
    var gridStart = new Date(firstOfMonth);
    gridStart.setDate(1 - startOffset);

    for (var i = 0; i < 42; i++) {{
      var d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      if (i >= 35 && d.getMonth() !== month) break; // pas de 6e ligne inutile
      var dStr = iso(d);
      var cell = document.createElement("div");
      var cls = "month-cell";
      if (d.getMonth() !== month) cls += " outside";
      if (dStr === TODAY_STR) cls += " is-today";
      cell.className = cls;
      var num = document.createElement("div");
      num.className = "mc-num";
      num.textContent = d.getDate();
      cell.appendChild(num);
      var dayEvents = DATA.filter(function(a) {{ return activeOn(a, dStr); }});
      var shown = dayEvents.slice(0, 2);
      shown.forEach(function(a) {{
        var chip = document.createElement("span");
        chip.className = "mc-chip status-" + a.status;
        chip.textContent = a.title;
        chip.title = eventLabel(a) + " — " + a.title;
        cell.appendChild(chip);
      }});
      if (dayEvents.length > shown.length) {{
        var more = document.createElement("div");
        more.className = "mc-more";
        more.textContent = "+" + (dayEvents.length - shown.length);
        cell.appendChild(more);
      }}
      grid.appendChild(cell);
    }}
  }}
  document.getElementById("month-prev").addEventListener("click", function() {{ monthOffset--; renderMonth(); }});
  document.getElementById("month-next").addEventListener("click", function() {{ monthOffset++; renderMonth(); }});
  document.getElementById("month-today").addEventListener("click", function() {{ monthOffset = 0; renderMonth(); }});

  renderWeek();
  renderMonth();
}})();
</script>
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
