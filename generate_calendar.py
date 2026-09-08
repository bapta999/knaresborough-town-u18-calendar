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
    headers={"User-Agent": "Mozilla/5.0"}
)

response.raise_for_status()

text = response.text

print("Characters downloaded:", len(text))

if len(text) < 5000:
    print("ERROR: FA page response is unexpectedly short.")
    print(text[:1000])
    raise SystemExit(1)


def clean_name(value):
    value = re.sub(r'!\[Image\s*\d*\s*:\s*([^\]]+)\]\([^)]*\)', r'\1', value)
    value = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', value)
    value = re.sub(r'https?://\S+', '', value)
    value = re.sub(r'\s+', ' ', value)
    value = value.strip(" |:-")
    return value


def parse_date_time(line):
    match = re.search(
        r'(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})',
        line
    )

    if not match:
        return None, None

    return match.group(1), match.group(2)


def find_fixture_url(line):
    match = re.search(
        r'https://fulltime\.thefa\.com/'
        r'(?:displayFixture|displayCountyFixture)\.html\?id=\d+[^)\s]*',
        line
    )

    if match:
        return match.group(0)

    return ""


fixtures = []

for line in text.splitlines():

    date_text, time_text = parse_date_time(line)

    if not date_text:
        continue

    if " VS " not in line and " v " not in line:
        continue

    # First try image alt-text, which is how the FA page presents many teams
    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    if len(image_names) >= 2:

        home = clean_name(image_names[0])
        away = clean_name(image_names[1])

    else:

        if " VS " in line:
            parts = re.split(r'\s+VS\s+', line, maxsplit=1)
        else:
            parts = re.split(r'\s+v\s+', line, maxsplit=1)

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


# Remove duplicate fixtures
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
print("FUTURE FIXTURES FOUND:", len(fixtures))
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
# COMPLETED RESULTS
# ------------------------------------------------------------
#
# The FA Full-Time fixture page currently removes completed
# fixtures from the remaining-fixtures list.
#
# Therefore completed games are kept separately here.
#
# Add future completed results to this list as required.
#

completed_results = [
    {
        "date": "05/09/26",
        "time": "10:30",
        "home": "Knaresborough Town U18 Women",
        "away": "Scarborough Ladies U18",
        "score": "6 - 2",
        "url": ""
    }
]


# Combine results + future fixtures
all_events = completed_results + fixtures

all_events.sort(key=sort_key)


print()
print("=" * 60)
print("TOTAL CALENDAR EVENTS:", len(all_events))
print("=" * 60)

for fixture in all_events:

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


for fixture in all_events:

    dt = sort_key(fixture)

    if dt == datetime.max:
        continue

    end = dt + timedelta(minutes=90)

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


    if fixture["url"]:

        description = (
            f"FA Full-Time fixture: "
            f"{fixture['home']} v {fixture['away']}\\n"
            f"{fixture['url']}"
        )

    else:

        description = (
            f"Knaresborough Town U18 Women result: "
            f"{fixture['home']} {fixture['score']} "
            f"{fixture['away']}"
        )


    # Use fixture ID where available.
    # Use a stable synthetic ID for completed results.
    fixture_id_match = re.search(
        r'id=(\d+)',
        fixture["url"]
    )

    if fixture_id_match:

        uid = (
            f"{fixture_id_match.group(1)}"
            "@knaresborough-town-u18-calendar"
        )

    else:

        uid_base = (
            f"{fixture['date']}-"
            f"{fixture['home']}-"
            f"{fixture['away']}"
        )

        uid_base = re.sub(
            r'[^A-Za-z0-9]+',
            '-',
            uid_base
        ).strip("-")

        uid = (
            f"{uid_base}"
            "@knaresborough-town-u18-calendar"
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
    ])

    if fixture["url"]:
        lines.append(f"URL:{fixture['url']}")

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
print("Events written:", len(all_events))
print("File:", OUTPUT)
print("File size:", OUTPUT.stat().st_size, "bytes")
