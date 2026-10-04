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

    value = re.sub(
        r'!\[[^\]]*\]\([^)]*\)',
        '',
        value
    )

    value = re.sub(
        r'\[([^\]]+)\]\([^)]*\)',
        r'\1',
        value
    )

    value = re.sub(r'https?://\S+', '', value)

    value = re.sub(
        r'\bImage\s*\d*\s*:\s*',
        '',
        value,
        flags=re.IGNORECASE
    )

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


def result_identity_name(name):
    """
    Creates a conservative identity used ONLY for deduplication.

    The FA sometimes displays the same opponent differently on
    different pages, for example:

      Bishopthorpe White Rose U17 Girls
      BISHOPTHORPE WHITE ROSE FC U17 Girls

      Hamilton Panthers U18 Girls
      HAMILTON PANTHERS JUNIORS U18 Girls

      Dunnington U18 Girls
      Dunnington U18

    These should be treated as the same team for deduplication,
    while the original display name is retained in the calendar.
    """

    name = normalise_team_name(name).upper()

    name = re.sub(
        r'\bFC\b',
        '',
        name
    )

    name = re.sub(
        r'\bJUNIORS?\b',
        '',
        name
    )

    name = re.sub(
        r'\bGIRLS\b',
        '',
        name
    )

    name = re.sub(
        r'\bWOMEN\b',
        '',
        name
    )

    name = re.sub(
        r'\bLADIES\b',
        '',
        name
    )

    name = re.sub(r'[^A-Z0-9]+', ' ', name)

    name = re.sub(r'\s+', ' ', name)

    return name.strip()


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

        score_match = re.search(
            r'(\d+)\s*[-–]\s*(\d+)',
            line
        )

        if not score_match:
            continue

        home = ""
        away = ""

        # (?<!!) means the opening [ must NOT be preceded by !.
        # This prevents Markdown image links being treated as
        # normal team links.
        links = re.findall(
            r'(?<!!)'
            r'\[([^\]]+)\]'
            r'\(([^)]+)\)',
            line
        )

        score_link_index = None

        for i, (link_text, link_url) in enumerate(links):

            if re.fullmatch(
                r'\d+\s*[-–]\s*\d+(?:\s*\(HT\s*\d+[-–]\d+\))?',
                link_text.strip()
            ):

                if (
                    "displayFixture" in link_url
                    or "displayCountyFixture" in link_url
                ):
                    score_link_index = i
                    break

        if score_link_index is not None:

            if score_link_index > 0:

                possible_home = links[
                    score_link_index - 1
                ][0]

                if possible_home:
                    home = normalise_team_name(
                        possible_home
                    )

            if score_link_index + 1 < len(links):

                possible_away = links[
                    score_link_index + 1
                ][0]

                if possible_away:
                    away = normalise_team_name(
                        possible_away
                    )

        # Fallback to image alt text.
        if not home or not away:

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

        # Final fallback to table cells.
        if not home or not away:

            cells = [
                clean_name(x)
                for x in line.split("|")
            ]

            cells = [
                x for x in cells
                if x
            ]

            score_index = None

            for i, cell in enumerate(cells):

                if re.fullmatch(
                    r'\d+\s*[-–]\s*\d+(?:\s*\(HT\s*\d+[-–]\d+\))?',
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


def parse_existing_results():
    """
    Read results already present in the existing ICS.

    This prevents older completed matches disappearing simply
    because the FA has stopped showing them on its current
    results pages.
    """

    if not OUTPUT.exists():
        return []

    text = OUTPUT.read_text(
        encoding="utf-8"
    )

    results = []

    events = re.findall(
        r'BEGIN:VEVENT(.*?)END:VEVENT',
        text,
        flags=re.DOTALL
    )

    for event in events:

        summary_match = re.search(
            r'^SUMMARY:(.*)$',
            event,
            flags=re.MULTILINE
        )

        start_match = re.search(
            r'DTSTART[^:]*:(\d{8})T(\d{6})',
            event
        )

        if not summary_match or not start_match:
            continue

        summary = summary_match.group(1)

        score_match = re.match(
            r'(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)',
            summary
        )

        if not score_match:
            continue

        home = score_match.group(1).replace("\\,", ",")
        away = score_match.group(4).replace("\\,", ",")
        home_score = int(score_match.group(2))
        away_score = int(score_match.group(3))

        date_raw = start_match.group(1)
        time_raw = start_match.group(2)

        try:
            dt = datetime.strptime(
                date_raw + time_raw,
                "%Y%m%d%H%M%S"
            )
        except ValueError:
            continue

        results.append({
            "date": dt.strftime("%d/%m/%y"),
            "time": dt.strftime("%H:%M"),
            "home": home,
            "away": away,
            "home_score": home_score,
            "away_score": away_score,
            "url": "",
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


print("Reading existing calendar...")

existing_results = parse_existing_results()

print(
    "Existing results retained:",
    len(existing_results)
)


print()
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

print(
    "Team page characters downloaded:",
    len(text)
)


print()
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

print(
    "Results page characters downloaded:",
    len(results_text)
)


print()
print("PARSING RESULTS FROM TEAM PAGE...")

team_page_results = parse_results(text)

print(
    "Team page results found:",
    len(team_page_results)
)


print()
print("PARSING RESULTS FROM RESULTS PAGE...")

results_page_results = parse_results(results_text)

print(
    "Results page results found:",
    len(results_page_results)
)


# Combine:
#
# 1. Results already in the calendar
# 2. Fresh results from the team page
# 3. Fresh results from the results page
#
# Fresh results are added after existing results so that current
# FA data takes precedence where the same match is found.

all_results = (
    existing_results
    + team_page_results
    + results_page_results
)


# Deduplicate results using a normalised identity for each team.
#
# This deals with FA naming differences such as:
#
# Bishopthorpe White Rose U17 Girls
# BISHOPTHORPE WHITE ROSE FC U17 Girls
#
# Hamilton Panthers U18 Girls
# HAMILTON PANTHERS JUNIORS U18 Girls
#
# Dunnington U18 Girls
# Dunnington U18

unique_results = {}

for result in all_results:

    key = (
        result["date"],
        result_identity_name(result["home"]),
        result_identity_name(result["away"])
    )

    unique_results[key] = result


results = list(unique_results.values())


fixtures = parse_future_fixtures(text)


# Remove duplicate future fixtures.
unique_fixtures = {}

for fixture in fixtures:

    key = (
        fixture["date"],
        fixture["time"],
        result_identity_name(fixture["home"]),
        result_identity_name(fixture["away"])
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


# Remove any fixture which has now become a result.
result_keys = {
    (
        result["date"],
        result_identity_name(result["home"]),
        result_identity_name(result["away"])
    )
    for result in results
}

fixtures = [
    fixture
    for fixture in fixtures
    if (
        fixture["date"],
        result_identity_name(fixture["home"]),
        result_identity_name(fixture["away"])
    ) not in result_keys
]


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
