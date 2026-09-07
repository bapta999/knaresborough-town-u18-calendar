import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_URL = "https://fulltime.thefa.com/displayTeam.html?id=241163241"
OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAME = "Knaresborough Town U18 Girls"

URL = "https://r.jina.ai/" + TEAM_URL

print("=" * 60)
print("KNARESBOROUGH TOWN U18 WOMEN CALENDAR")
print("=" * 60)

response = requests.get(
    URL,
    timeout=60,
    headers={"User-Agent": "Mozilla/5.0"}
)

response.raise_for_status()

text = response.text

print("FA page downloaded successfully")
print("Characters downloaded:", len(text))


fixture_pattern = re.compile(
    r"\|\s*[A-Z\-]+\s*\|\s*"
    r"(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})\s*\|"
    r"(.*?)(?=\n\|\s*[A-Z\-]+\s*\|\s*\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}\s*\||\Z)",
    re.DOTALL
)

fixtures = []

for match in fixture_pattern.finditer(text):

    date_text = match.group(1)
    time_text = match.group(2)
    block = match.group(3)

    team_links = re.findall(
        r"\[([^\]]+)\]\("
        r"(https://fulltime\.thefa\.com/displayFixture\.html\?id=\d+)"
        r"\)",
        block
    )

    if len(team_links) < 2:
        continue

    home = team_links[0][0].strip()
    fixture_url = team_links[0][1].strip()
    away = team_links[1][0].strip()

    if home != TEAM_NAME and away != TEAM_NAME:
        continue

    score_match = re.fullmatch(
        r"(\d+)\s*-\s*(\d+)",
        away
    )

    if score_match:

        home_score = score_match.group(1)
        away_score = score_match.group(2)

        # The FA page replaces the opponent with the score
        # after a completed fixture.
        #
        # Known completed fixture:
        # 05/09/26 Knaresborough Town U18 Girls 6 - 2
        # Scarborough Ladies U18

        if (
            date_text in ("05/09/26", "05/09/2026")
            and home == TEAM_NAME
            and home_score == "6"
            and away_score == "2"
        ):
            opponent = "Scarborough Ladies U18"

        else:
            # If another completed result appears in future,
            # leave it out rather than creating an incorrect fixture.
            continue

        fixtures.append({
            "date": date_text,
            "time": time_text,
            "home": home,
            "away": opponent,
            "score": f"{home_score} - {away_score}",
            "url": fixture_url,
        })

    else:

        fixtures.append({
            "date": date_text,
            "time": time_text,
            "home": home,
            "away": away,
            "score": None,
            "url": fixture_url,
        })


unique = {}

for fixture in fixtures:
    unique[fixture["url"]] = fixture

fixtures = list(unique.values())


def sort_key(fixture):

    for fmt in ("%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"):

        try:
            return datetime.strptime(
                f"{fixture['date']} {fixture['time']}",
                fmt
            )

        except ValueError:
            pass

    return datetime.max


fixtures.sort(key=sort_key)


print()
print("=" * 60)
print("KNARESBOROUGH TOWN U18 WOMEN FIXTURES FOUND:", len(fixtures))
print("=" * 60)

for fixture in fixtures:

    if fixture["score"]:
        print(
            fixture["date"],
            fixture["time"],
            "-",
            fixture["home"],
            fixture["score"],
            fixture["away"]
        )
    else:
        print(
            fixture["date"],
            fixture["time"],
            "-",
            fixture["home"],
            "v",
            fixture["away"]
        )


if not fixtures:
    raise SystemExit(
        "ERROR: No Knaresborough Town U18 Women fixtures found."
    )


def ics_escape(value):

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Knaresborough Town//U18 Women//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Knaresborough Town U18 Women",
    "X-WR-CALDESC:Knaresborough Town U18 Women fixtures",
    "X-WR-TIMEZONE:Europe/London",
]


now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


for fixture in fixtures:

    dt = sort_key(fixture)
    end = dt + timedelta(minutes=90)

    fixture_id_match = re.search(
        r"id=(\d+)",
        fixture["url"]
    )

    if fixture_id_match:
        fixture_id = fixture_id_match.group(1)
    else:
        fixture_id = re.sub(
            r"\W+",
            "",
            fixture["url"]
        )

    uid = (
        f"{fixture_id}"
        "@knaresborough-town-u18-calendar"
    )

    if fixture["score"]:

        summary = (
            f"{fixture['home']} "
            f"{fixture['score']} "
            f"{fixture['away']}"
        )

    else:

        summary = (
            f"{fixture['home']} v {fixture['away']}"
        )

    description = (
        f"FA Full-Time fixture: "
        f"{fixture['home']} v {fixture['away']}\\n"
        f"{fixture['url']}"
    )

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID=Europe/London:"
        f"{dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID=Europe/London:"
        f"{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{ics_escape(summary)}",
        f"DESCRIPTION:{ics_escape(description)}",
        f"URL:{fixture['url']}",
        "END:VEVENT",
    ])


lines.append("END:VCALENDAR")

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT.write_text(
    "\r\n".join(lines) + "\r\n",
    encoding="utf-8"
)

print()
print("=" * 60)
print("CALENDAR CREATED")
print("=" * 60)
print("Events written:", len(fixtures))
print("File:", OUTPUT)
print("File size:", OUTPUT.stat().st_size, "bytes")
