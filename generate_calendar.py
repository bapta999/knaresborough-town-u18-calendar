import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_URL = "https://fulltime.thefa.com/displayTeam.html?id=241163241"

RESULTS_URL = (
    "https://fulltime.thefa.com/results.html"
    "?league=4051434"
)

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
    headers={"User-Agent": "Mozilla/5.0"}
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


def normalise_name(name):

    name = name.lower()

    name = name.replace(
        "knaresborough town u18 women",
        "knaresborough"
    )

    name = name.replace(
        "knaresborough town u18 girls",
        "knaresborough"
    )

    name = re.sub(
        r'[^a-z0-9]+',
        ' ',
        name
    )

    return " ".join(name.split())


# ------------------------------------------------------------
# FIND FIXTURES
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

        date_time_text = (
            f"{date_text} {time_text}"
        )

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


def extract_results_from_page(page_text):

    results = []

    for line in page_text.splitlines():

        date_match = re.search(
            r'(\d{2}/\d{2}/\d{2,4})',
            line
        )

        if not date_match:
            continue

        score_match = re.search(
            r'\b(\d+)\s*-\s*(\d+)\b',
            line
        )

        if not score_match:
            continue

        names = re.findall(
            r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
            line,
            flags=re.IGNORECASE
        )

        if len(names) >= 2:

            results.append({
                "date": date_match.group(1),
                "home": names[0].strip(),
                "away": names[1].strip(),
                "score": (
                    f"{score_match.group(1)} - "
                    f"{score_match.group(2)}"
                )
            })

    return results


# Try the FA results page through Jina
result_text = ""

try:

    result_response = requests.get(
        "https://r.jina.ai/" + RESULTS_URL,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    if result_response.status_code == 200:

        result_text = result_response.text

        print(
            "Results page downloaded:",
            len(result_text),
            "characters"
        )

except Exception as e:

    print(
        "Results page lookup failed:",
        str(e)
    )


results = extract_results_from_page(
    result_text
)


# ------------------------------------------------------------
# MATCH RESULTS TO OUR FIXTURES
# ------------------------------------------------------------

for fixture in fixtures:

    fixture_date = fixture["date"]

    fixture_home = normalise_name(
        fixture["home"]
    )

    fixture_away = normalise_name(
        fixture["away"]
    )

    for result in results:

        if result["date"] != fixture_date:
            continue

        result_home = normalise_name(
            result["home"]
        )

        result_away = normalise_name(
            result["away"]
        )

        if (
            result_home == fixture_home
            and
            result_away == fixture_away
        ):

            fixture["score"] = result["score"]

            print(
                "RESULT FOUND:",
                fixture["date"],
                fixture["home"],
                fixture["score"],
                fixture["away"]
            )

            break


# ------------------------------------------------------------
# KNOWN RESULT FALLBACK
# ------------------------------------------------------------
#
# 5 September 2026:
# Knaresborough Town U18 Girls 6 - 2
# Scarborough Ladies U18 Girls
#
# This guarantees that the known result is retained even
# if Full-Time temporarily fails to expose it.
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

        print(
            "KNOWN RESULT APPLIED:",
            fixture["home"],
            "6 - 2",
            fixture["away"]
        )


# ------------------------------------------------------------
# FINAL LIST
# ------------------------------------------------------------

print()
print("=" * 60)
print("FINAL CALENDAR")
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
        f"FA Full-Time fixture: "
        f"{fixture['home']} v "
        f"{fixture['away']}"
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
