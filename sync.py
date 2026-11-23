import os
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

USER = os.environ["AURION_USER"]
PASS = os.environ["AURION_PASS"]

def format_ics_date(ms):
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://web.isen-ouest.fr/webAurion/")

    # Connexion
    page.fill("input[name='username'], input[type='text']", USER)
    page.fill("input[name='password'], input[type='password']", PASS)
    page.click("button[type='submit'], input[type='submit']")
    page.wait_for_load_state("networkidle")

    # Navigation vers le planning
    page.get_by_text("Mon planning", exact=False).first.click()
    page.wait_for_selector(".fc-view")
    page.wait_for_timeout(2000)

    # Récupère les événements sur 12 semaines en cliquant sur "Suivant"
    all_events = {}
    for _ in range(12):
        events = page.evaluate("""() => {
            let res = [];
            if (window.jQuery) {
                jQuery('.fc').each(function() {
                    let ev = jQuery(this).fullCalendar('clientEvents');
                    if (ev && ev.length) res = ev;
                });
            }
            return res.map(e => ({
                id: e.id || (e.title + e.start),
                title: e.title || 'Cours ISEN',
                start: e.start ? e.start.valueOf() : null,
                end: e.end ? e.end.valueOf() : null
            }));
        }""")
        for ev in events:
            if ev["start"]:
                all_events[str(ev["id"])] = ev
        page.click(".fc-next-button")
        page.wait_for_timeout(1500)

    browser.close()

# Génération du fichier .ics
lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//WebAurion ISEN Sync//FR",
    "CALSCALE:GREGORIAN"
]

now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

for idx, ev in enumerate(all_events.values()):
    start = ev["start"]
    end = ev["end"] or (start + 3600000)
    title = ev["title"].replace("\n", " - ")
    lines.extend([
        "BEGIN:VEVENT",
        f"UID:aurion-{idx}-{start}@isen-ouest.fr",
        f"DTSTAMP:{now_str}",
        f"DTSTART:{format_ics_date(start)}",
        f"DTEND:{format_ics_date(end)}",
        f"SUMMARY:{title}",
        "END:VEVENT"
    ])

lines.append("END:VCALENDAR")

with open("planning.ics", "w", encoding="utf-8") as f:
    f.write("\r\n".join(lines))
