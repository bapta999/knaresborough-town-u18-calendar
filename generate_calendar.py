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

    image_match = re.search(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        value,
        flags=re.IGNORECASE
    )

    if image_match:
        return image_match.group(1).strip()

    value = re.sub(
        r'\[([^\]]+)\]\([^)]+\)',
        r'\1',
        value
    )

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
    match = re.search(
        r'https://fulltime\.thefa\.com/'
        r'displayFixture\.html\?id=\d+',
        line
    )

    if match:
        return match.group(0)

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


def get_fixture_id(url):
    match = re.search(
        r'id=(\d+)',
        url
    )

    if match:
        return match.group(1)

    return None


# ------------------------------------------------------------
# FIND THE 14 FIXTURES
# ------------------------------------------------------------

fixtures = []

for line in text.splitlines():

    date_text, time_text = parse_date_time(line)

    if not date_text:
        continue

    if "VS" not in line and " v " not in line:
        continue

    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    if len(image_names) >= 2:

        home = image_names[0].strip()
        away = image_names[1].strip()

    else:

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

    if not any(
        team in home or team in away
        for team in TEAM_NAMES
    ):
        continue

    fixture_url = find_fixture_url(line)

    fixtures.append({
        "date": date_text,
        "time": time_text,
        "home": home,
        "away": away,
        "score": None,
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


print()
print("=" * 60)
print("FIXTURES FOUND:", len(fixtures))
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


# ------------------------------------------------------------
# RESULT LOOKUP
# ------------------------------------------------------------

print()
print("=" * 60)
print("CHECKING RESULTS")
print("=" * 60)


def lookup_result(fixture):

    fixture_url = fixture["url"]

    if not fixture_url:
        return None

    result_url = "https://r.jina.ai/" + fixture_url

    try:

        result_response = requests.get(
            result_url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if result_response.status_code != 200:
            return None

        result_text = result_response.text

        # Look for a normal football score
        scores = re.findall(
            r'\b(\d+)\s*-\s*(\d+)\b',
            result_text
        )

        if not scores:
            return None

        # Prefer a score occurring near the team names
        team_pos = result_text.lower().find(
            fixture["home"].lower()
        )

        if team_pos == -1:
            team_pos = result_text.lower().find(
                "knaresborough"
            )

        if team_pos >= 0:

            nearby = result_text[
                max(0, team_pos - 300):
                team_pos + 1000
            ]

            nearby_scores = re.findall(
                r'\b(\d+)\s*-\s*(\d+)\b',
                nearby
            )

            if nearby_scores:

                home_score, away_score = (
                    nearby_scores[0]
                )

                return (
                    f"{home_score} - {away_score}"
                )

        # Fallback to first score on page
        home_score, away_score = scores[0]

        return f"{home_score} - {away_score}"

    except Exception as e:

        print(
            "Result lookup failed:",
            fixture["date"],
            fixture["home"],
            "v",
            fixture["away"],
            "-",
            str(e)
        )

        return None


# ------------------------------------------------------------
# LOOK UP RESULTS FOR COMPLETED FIXTURES
# ------------------------------------------------------------

today = datetime.now()

for fixture in fixtures:

    fixture_date = sort_key(fixture)

    # Only bother checking games that have already happened
    if fixture_date.date() > today.date():
        continue

    score = lookup_result(fixture)

    if score:
        fixture["score"] = score

        print(
            "RESULT:",
            fixture["date"],
            fixture["home"],
            fixture["score"],
            fixture["away"]
        )


# ------------------------------------------------------------
# KNOWN RESULT FALLBACK
# ------------------------------------------------------------
#
# This is the match we already know was played:
#
# 05/09/26
# Knaresborough Town U18 Girls 6-2
# Scarborough Ladies U18 Girls
#
# This also protects the calendar if FA Full-Time's result
# page doesn't expose the score to the scraper.
# ------------------------------------------------------------

for fixture in fixtures:

    if (
        fixture["date"] == "05/09/26"
        and
        "Knaresborough" in fixture["home"]
        and
        "Scarborough" in fixture["away"]
    ):

        fixture["score"] = "6 - 2"


# ------------------------------------------------------------
# SHOW FINAL FIXTURE LIST
# ------------------------------------------------------------

print()
print("=" * 60)
print("FINAL CALENDAR FIXTURES")
print("=" * 60)

for fixture in fixtures:

    if fixture["score"]:

        print(
            fixture["date"],
            "-",
            fixture["home"],
            fixture["score"],
            fixture["away"]
        )

    else:

        print(
            fixture["date"],
            "-",
            fixture["home"],
            "v",
            fixture["away"]
        )


# ------------------------------------------------------------
# ICALENDAR
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

    fixture_id = get_fixture_id(
        fixture["url"]
    )

    if not fixture_id:

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
    # Summary
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    description = (
        f"FA Full-Time fixture: "
        f"{fixture['home']} v "
        f"{fixture['away']}"
    )

    if fixture["score"]:

        description += (
            f"\\nResult: "
            f"{fixture['score']}"
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
