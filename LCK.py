import os
import re  
import json
import urllib.request
from datetime import datetime, timedelta

def fetch_lck_events():
    url = "https://lolesports.com/en-US/leagues/lck"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=15) as response:
        html = response.read().decode("utf-8")

    all_events = []
    seen_ids = set()
    for pos in [m.start() for m in re.finditer(r'"events":\[', html)]:
        start = pos + len('"events":')
        depth = 0
        for i in range(start, len(html)):
            if html[i] == "[": depth += 1
            elif html[i] == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            ev_list = json.loads(html[start:end])
            for ev in ev_list:
                if isinstance(ev, dict) and ev.get("id") and ev.get("id") not in seen_ids:
                    seen_ids.add(ev["id"])
                    all_events.append(ev)
        except Exception:
            pass
    all_events.sort(key=lambda x: x.get("startTime", ""))
    return all_events


def format_event_to_ics(ev, has_alarm=False):
    start_dt = datetime.fromisoformat(ev["startTime"].replace("Z", "+00:00"))
    bo_count = ev.get("match", {}).get("strategy", {}).get("count", 3)

    duration_hours = 4 if bo_count == 5 else 2.5
    end_dt = start_dt + timedelta(hours=duration_hours)

    dtstart = start_dt.strftime("%Y%m%dT%H%M%SZ")
    dtend = end_dt.strftime("%Y%m%dT%H%M%SZ")

    teams = ev.get("matchTeams", [])
    if len(teams) >= 2:
        t1 = teams[0].get("code", "TBD")
        t2 = teams[1].get("code", "TBD")
        w1 = teams[0].get("result", {}).get("gameWins", 0) if teams[0].get("result") else 0
        w2 = teams[1].get("result", {}).get("gameWins", 0) if teams[1].get("result") else 0
    else:
        t1, t2, w1, w2 = "TBD", "TBD", 0, 0

    title = f"{t1} vs {t2}"
    if ev.get("state") == "completed":
        title += f" - {w1} : {w2}"

    description = f"LCK {ev.get('tournament', {}).get('name', '')} {ev.get('blockName', '')}"
    uid = f"lck-{ev.get('id')}@lolesports.com"

    alarm_str = ""
    if has_alarm and ev.get("state") == "unstarted":
        alarm_str = (
            "BEGIN:VALARM\n"
            "ACTION:AUDIO\n"
            "TRIGGER:-PT30M\n"
            "ATTACH;VALUE=URI:Glass\n"
            "END:VALARM\n"
        )

    return (
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"SUMMARY:{title}\n"
        f"DTSTART:{dtstart}\n"
        f"DTEND:{dtend}\n"
        f"DESCRIPTION:{description}\n"
        "URL:https://lolesports.com/en-US/leagues/lck\n"
        "STATUS:CONFIRMED\n"
        f"{alarm_str}"
        "END:VEVENT\n"
    )


def export_all_ics(events, base_dir):
    lck_dir = os.path.join(base_dir, "2026_lck")
    team_dir = os.path.join(lck_dir, "team")
    os.makedirs(team_dir, exist_ok=True)
    
    team_events_map = {}
    for ev in events:
        for t in ev.get("matchTeams", []):
            code = t.get("code")
            if code and code != "TBD":
                team_events_map.setdefault(code, []).append(ev)
                
    def save_ics(filepath, event_list, cal_name, has_alarm):
        content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:lolesports-scraper",
            f"X-WR-CALNAME:{cal_name}",
            "X-PUBLISHED-TTL:PT1H"
        ]
        for ev in event_list:
            content.append(format_event_to_ics(ev, has_alarm))
        content.append("END:VCALENDAR\n")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    save_ics(os.path.join(lck_dir, "2026_lck.ics"), events, "LCK 2026 schedule", False)
    save_ics(os.path.join(lck_dir, "2026_lck-alarm.ics"), events, "LCK 2026 schedule(w/ alarm)", True)
    
    for team_code, t_events in team_events_map.items():
        save_ics(os.path.join(team_dir, f"{team_code}.ics"), t_events, f"LCK {team_code} schedule", False)
        save_ics(os.path.join(team_dir, f"{team_code}-alarm.ics"), t_events, f"LCK {team_code} schedule(w/ alarm)", True)


if __name__ == "__main__":
    target_folder = os.path.expanduser("~/Downloads")
    events = fetch_lck_events()
    print(f"Successfully fetched {len(events)} games, creating ics files...")
    export_all_ics(events, base_dir=target_folder)
    print(f"Done! ics files created in: {os.path.join(target_folder, '2026_lck')}")