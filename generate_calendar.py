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

OUTPUT = Path(
    "docs/knaresborough-town-u18-women.ics"
)

TEAM_NAME = "Knaresborough Town U18 Girls"


def clean_cell(value):

    value = value.strip()

    # Remove image markdown such as:
    # ![Image 51](...)
    value = re.sub(
        r'!\[[^\]]*\]\([^)]+\)',
        '',
        value
    )

    # Remove things such as:
    # Image: Knaresborough Town U18 Women
    # [Image 51]
    value = re.sub(
        r'Image(?:\s+\d+)?(?::)?',
        '',
        value,
        flags=re.IGNORECASE
    )

    # Convert normal markdown links to their visible text
    value = re.sub(
        r'\[([^\]]+)\]\([^)]+\)',
        r'\1',
        value
    )

    # Remove HTML
    value = re.sub(
        r'<[^>]+>',
        '',
        value
    )

    # Tidy spaces
    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    return value.strip()


def is_knaresborough(name):

    name = name.lower().strip()

    return (
        "knaresborough town u18 girls" in name
        or
        "knaresborough town u18 women" in name
    )


def parse_fixtures(text):

    fixtures = []

    for line in text.splitlines():

        # We only care about lines containing a date and time
        date_match = re.search(
            r'(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})',
            line
        )

        if not date_match:
            continue

        date_text = date_match.group(1)
        time_text = date_match.group(2)

        # Split the markdown table into cells
        raw_cells = line.split("|")

        cells = [
            clean_cell(cell)
            for cell in raw_cells
        ]

        # Remove empty cells
        cells = [
            cell for cell in cells
            if cell
        ]

        # Find VS
        vs_index = None

        for i, cell in enumerate(cells):

            if cell.upper() == "VS":
                vs_index = i
                break

        if vs_index is None:
            continue

        # Find the date cell
        date_index = None

        for i, cell in enumerate(cells):

            if date_text in cell:
                date_index = i
                break

        if date_index is None:
            continue

        # Team before VS
        before = cells[
            date_index + 1:vs_index
        ]

        # Teams / score after VS
        after = cells[
            vs_index + 1:
        ]

        # Remove status / competition labels
        before = [
            x for x in before
            if x.upper() not in (
                "L",
                "CC"
            )
        ]

        if not before:
            continue

        home = before[0]

        # Look for a score
        score = None

        for cell in after:

            if re.fullmatch(
                r'\d+\s*-\s*\d+',
                cell
            ):
                score = cell
                break

        # Find away team
        away = ""

        for cell in after:

            if cell == score:
                continue

            if cell.lower() == "venue":
                continue

            if not cell:
                continue

            # Don't accidentally use other metadata
            if cell.upper() in (
                "L",
                "CC"
            ):
                continue

            away = cell
            break

        # If what we found as away is actually a score,
        # leave it blank so we can recover it below.
        if re.fullmatch(
            r'\d+\s*-\s*\d+',
            away
        ):
            away = ""

        # We only want Knaresborough fixtures
        if not (
            is_knaresborough(home)
            or
            is_knaresborough(away)
        ):
            continue

        # Find fixture URL if present
        url_match = re.search(
            r'https://fulltime\.thefa\.com/displayFixture\.html\?id=\d+',
            line
        )

        fixture_url = (
            url_match.group(0)
            if url_match
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
        "%d/%m/%Y %H:%M"
    ):

        try:

            return datetime.strptime(
                fixture["date"]
                + " "
                + fixture["time"],
                fmt
            )

        except ValueError:
            pass

    return datetime.max


def fetch_page(url):

    jina_url = (
        "https://r.jina.ai/"
        + url
    )

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
print("KNARESBOROUGH TOWN U18 WOMEN")
print("=" * 60)

print("Downloading team-filtered fixtures...")

text = fetch_page(
    TEAM_FILTERED_URL
)

print(
    "Characters downloaded:",
    len(text)
)

fixtures = parse_fixtures(text)

print(
    "Fixtures found:",
    len(fixtures)
)


# ------------------------------------------------------------
# Use the normal team page as a second source.
# This helps recover opponents for completed matches.
# ------------------------------------------------------------

