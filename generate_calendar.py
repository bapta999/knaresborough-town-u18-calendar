import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_URL = "https://fulltime.thefa.com/displayTeam.html?id=241163241"

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAMES = [
    "Knaresborough Town U18 Women",
    "Knaresborough Town U18 Girls"
]

URL = "https://r.jina.ai/" + TEAM_URL

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


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def clean_name(value):
    value = value.strip()

    # Extract text from image alt-text
    image_match = re.search(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        value,
        flags=re.IGNORECASE
    )

    if image_match:
        return image_match.group(1).strip()

    # Remove normal markdown links
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

    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    return value.strip()


def find_fixture_url(line):
    # Standard fixtures
    match = re.search(
        r'https://fulltime\.thefa\.com/'
        r'displayFixture\.html\?id=\d+',
        line
    )

    if match:
        return match.group(0)

    # County cup fixtures
    match = re.search(
        r'https://fulltime\.thefa\.com/'
        r'displayCountyFixture\.html\?id=\d+(?:&[^)\s<]+)?',
        line
    )

    if match:
        return match.group(0)

    return ""


def parse_date_time(line):
    match = re.search(
        r'(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})',
        line
    )

    if not match:
        return None, None

    return match.group(1), match.group(2)


# ------------------------------------------------------------
# FIND FIXTURES
# ------------------------------------------------------------

fixtures = []

for line in text.splitlines():

    date_text, time_text = parse_date_time(line)

    if not date_text:
        continue

    # We now accept both:
    #
    #   VS
    #
    # and
    #
    #   v
    #
    if "VS" not in line and " v " not in line:
        continue

    # --------------------------------------------------------
    # First try the image alt-text.
    #
    # Example:
    #
    # ![Image 47: Knaresborough Town U18 Women]
    #
    # --------------------------------------------------------

    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    if len(image_names) >= 2:

        home = image_names[0].strip()
        away = image_names[1].strip()

    else:

        # ----------------------------------------------------
        # Fall back to the visible text around "v" or "VS"
        # ----------------------------------------------------

        if " VS " in line:
            parts = re.split(
                r'\s+VS\s+',
                line,
                maxsplit=1
            )
        else:
            parts = re.split(
                r'\s+v\s+',
                line,
                maxsplit=1
            )

        if len(parts) != 2:
            continue

        home_part = parts[0]
        away_part = parts[1]

        # Remove everything before the date/time
        date_time_text = f"{date_text} {time_text}"

        if date_time_text in home_part:
            home_part = home_part.split(
                date_time_text,
                1
            )[1]

        home = clean_name(home_part)
        away = clean_name(away_part)

        if not home or not away:
            continue

    # --------------------------------------------------------
    # Ignore rows that aren't Knaresborough fixtures
    # --------------------------------------------------------

    if not any(
        team in home or team in away
        for team in TEAM_NAMES
    ):
        continue

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    score_match = re.search(
        r'\b(\d+\s*-\s*\d+)\b',
        line
    )

    score = None

    if score_match:
        score = score_match.group(1)

    # --------------------------------------------------------
    # Fixture URL
    # --------------------------------------------------------

    fixture_url = find_fixture_url(line)

    fixtures.append({
        "date": date_text,
        "time": time_text,
        "home": home,
        "away": away,
        "score": score,
        "url": fixture_url
    })


# ------------------------------------------------------------
# REMOVE DUPLICATES
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

fixtures = list(unique.values())


# ------------------------------------------------------------
# SORT FIXTURES
# ------------------------------------------------------------

def sort_key(fixture):

    for fmt in (
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M"
    ):

        try:
            return datetime.strptime(
                f"{fixture['date']} {fixture['time']}",
                fmt
            )

        except ValueError:
            pass

    return datetime.max


fixtures.sort(key=sort_key)


# ------------------------------------------------------------
# SHOW RESULTS
# ------------------------------------------------------------

print()
print("=" * 60)
print("FIXTURES FOUND:", len(fixtures))
print("=" * 60)

for fixture in fixtures:

    result = ""

    if fixture["score"]:
        result = f" ({fixture['score']})"

    print(
        fixture["date"],
        fixture["time"],
        "-",
        fixture["home"],
        "v",
        fixture["away"],
        result
    )


# ------------------------------------------------------------
# CREATE ICALENDAR
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

    dt = sort_key(fixture)

    end = dt + timedelta(
        minutes=90
    )

    # Use FA fixture ID where available
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
            fixture["date"]
            + fixture["time"]
            + fixture["home"]
            + fixture["away"]
        )

    uid = (
        f"{fixture_id}"
        "@knaresborough-town-u18-calendar"
    )

    summary = (
        f"{fixture['home']} v {fixture['away']}"
    )

    if fixture["score"]:

        summary += (
            f" ({fixture['score']})"
        )

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
        (
            "DTSTART;TZID=Europe/London:"
            f"{dt.strftime('%Y%m%dT%H%M%S')}"
        ),
        (
            "DTEND;TZID=Europe/London:"
            f"{end.strftime('%Y%m%dT%H%M%S')}"
        ),
        f"SUMMARY:{ics_escape(summary)}",
        f"DESCRIPTION:{ics_escape(description)}",
        f"URL:{fixture['url']}",
        "END:VEVENT",
    ])


lines.append(
    "END:VCALENDAR"
)


# ------------------------------------------------------------
# WRITE CALENDAR
# ------------------------------------------------------------

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
