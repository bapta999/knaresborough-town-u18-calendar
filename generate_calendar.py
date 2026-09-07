import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_NAME = "Knaresborough Town U18 Women"

TEAM_URL = (
    "https://fulltime.thefa.com/fixtures.html?"
    "selectedSeason=158072627&"
    "selectedFixtureGroupAgeGroup=0&"
    "selectedFixtureGroupKey=&"
    "selectedDateCode=all&"
    "selectedClub=&"
    "selectedTeam=241163241&"
    "selectedRelatedFixtureOption=3&"
    "selectedFixtureDateStatus=&"
    "selectedFixtureStatus=&"
    "previousSelectedFixtureGroupAgeGroup=&"
    "previousSelectedFixtureGroupKey=&"
    "previousSelectedClub=&"
    "itemsPerPage=100"
)

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

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


# Find fixture blocks from the FA Full-Time page.
fixture_pattern = re.compile(
    r"\|\s*[A-Z]\s*\|\s*"
    r"(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})\s*\|"
    r"(.*?)(?=\|\s*[A-Z]\s*\|\s*\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}\s*\||\Z)",
    re.DOTALL
)

fixtures = []

for match in fixture_pattern.finditer(text):

    date_text = match.group(1)
    time_text = match.group(2)
    block = match.group(3)

    # Find the two teams and the fixture link.
    team_links = re.findall(
        r"\[([^\]]+)\]\(\s*"
        r"(https://fulltime\.thefa\.com/displayFixture\.html\?id=\d+)"
        r"\s*\)",
        block
    )

    if len(team_links) < 2:
        continue

    home = team_links[0][0].strip()
    fixture_url = team_links[0][1].strip()
    away = team_links[1][0].strip()

    # Only include fixtures where Knaresborough are actually playing.
    if home != TEAM_NAME and away != TEAM_NAME:
        continue

    fixtures.append({
        "date": date_text,
        "time": time_text,
        "home": home,
        "away": away,
        "url": fixture_url,
    })


# Remove duplicates.
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

    print(
        fixture["date"],
        fixture["time"],
        "-",
        fixture["home"],
        "v",
        fixture["away"]
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