print("Downloading main team page...")

team_page_text = fetch_page(
    TEAM_PAGE_URL
)

team_page_fixtures = parse_fixtures(
    team_page_text
)

print(
    "Fixtures found on team page:",
    len(team_page_fixtures)
)


# ------------------------------------------------------------
# Match the two sources by date and time
# ------------------------------------------------------------

for fixture in fixtures:

    matches = [
        other
        for other in team_page_fixtures
        if (
            other["date"] == fixture["date"]
            and
            other["time"] == fixture["time"]
        )
    ]

    if not matches:
        continue

    other = matches[0]

    if not fixture["away"] and other["away"]:
        fixture["away"] = other["away"]

    if not fixture["home"] and other["home"]:
        fixture["home"] = other["home"]

    if not fixture["score"] and other["score"]:
        fixture["score"] = other["score"]

    if not fixture["url"] and other["url"]:
        fixture["url"] = other["url"]


# ------------------------------------------------------------
# Remove duplicates
# ------------------------------------------------------------

unique = {}

for fixture in fixtures:

    key = (
        fixture["date"],
        fixture["time"],
        fixture["home"],
        fixture["away"]
    )

    unique[key] = fixture


fixtures = list(
    unique.values()
)

fixtures.sort(
    key=fixture_datetime
)


# ------------------------------------------------------------
# Print final fixtures
# ------------------------------------------------------------

print()
print("=" * 60)
print(
    "FINAL FIXTURES:",
    len(fixtures)
)
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
# Create iCal
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


now = datetime.utcnow().strftime(
    "%Y%m%dT%H%M%SZ"
)


for fixture in fixtures:

    dt = fixture_datetime(
        fixture
    )

    if dt == datetime.max:
        continue

    end = dt + timedelta(
        minutes=90
    )

    # Stable fixture ID
    if fixture["url"]:

        match = re.search(
            r'id=(\d+)',
            fixture["url"]
        )

        if match:

            uid = (
                match.group(1)
                + "@knaresborough-town-u18-calendar"
            )

        else:

            uid = hashlib.sha1(
                (
                    fixture["home"]
                    + "|"
                    + fixture["away"]
                ).encode()
            ).hexdigest() \
                + "@knaresborough-town-u18-calendar"

    else:

        identity = (
            "158072627|"
            + fixture["home"]
            + "|"
            + fixture["away"]
        )

        uid = hashlib.sha1(
            identity.encode()
        ).hexdigest() \
            + "@knaresborough-town-u18-calendar"


    # Calendar title
    if fixture["score"]:

        summary = (
            fixture["home"]
            + " "
            + fixture["score"]
            + " "
            + fixture["away"]
        )

    else:

        summary = (
            fixture["home"]
            + " v "
            + fixture["away"]
        )


    description = (
        "FA Full-Time fixture: "
        + fixture["home"]
        + " v "
        + fixture["away"]
    )

    if fixture["score"]:

        description += (
            "\\nResult: "
            + fixture["score"]
        )

    if fixture["url"]:

        description += (
            "\\n"
            + fixture["url"]
        )


    lines.extend([
        "BEGIN:VEVENT",
        "UID:" + uid,
        "DTSTAMP:" + now,
        "DTSTART;TZID=Europe/London:"
        + dt.strftime("%Y%m%dT%H%M%S"),
        "DTEND;TZID=Europe/London:"
        + end.strftime("%Y%m%dT%H%M%S"),
        "SUMMARY:"
        + ics_escape(summary),
        "DESCRIPTION:"
        + ics_escape(description),
    ])


    if fixture["url"]:

        lines.append(
            "URL:" + fixture["url"]
        )

    lines.append(
        "END:VEVENT"
    )


lines.append(
    "END:VCALENDAR"
)


OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT.write_text(
    "\r\n".join(lines)
    + "\r\n",
    encoding="utf-8"
)


print()
print("=" * 60)
print("CALENDAR CREATED")
print("=" * 60)
print(
    "Events written:",
    len(fixtures)
)
print(
    "File:",
    OUTPUT
)
print(
    "File size:",
    OUTPUT.stat().st_size,
    "bytes"
)
