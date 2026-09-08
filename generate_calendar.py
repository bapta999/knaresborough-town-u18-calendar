import re
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_FILTERED_URL = (
    "https://fulltime.thefa.com/fixtures.html"
    "?selectedSeason=158072627"
    "&selectedFixtureGroupAgeGroup=0"
    "&selectedFixtureGroupKey="
    "&selectedDateCode=all"
    "&selectedClub="
    "&selectedTeam=241163241"
    "&selectedRelatedFixtureOption=3"
    "&selectedFixtureDateStatus="
    "&selectedFixtureStatus="
    "&previousSelectedFixtureGroupAgeGroup="
    "&previousSelectedFixtureGroupKey="
    "&previousSelectedClub="
    "&itemsPerPage=25"
)

TEAM_PAGE_URL = (
    "https://fulltime.thefa.com/displayTeam.html?id=241163241"
)

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAMES = {
    "knaresborough town u18 girls",
    "knaresborough town u18 women",
}

DATE_RE = re.compile(
    r"(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})"
)

FIXTURE_URL_RE = re.compile(
    r"https://fulltime\.thefa\.com/displayFixture\.html\?id=\d+"
)


def clean_cell(value):
    value = value.strip()

    # Remove image markdown completely
    value = re.sub(
        r'!\[[^\]]*\]\([^)]+\)',
        '',
        value
    )

    # Remove plain "Image ..." references
    value = re.sub(
        r'\[?Image(?:\s+\d+)?\]?',
        '',
        value,
        flags=re.IGNORECASE
    )

    # Remove Markdown links but keep their visible text
    value = re.sub(
        r'\[([^\]]+)\]\([^)]+\)',
        r'\1',
        value
    )

    # Remove HTML
    value = re.sub(r'<[^>]+>', '', value)

    # Clean up whitespace
    value = re.sub(r'\s+', ' ', value)

    return value.strip()


def is_team_name(value):
    value = value.strip().lower()

    if not value:
        return False

    if value in TEAM_NAMES:
        return True

    return (
        "u18" in value
        and (
            "girls" in value
            or "women" in value
        )
    )


def parse_rows(text):
    fixtures = []

    for line in text.splitlines():

        if not DATE_RE.search(line):
            continue

        cells = [
            clean_cell(cell)
            for cell in line.split("|")
        ]

        cells = [
            cell for cell in cells
            if cell != ""
        ]

        date_match = DATE_RE.search(line)

        if not date_match:
            continue

        date_text = date_match.group(1)
        time_text = date_match.group(2)

        # Find VS
        vs_index = None

        for i, cell in enumerate(cells):
            if cell.upper() == "VS":
                vs_index = i
                break

        if vs_index is None:
            continue

        # Everything before VS after the date
        date_index = None

        for i, cell in enumerate(cells):
            if date_text in cell:
                date_index = i
                break

        if date_index is None:
            continue

        before = cells[date_index + 1:vs_index]
        after = cells[vs_index + 1:]

        # Ignore obvious status / competition text
        before = [
            x for x in before
            if x.upper() not in ("L", "CC")
        ]

        # First real team before VS
        home = before[0] if before else ""

        # Find score if present
        score = None

        for cell in after:
            if re.fullmatch(
                r"\d+\s*-\s*\d+(?:\s*\(.*\))?",
                cell
            ):
                score = cell
                break

        # First non-score cell after VS is normally the away team
        away = ""

        for cell in after:
            if cell == score:
                continue

            if cell.lower() == "venue":
                continue

            if cell:
                away = cell
                break

        # If the score has replaced the away team,
        # away will currently be blank.
        if away and re.fullmatch(r"\d+\s*-\s*\d+.*", away):
            away = ""

        if not home:
            continue

        # We only want Knaresborough fixtures
        if not (
            is_team_name(home)
            or is_team_name(away)
        ):
            continue

        fixture_url_match = FIXTURE_URL_RE.search(line)

        fixture_url = (
            fixture_url_match.group(0)
            if fixture_url_match
            else ""
        )

        fixtures.append({
            "date": date_text,
            "time": time_text,
            "home": home,
            "away": away,
            "score": score,
            "url": fixture_url,
        })

    return fixtures


