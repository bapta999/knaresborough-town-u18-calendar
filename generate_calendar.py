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
    "Knaresborough Town U18 Girls",
]

TEAM_PAGE_URL = "https://r.jina.ai/" + TEAM_URL
RESULTS_PAGE_URL = "https://r.jina.ai/" + RESULTS_URL


def clean_name(value):
    value = re.sub(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]\([^)]*\)',
        r'\1',
        value,
        flags=re.IGNORECASE
    )
    value = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', value)
    value = re.sub(r'https?://\S+', '', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip(" |:-")


def normalise_team_name(name):
    name = clean_name(name)

    if re.search(
        r'Knaresborough Town U18 (Women|Girls)',
        name,
        re.IGNORECASE
    ):
        return "Knaresborough Town U18 Women"

    return name


def parse_date_time(line):
    match = re.search(
        r'(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})',
        line
    )

    if not match:
        return None, None

    return match.group(1), match.group(2)


def parse_date_only(line):
    match = re.search(
        r'(\d{2}/\d{2}/\d{2,4})',
        line
    )

    if not match:
        return None

    return match.group(1)


def find_fixture_url(line):
    match = re.search(
        r'https://fulltime\.thefa\.com/'
        r'(?:displayFixture|displayCountyFixture)\.html'
        r'\?id=\d+[^)\s]*',
        line
    )

    return match.group(0) if match else ""


def is_our_team(name):
    return any(
        team.lower() in name.lower()
        for team in TEAM_NAMES
    )


def extract_teams(line):
    """
    Extract team names from a Full-Time/Jina line.

    First preference is image alt text.
    """

    image_names = re.findall(
        r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
        line,
        flags=re.IGNORECASE
    )

    image_names = [
        normalise_team_name(x)
        for x in image_names
    ]

    image_names = [
        x for x in image_names
        if x and x.lower() != "image"
    ]

    if len(image_names) >= 2:
        return image_names[0], image_names[1]

    # Normal fixture: Team VS Team
    match = re.search(
        r'\s+VS\s+',
        line,
        flags=re.IGNORECASE
    )

    if match:
        left = line[:match.start()]
        right = line[match.end():]

        date_text, time_text = parse_date_time(line)

        if date_text and time_text:
            date_time = f"{date_text} {time_text}"

            if date_time in left:
                left = left.split(date_time, 1)[1]

        home = normalise_team_name(left)
        away = normalise_team_name(right)

        return home, away

    # Cup fixtures sometimes use lower-case "v"
    match = re.search(
        r'\s+v\s+',
        line
    )

    if match:
        left = line[:match.start()]
        right = line[match.end():]

        date_text, time_text = parse_date_time(line)

        if date_text and time_text:
            date_time = f"{date_text} {time_text}"

            if date_time in left:
                left = left.split(date_time, 1)[1]

        home = normalise_team_name(left)
        away = normalise_team_name(right)

        return home, away

    return "", ""


def parse_results(text):
    results = []

    for line in text.splitlines():

        date_text = parse_date_only(line)

        if not date_text:
            continue

        # Diagnostic only:
        # show lines containing the scores we expect.
        if any(
            score in line
            for score in ["6 - 2", "8 - 4", "6–2", "8–4"]
        ):
            print()
            print("POSSIBLE RESULT LINE FOUND:")
            print(line)

        # Look for a numeric score anywhere in the line.
        score_match = re.search(
            r'(\d+)\s*[-–]\s*(\d+)',
            line
        )

        if not score_match:
            continue

        image_names = re.findall(
            r'!\[Image\s*\d*\s*:\s*([^\]]+)\]',
            line,
            flags=re.IGNORECASE
        )

        image_names = [
            normalise_team_name(x)
            for x in image_names
        ]

        image_names = [
            x for x in image_names
            if x
        ]

        if len(image_names) >= 2:

            home = image_names[0]
            away = image_names[1]

        else:

            # Try extracting the teams from table cells.
            cells = [
                clean_name(x)
                for x in line.split("|")
            ]

            cells = [
                x for x in cells
                if x
            ]

            home = ""
            away = ""

            score_index = None

            for i, cell in enumerate(cells):

                if re.fullmatch(
                    r'\d+\s*[-–]\s*\d+',
                    cell
                ):
                    score_index = i
                    break

            if score_index is not None:

                if score_index > 0:
                    home = cells[score_index - 1]

                if score_index + 1 < len(cells):
                    away = cells[score_index + 1]

            home = normalise_team_name(home)
            away = normalise_team_name(away)

        if not home or not away:
            continue

        if not is_our_team(home) and not is_our_team(away):
            continue

        home = normalise_team_name(home)
        away = normalise_team_name(away)

        home_score = int(score_match.group(1))
        away_score = int(score_match.group(2))

        results.append({
            "date": date_text,
            "time": "10:30",
            "home": home,
            "away": away,
            "home_score": home_score,
            "away_score": away_score,
            "url": find_fixture_url(line),
        })

    return results


def parse_future_fixtures(text):
    fixtures = []

    for line in text.splitlines():

        date_text, time_text = parse_date_time(line)

        if not date_text:
            continue

        if not re.search(r'\s(?:VS|v)\s', line):
            continue

        if re.search(r'\|\s*\d+\s*[-–]\s*\d+\s*\|', line):
            continue

        home, away = extract_teams(line)

        if not home or not away:
            continue

        if not is_our_team(home) and not is_our_team(away):
            continue

        home = normalise_team_name(home)
        away = normalise_team_name(away)

        fixtures.append({
            "date": date_text,
            "time": time_text,
            "home": home,
            "away": away,
            "home_score": None,
            "away_score": None,
            "url": find_fixture_url(line),
        })

    return fixtures


def parse_datetime(date_text, time_text):

    for fmt in ("%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(
                f"{date_text} {time_text}",
                fmt
            )
        except ValueError:
            pass

    return None


def make_uid(fixture):

    return (
        fixture["date"]
        + "_"
        + fixture["time"]
        + "_"
        + fixture["home"]
        + "_"
        + fixture["away"]
    ).replace(" ", "").replace("/", "").replace(":", "")


def escape_ics(value):

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


print("Downloading Full-Time team page...")

response = requests.get(
    TEAM_PAGE_URL,
    timeout=60,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

response.raise_for_status()

text = response.text

print("Team page characters downloaded:", len(text))


print("Downloading Full-Time results page...")

results_response = requests.get(
    RESULTS_PAGE_URL,
    timeout=60,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

results_response.raise_for_status()

results_text = results_response.text

print("Results page characters downloaded:", len(results_text))


print()
print("SEARCHING RESULTS PAGE FOR SCORES...")

for score in ["6 - 2", "8 - 4", "6–2", "8–4"]:

    position = results_text.find(score)

    if position >= 0:

        print()
        print("FOUND:", score)
        print(
            results_text[
                max(0, position - 500):
                position + 500
            ]
        )

    else:

        print("NOT FOUND:", score)


results = parse_results(results_text)
fixtures = parse_future_fixtures(text)


# Remove duplicate results.
unique_results = {}

for result in results:

    key = (
        result["date"],
        result["time"],
        result["home"],
        result["away"]
    )

    unique_results[key] = result

results = list(unique_results.values())


# Remove duplicate fixtures.
unique_fixtures = {}

for fixture in fixtures:

    key = (
        fixture["date"],
        fixture["time"],
        fixture["home"],
        fixture["away"]
    )

    unique_fixtures[key] = fixture

fixtures = list(unique_fixtures.values())


print()
print("RESULTS FOUND:", len(results))

for result in results:

    print(
        f'{result["date"]} {result["time"]} - '
        f'{result["home"]} '
        f'{result["home_score"]} - {result["away_score"]} '
        f'{result["away"]}'
    )


print()
print("FUTURE FIXTURES FOUND:", len(fixtures))

for fixture in fixtures:

    print(
        f'{fixture["date"]} {fixture["time"]} - '
        f'{fixture["home"]} v {fixture["away"]}'
    )


# Combine results and future fixtures.
events = results + fixtures


# Sort chronologically.
events.sort(
    key=lambda x: parse_datetime(
        x["date"],
        x["time"]
    ) or datetime.max
)


print()
print("TOTAL CALENDAR EVENTS:", len(events))


# Build ICS.
lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Knaresborough Town U18 Women//Football Calendar//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Knaresborough Town U18 Women",
    "X-WR-CALDESC:Knaresborough Town U18 Women football fixtures",
    "X-WR-TIMEZONE:Europe/London",
]


for event in events:

    dt = parse_datetime(
        event["date"],
        event["time"]
    )

    if not dt:
        continue

    start = dt.strftime("%Y%m%dT%H%M%S")

    # Assume 2-hour match duration.
    end = dt + timedelta(hours=2)

    end_text = end.strftime("%Y%m%dT%H%M%S")

    uid = make_uid(event)

    if event["home_score"] is not None:

        summary = (
            f'{event["home"]} '
            f'{event["home_score"]} - {event["away_score"]} '
            f'{event["away"]}'
        )

        description = "Result"

    else:

        summary = (
            f'{event["home"]} v {event["away"]}'
        )

        description = "Upcoming fixture"

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{escape_ics(uid)}@knaresborough-town-u18-calendar",
        f"DTSTART;TZID=Europe/London:{start}",
        f"DTEND;TZID=Europe/London:{end_text}",
        f"SUMMARY:{escape_ics(summary)}",
        f"DESCRIPTION:{escape_ics(description)}",
    ])

    if event.get("url"):
        lines.append(
            f"URL:{event['url']}"
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
print("Calendar written to:", OUTPUT)
