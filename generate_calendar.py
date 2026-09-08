import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_FILTERED_URL = "https://fulltime.thefa.com/fixtures.html?selectedSeason=158072627&selectedFixtureGroupAgeGroup=0&selectedFixtureGroupKey=&selectedDateCode=all&selectedClub=&selectedTeam=241163241&selectedRelatedFixtureOption=3&selectedFixtureDateStatus=&selectedFixtureStatus=&previousSelectedFixtureGroupAgeGroup=&previousSelectedFixtureGroupKey=&previousSelectedClub=&itemsPerPage=25"

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAME = "Knaresborough Town U18 Girls"

URL = "https://r.jina.ai/" + TEAM_FILTERED_URL

print("=" * 60)
print("KNARESBOROUGH TOWN U18 WOMEN CALENDAR")
print("=" * 60)

response = requests.get(
    URL,
    timeout=60,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

response.raise_for_status()

text = response.text

print("FA page downloaded successfully")
print("Characters downloaded:", len(text))


def clean_cell(value):
    value = value.strip()

    # Remove complete Markdown image placeholders
    value = re.sub(
        r'!\[[^\]]*\]\([^)]+\)',
        '',
        value
    )

    # Remove things such as [Image 51](...)
    value = re.sub(
        r'\[\s*Image(?:\s+\d+)?\s*\]\([^)]+\)',
        '',
        value,
        flags=re.IGNORECASE
    )

    # Remove things such as [Image 51]
    value = re.sub(
        r'\[\s*Image(?:\s+\d+)?\s*\]',
        '',
        value,
        flags=re.IGNORECASE
    )

    # Remove image placeholders such as Image: something
    value = re.sub(
        r'Image\s*:\s*[^|]+',
        '',
        value,
        flags=re.IGNORECASE
    )

    # Remove any remaining plain Image 51 text
    value = re.sub(
        r'Image(?:\s+\d+)?',
        '',
        value,
        flags=re.IGNORECASE
    )

    # Convert normal Markdown links to their visible text
    value = re.sub(
        r'\[([^\]]+)\]\([^)]+\)',
        r'\1',
        value
    )

    # Remove HTML
    value = re.sub(r'<[^>]+>', '', value)

    # Remove empty brackets left behind
    value = re.sub(r'\[\s*\]', '', value)

    # Tidy whitespace
    value = re.sub(r'\s+', ' ', value)

    return value.strip()


def parse_rows(text):
    fixtures = []

    date_re = re.compile(
        r'\b\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}\b'
    )

    fixture_url_re = re.compile(
        r'https://fulltime\.thefa\.com/displayFixture\.html\?id=\d+'
    )

    for line in text.splitlines():

        if not date_re.search(line):
            continue

        if "|" not in line:
            continue

        raw_cells = line.split("|")
        cells = [clean_cell(cell) for cell in raw_cells]

        # Remove completely empty cells
        cells = [cell for cell in cells if cell]

        if "VS" not in cells:
            continue

        vs_index = cells.index("VS")

        date_index = None

        for i, cell in enumerate(cells):
            if date_re.search(cell):
                date_index = i
                break

        if date_index is None:
            continue

        before = cells[date_index + 1:vs_index]
        after = cells[vs_index + 1:]

        # Remove fixture type such as L or CC
        before = [
            x for x in before
            if x not in ("L", "CC")
        ]

        if not before or not after:
            continue

        home = before[0].strip()

        score_pattern = re.compile(
            r'^\d+\s*-\s*\d+(?:\s*\(.*\))?$'
        )

        score = None
        away = None

        for cell in after:

            if score_pattern.fullmatch(cell):
                score = cell
                continue

            if cell in ("L", "CC", "Cancelled"):
                continue

            if not cell:
                continue

            away = cell
            break

        if not home or not away:
            continue

        # Only include fixtures involving the Knaresborough team
        if home != TEAM_NAME and away != TEAM_NAME:
            continue

        # Find the fixture URL in the original line
        url_match = fixture_url_re.search(line)

        fixture_url = (
            url_match.group(0)
            if url_match
            else ""
        )

        date_match = date_re.search(line)

        if not date_match:
            continue

        date_time = date_match.group(0)

        fixtures.append({
            "date_time": date_time,
            "home": home,
            "away": away,
            "score": score,
            "url": fixture_url
        })

    return fixtures


fixtures = parse_rows(text)

# Remove duplicates
unique = {}

for fixture in fixtures:
    key = (
        fixture["date_time"],
        fixture["home"],
        fixture["away"]
    )
    unique[key] = fixture

fixtures = list(unique.values())


def sort_key(fixture):
    for fmt in (
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M"
    ):
        try:
            return datetime.strptime(
                fixture["date_time"],
                fmt
            )
        except ValueError:
            pass

    return datetime.max


fixtures.sort(key=sort_key)


print()
print("=" * 60)
print("FIXTURES FOUND:", len(fixtures))
print("=" * 60)

for fixture in fixtures:
    print(
        fixture["date_time"],
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
        r'id=(\d+)',
        fixture["url"]
    )

    if fixture_id_match:
        fixture_id = fixture_id_match.group(1)
    else:
        fixture_id = re.sub(
            r'\W+',
            '',
            fixture["date_time"] + fixture["home"] + fixture["away"]
        )

    uid = (
        f"{fixture_id}"
        f"@knaresborough-town-u18-calendar"
    )

    summary = (
        f"{fixture['home']} v {fixture['away']}"
    )

    if fixture["score"]:
        summary += f" ({fixture['score']})"

    description = (
        f"FA Full-Time fixture: "
        f"{fixture['home']} v {fixture['away']}"
    )

    if fixture["score"]:
        description += (
            f"\\nResult: {fixture['score']}"
        )

    if fixture["url"]:
        description += (
            f"\\n{fixture['url']}"
        )

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID=Europe/London:{dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID=Europe/London:{end.strftime('%Y%m%dT%H%M%S')}",
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
