import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_URL = "https://fulltime.thefa.com/displayTeam.html?id=241163241"

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAME = "Knaresborough Town U18 Women"

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
# CLEAN TEXT
# ------------------------------------------------------------

def clean_text(value):
    value = value.strip()

    # Remove Markdown links but keep their visible text
    value = re.sub(
        r'\[([^\]]+)\]\([^)]+\)',
        r'\1',
        value
    )

    # Remove Markdown image syntax but keep the ALT text
    value = re.sub(
        r'!\[([^\]]+)\]\([^)]+\)',
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


# ------------------------------------------------------------
# EXTRACT FIXTURES
# ------------------------------------------------------------

fixtures = []

date_pattern = re.compile(
    r'(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})'
)

# This recognises both normal fixture links and county cup links
fixture_url_pattern = re.compile(
    r'https://fulltime\.thefa\.com/'
    r'(?:displayFixture|displayCountyFixture)\.html\?id=\d+(?:&[^)\s]+)?'
)


for line in text.splitlines():

    date_match = date_pattern.search(line)

    if not date_match:
        continue

    if "VS" not in line:
        continue

    date_text = date_match.group(1)
    time_text = date_match.group(2)

    # --------------------------------------------------------
    # Find team names.
    #
    # FA/Jina represents them like:
    #
    # ![Image 42: Dunnington U18](...)
    #
    # We take the text after "Image XX:"
    # --------------------------------------------------------

    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    # Also allow plain text team names where no image exists
    if len(image_names) >= 2:

        home = image_names[0].strip()
        away = image_names[1].strip()

    else:

        # Fall back to splitting the line around VS
        before_vs, after_vs = line.split(
            "VS",
            1
        )

        before_vs = clean_text(before_vs)
        after_vs = clean_text(after_vs)

        # Remove the date/time and fixture markers
        before_vs = re.sub(
            r'.*?' + re.escape(time_text),
            '',
            before_vs,
            count=1
        )

        before_vs = re.sub(
            r'^\s*[A-Z]{1,2}\s*\|\s*',
            '',
            before_vs
        )

        home = before_vs.strip()

        # Remove everything after the first pipe
        away = after_vs.split("|")[0].strip()

        if not home or not away:
            continue

    # --------------------------------------------------------
    # Only include fixtures involving this team
    # --------------------------------------------------------

    if (
        TEAM_NAME not in home
        and
        TEAM_NAME not in away
        and
        "Knaresborough Town U18 Girls" not in home
        and
        "Knaresborough Town U18 Girls" not in away
    ):
        continue

    # --------------------------------------------------------
    # Find fixture URL
    # --------------------------------------------------------

    url_match = fixture_url_pattern.search(line)

    if url_match:
        fixture_url = url_match.group(0)
    else:
        fixture_url = ""

    # --------------------------------------------------------
    # Look for a score on the same line
    # --------------------------------------------------------

    score_match = re.search(
        r'\b(\d+\s*-\s*\d+)\b',
        line
    )

    score = None

    if score_match:
        score = score_match.group(1)

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
# SORT
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
# SHOW WHAT WE FOUND
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
# CREATE ICS
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

    # Use the FA fixture ID where possible
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

    # --------------------------------------------------------
    # Calendar title
    # --------------------------------------------------------

    summary = (
        f"{fixture['home']} v {fixture['away']}"
    )

    if fixture["score"]:

        summary += (
            f" ({fixture['score']})"
        )

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

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
# WRITE FILE
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