def fixture_datetime(fixture):
    for fmt in (
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(
                f"{fixture['date']} {fixture['time']}",
                fmt
            )
        except ValueError:
            pass

    return datetime.max


def fetch_page(url):
    jina_url = "https://r.jina.ai/" + url

    response = requests.get(
        jina_url,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    return response.text


print("=" * 60)
print("KNARESBOROUGH TOWN U18 WOMEN CALENDAR")
print("=" * 60)

# ------------------------------------------------------------
# 1. Get the team-filtered fixture list
# ------------------------------------------------------------

text = fetch_page(TEAM_FILTERED_URL)

print("Team-filtered page downloaded")
print("Characters downloaded:", len(text))

fixtures = parse_rows(text)

print("Fixtures found on team-filtered page:", len(fixtures))

# ------------------------------------------------------------
# 2. Get the normal team page as a second source.
#    This is particularly useful for completed results where
#    Full-Time replaces the opposition with the score.
# ------------------------------------------------------------

team_page_text = fetch_page(TEAM_PAGE_URL)

team_page_fixtures = parse_rows(team_page_text)

print(
    "Fixtures found on team page:",
    len(team_page_fixtures)
)

# ------------------------------------------------------------
# 3. Fill in missing opponents / scores from the team page
# ------------------------------------------------------------

for fixture in fixtures:

    matching = [
        other
        for other in team_page_fixtures
        if (
            other["date"] == fixture["date"]
            and other["time"] == fixture["time"]
        )
    ]

    if not matching:
        continue

    other = matching[0]

    # If one source has the opponent and the other doesn't,
    # use the source that has it.
    if not fixture["away"] and other["away"]:
        fixture["away"] = other["away"]

    if not fixture["home"] and other["home"]:
        fixture["home"] = other["home"]

    if not fixture["score"] and other["score"]:
        fixture["score"] = other["score"]

    if not fixture["url"] and other["url"]:
        fixture["url"] = other["url"]


# ------------------------------------------------------------
# 4. Remove duplicates
# ------------------------------------------------------------

unique = {}

for fixture in fixtures:

    key = (
        fixture["date"],
        fixture["time"],
        fixture["home"],
        fixture["away"],
    )

    unique[key] = fixture

fixtures = list(unique.values())

fixtures.sort(key=fixture_datetime)


# ------------------------------------------------------------
# 5. Print everything found
# ------------------------------------------------------------

print()
print("=" * 60)
print("FINAL FIXTURES:", len(fixtures))
print("=" * 60)

for fixture in fixtures:

    print(
        fixture["date"],
        fixture["time"],
        "-",
        fixture["home"],
        "v",
        fixture["away"],
        "|",
        fixture["score"] or "No score"
    )


# ------------------------------------------------------------
# 6. Create iCal
# ------------------------------------------------------------

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

    dt = fixture_datetime(fixture)

    if dt == datetime.max:
        continue

    end = dt + timedelta(minutes=90)

    # Prefer the FA fixture ID for a stable UID.
    # Otherwise create a stable UID from the teams.
    fixture_id_match = re.search(
        r"id=(\d+)",
        fixture["url"]
    )

    if fixture_id_match:
        uid = (
            fixture_id_match.group(1)
            + "@knaresborough-town-u18-calendar"
        )
    else:
        identity = (
            "158072627|"
            + fixture["home"]
            + "|"
            + fixture["away"]
        )

        uid_hash = hashlib.sha1(
            identity.encode("utf-8")
        ).hexdigest()

        uid = (
            uid_hash
            + "@knaresborough-town-u18-calendar"
        )

    if fixture["score"]:
        summary = (
            f"{fixture['home']} "
            f"{fixture['score']} "
            f"{fixture['away']}"
        )
    else:
        summary = (
            f"{fixture['home']} v "
            f"{fixture['away']}"
        )

    description = (
        "FA Full-Time fixture: "
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
    ])

    if fixture["url"]:
        lines.append(
            f"URL:{fixture['url']}"
        )

    lines.append("END:VEVENT")


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
print(
    "File size:",
    OUTPUT.stat().st_size,
    "bytes"
)
