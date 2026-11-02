
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
    value = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', value)
    value = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', value)
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
    Conservative identity used only for deduplication.
    Original display names are retained in the calendar.
    """
    name = normalise_team_name(name).upper()

    for word in (
        r'\bFC\b',
        r'\bJUNIORS?\b',
        r'\bGIRLS\b',
        r'\bWOMEN\b',
        r'\bLADIES\b',
    ):
        name = re.sub(word, '', name)

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
    match = re.search(r'(\d{2}/\d{2}/\d{2,4})', line)
    return match.group(1) if match else None


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

    match = re.search(r'\s+VS\s+', line, flags=re.IGNORECASE)

    if not match:
        match = re.search(r'\s+v\s+', line)

    if match:
        left = line[:match.start()]
        right = line[match.end():]

        date_text, time_text = parse_date_time(line)

        if date_text and time_text:
            date_time = f"{date_text} {time_text}"

            if date_time in left:
                left = left.split(date_time, 1)[1]

        return (
            normalise_team_name(left),
            normalise_team_name(right)
        )

    return "", ""


def parse_results(text):
    results = []

    for line in text.splitlines():
        date_text = parse_date_only(line)

        if not date_text:
            continue

        score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', line)

        if not score_match:
            continue

        home = ""
        away = ""

        # Do not treat Markdown image links as ordinary links.
        links = re.findall(
            r'(?<!!)\[([^\]]+)\]\(([^)]+)\)',
            line
        )

        score_link_index = None

        for i, (link_text, link_url) in enumerate(links):
            if re.fullmatch(
                r'\d+\s*[-–]\s*\d+'
                r'(?:\s*\(HT\s*\d+[-–]\d+\))?',
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
                home = normalise_team_name(
                    links[score_link_index - 1][0]
                )

            if score_link_index + 1 < len(links):
                away = normalise_team_name(
                    links[score_link_index + 1][0]
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

            image_names = [x for x in image_names if x]

            if len(image_names) >= 2:
                home, away = image_names[:2]

        # Final fallback to table cells.
        if not home or not away:
            cells = [
                clean_name(x)
                for x in line.split("|")
            ]

            cells = [x for x in cells if x]
            score_index = None

            for i, cell in enumerate(cells):
                if re.fullmatch(
                    r'\d+\s*[-–]\s*\d+'
                    r'(?:\s*\(HT\s*\d+[-–]\d+\))?',
                    cell
                ):
                    score_index = i
                    break

            if score_index is not None:
                if score_index > 0:
                    home = normalise_team_name(
                        cells[score_index - 1]
                    )

                if score_index + 1 < len(cells):
                    away = normalise_team_name(
                        cells[score_index + 1]
                    )

        if not home or not away:
            continue

        if not is_our_team(home) and not is_our_team(away):
            continue

        results.append({
            "date": date_text,
            "time": "10:30",
            "home": normalise_team_name(home),
            "away": normalise_team_name(away),
            "home_score": int(score_match.group(1)),
            "away_score": int(score_match.group(2)),
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

        fixtures.append({
            "date": date_text,
            "time": time_text,
            "home": normalise_team_name(home),
            "away": normalise_team_name(away),
            "home_score": None,
            "away_score": None,
            "url": find_fixture_url(line),
        })

    return fixtures


def unescape_ics(value):
    value = value.replace(r"\n", "\n").replace(r"\N", "\n")
    value = value.replace(r"\,", ",").replace(r"\;", ";")
    value = value.replace(r"\\", "\\")
    return value


def parse_existing_events():
    """
    Preserve both results and upcoming fixtures from the existing ICS.
    """
    if not OUTPUT.exists():
        return []

    text = OUTPUT.read_text(encoding="utf-8")
    events = re.findall(
        r'BEGIN:VEVENT(.*?)END:VEVENT',
        text,
        flags=re.DOTALL
    )

    preserved = []

    for event in events:
        summary_match = re.search(
            r'^SUMMARY:(.*)$',
            event,
            flags=re.MULTILINE
        )

        start_match = re.search(
            r'^DTSTART[^:]*:(\d{8})T(\d{6})',
            event,
            flags=re.MULTILINE
        )

        if not summary_match or not start_match:
            continue

        summary = unescape_ics(summary_match.group(1).strip())

        try:
            dt = datetime.strptime(
                start_match.group(1) + start_match.group(2),
                "%Y%m%d%H%M%S"
            )
        except ValueError:
            continue

        score_match = re.match(
            r'^(.+?)\s+(\d+)\s*[-–]\s*(\d+)\s+(.+)$',
            summary
        )

        if score_match:
            home = score_match.group(1)
            away = score_match.group(4)
            home_score = int(score_match.group(2))
            away_score = int(score_match.group(3))
        else:
            fixture_match = re.match(
                r'^(.+?)\s+(?:v|VS)\s+(.+)$',
                summary,
                flags=re.IGNORECASE
            )

            if not fixture_match:
                continue

            home = fixture_match.group(1)
            away = fixture_match.group(2)
            home_score = None
            away_score = None

        home = normalise_team_name(home)
        away = normalise_team_name(away)

        if not is_our_team(home) and not is_our_team(away):
            continue

        preserved.append({
            "date": dt.strftime("%d/%m/%y"),
            "time": dt.strftime("%H:%M"),
            "home": home,
            "away": away,
            "home_score": home_score,
            "away_score": away_score,
            "url": "",
        })

    return preserved


def validate_source_page(text, label):
    """
    Jina can return a short CAPTCHA/block page with HTTP 200.
    Do not mistake that for a valid page containing no fixtures.
    """
    lowered = text.lower()

    if len(text.strip()) < 5000:
        raise RuntimeError(
            f"{label} is only {len(text)} characters; "
            "likely a block/challenge page. "
            "The existing calendar has NOT been overwritten."
        )

    if "knaresborough" not in lowered:
        raise RuntimeError(
            f"{label} does not contain the expected team name. "
            "The existing calendar has NOT been overwritten."
        )

    blocked_phrases = (
        "captcha",
        "cloudflare",
        "access denied",
        "just a moment",
        "verify you are human",
        "temporarily blocked",
    )

    found = [
        phrase for phrase in blocked_phrases
        if phrase in lowered
    ]

    if found:
        raise RuntimeError(
            f"{label} appears to be blocked: {', '.join(found)}. "
            "The existing calendar has NOT been overwritten."
        )


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


# ------------------------------------------------------------
# MAIN PROCESS
# ------------------------------------------------------------

print("Reading existing calendar...")

existing_events = parse_existing_events()

existing_results = [
    event for event in existing_events
    if event["home_score"] is not None
]

existing_fixtures = [
    event for event in existing_events
    if event["home_score"] is None
]

print("Existing results retained:", len(existing_results))
print("Existing future fixtures retained:", len(existing_fixtures))


print()
print("Downloading Full-Time team page...")

response = requests.get(
    TEAM_PAGE_URL,
    timeout=60,
    headers={"User-Agent": "Mozilla/5.0"}
)

response.raise_for_status()
text = response.text

print("Team page characters downloaded:", len(text))

validate_source_page(text, "Full-Time team page")


print()
print("Downloading Full-Time results page...")

results_response = requests.get(
    RESULTS_PAGE_URL,
    timeout=60,
    headers={"User-Agent": "Mozilla/5.0"}
)

results_response.raise_for_status()
results_text = results_response.text

print("Results page characters downloaded:", len(results_text))

validate_source_page(results_text, "Full-Time results page")


print()
print("PARSING RESULTS FROM TEAM PAGE...")

team_page_results = parse_results(text)

print("Team page results found:", len(team_page_results))


print()
print("PARSING RESULTS FROM RESULTS PAGE...")

results_page_results = parse_results(results_text)

print("Results page results found:", len(results_page_results))


# Combine old and newly discovered results.
all_results = (
    existing_results
    + team_page_results
    + results_page_results
)

unique_results = {}

for result in all_results:
    key = (
        result["date"],
        result_identity_name(result["home"]),
        result_identity_name(result["away"])
    )

    unique_results[key] = result

results = list(unique_results.values())


# Preserve old fixtures and add newly discovered fixtures.
fresh_fixtures = parse_future_fixtures(text)

print()
print("New future fixtures found:", len(fresh_fixtures))


# Do not publish a results-only calendar if all future fixtures
# have disappeared from both the old calendar and the new source.
if not existing_fixtures and not fresh_fixtures:
    raise RuntimeError(
        "No future fixtures were found and there are no existing "
        "future fixtures to preserve. Refusing to write an "
        "incomplete calendar."
    )


all_fixtures = existing_fixtures + fresh_fixtures

unique_fixtures = {}

for fixture in all_fixtures:
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


# Remove fixtures which have now become results.
result_keys = {
    (
        result["date"],
        result_identity_name(result["home"]),
        result_identity_name(result["away"])
    )
    for result in results
}

fixtures = [
    fixture for fixture in fixtures
    if (
        fixture["date"],
        result_identity_name(fixture["home"]),
        result_identity_name(fixture["away"])
    ) not in result_keys
]


events = results + fixtures

events.sort(
    key=lambda x: parse_datetime(
        x["date"],
        x["time"]
    ) or datetime.max
)


print()
print("TOTAL CALENDAR EVENTS:", len(events))


# ------------------------------------------------------------
# BUILD ICS
# ------------------------------------------------------------

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
    end_text = (
        dt + timedelta(hours=2)
    ).strftime("%Y%m%dT%H%M%S")

    uid = make_uid(event)

    if event["home_score"] is not None:
        summary = (
            f'{event["home"]} '
            f'{event["home_score"]} - {event["away_score"]} '
            f'{event["away"]}'
        )
        description = "Result"
    else:
        summary = f'{event["home"]} v {event["away"]}'
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
        lines.append(f'URL:{event["url"]}')

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
