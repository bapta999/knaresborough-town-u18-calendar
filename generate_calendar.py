import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

TEAM_URL = "https://fulltime.thefa.com/displayTeam.html?id=241163241"

RESULTS_URL = (
    "https://fulltime.thefa.com/index.html"
    "?league=4051434"
    "&selectedCompetition=0"
    "&selectedDivision=113697267"
    "&selectedFixtureGroupKey=1_431850056"
    "&selectedSeason=158072627"
)

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAMES = [
    "Knaresborough Town U18 Women",
    "Knaresborough Town U18 Girls"
]


def download(url):
    response = requests.get(
        "https://r.jina.ai/" + url,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    response.raise_for_status()

    return response.text


print("=" * 60)
print("KNARESBOROUGH TOWN U18 WOMEN CALENDAR")
print("=" * 60)


# ============================================================
# DOWNLOAD FIXTURE PAGE
# ============================================================

fixture_text = download(TEAM_URL)

print("Fixture page characters:", len(fixture_text))

if len(fixture_text) < 5000:
    print("ERROR: fixture page unexpectedly short")
    print(fixture_text[:1000])
    raise SystemExit(1)


# ============================================================
# DOWNLOAD RESULTS PAGE
# ============================================================

results_text = download(RESULTS_URL)

print("Results page characters:", len(results_text))

if len(results_text) < 5000:
    print("ERROR: results page unexpectedly short")
    print(results_text[:1000])
    raise SystemExit(1)


def clean_name(value):

    # Markdown image
    value = re.sub(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]\([^)]*\)',
        r'\1',
        value,
        flags=re.IGNORECASE
    )

    # Markdown link
    value = re.sub(
        r'\[([^\]]+)\]\([^)]*\)',
        r'\1',
        value
    )

    # Remove URLs
    value = re.sub(
        r'https?://\S+',
        '',
        value
    )

    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    return value.strip(" |:-")


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


# ============================================================
# FUTURE FIXTURES
# ============================================================

fixtures = []

for line in fixture_text.splitlines():

    date_text, time_text = parse_date_time(line)

    if not date_text:
        continue

    if " VS " not in line and " v " not in line:
        continue

    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    if len(image_names) >= 2:

        # IMPORTANT:
        # Only use the first two team images.
        home = clean_name(image_names[0])
        away = clean_name(image_names[1])

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


# ============================================================
# RESULTS
# ============================================================

results = []

for line in results_text.splitlines():

    date_text, time_text = parse_date_time(line)

    if not date_text:
        continue

    # We only want lines containing an actual score.
    score_match = re.search(
        r'\|\s*(\d+)\s*-\s*(\d+)\s*\|',
        line
    )

    if not score_match:
        continue

    home_score = score_match.group(1)
    away_score = score_match.group(2)

    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    if len(image_names) < 2:
        continue

    home = clean_name(image_names[0])
    away = clean_name(image_names[1])

    if not home or not away:
        continue

    # Only results involving Knaresborough
    if not any(
        team in home or team in away
        for team in TEAM_NAMES
    ):
        continue

    results.append({
        "date": date_text,
        "time": time_text,
        "home": home,
        "away": away,
        "score": f"{home_score} - {away_score}",
        "url": ""
    })


# Remove duplicate results

unique_results = {}

for result in results:

    key = (
        result["date"],
        result["home"],
        result["away"]
    )

    unique_results[key] = result

results = list(unique_results.values())


# ============================================================
# REMOVE FUTURE FIXTURE IF IT IS NOW A RESULT
# ============================================================

result_keys = set()

for result in results:

    result_keys.add(
        (
            result["date"],
            result["home"],
            result["away"]
        )
    )


fixtures = [
    fixture
    for fixture in fixtures
    if (
        fixture["date"],
        fixture["home"],
        fixture["away"]
    ) not in result_keys
]


# ============================================================
# SORT
# ============================================================

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
results.sort(key=sort_key)


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 60)
print("RESULTS FOUND:", len(results))
print("=" * 60)

for result in results:

    print(
        result["date"],
        "-",
        result["home"],
        result["score"],
        result["away"]
    )


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


all_events = results + fixtures

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


# ============================================================
# CREATE ICS
# ============================================================

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
    "X-WR-CALDESC:Knaresborough Town U18 Women fixtures and results",
    "X-WR-TIMEZONE:Europe/London",
]


now = datetime.utcnow().strftime(
    "%Y%m%dT%H%M%SZ"
)


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

        description = (
            f"Knaresborough Town U18 Women result: "
            f"{fixture['home']} {fixture['score']} "
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
            f"{fixture['away']}\\n"
            f"{fixture['url']}"
        )


    if fixture["url"]:

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

            uid = (
                f"{fixture['date']}-"
                f"{fixture['home']}-"
                f"{fixture['away']}"
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
        lines.append(
            f"URL:{fixture['url']}"
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
    "\r\n".join(lines) + "\r\n",
    encoding="utf-8"
)


print()
print("=" * 60)
print("CALENDAR CREATED")
print("=" * 60)

print(
    "Events written:",
    len(all_events)
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
