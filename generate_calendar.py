import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

TEAM_URL = "https://fulltime.thefa.com/displayTeam.html?id=241163241"
URL = "https://r.jina.ai/" + TEAM_URL

RESULTS_URL = (
    "https://fulltime.thefa.com/index.html?"
    "league=4051434&"
    "selectedCompetition=0&"
    "selectedDivision=113697267&"
    "selectedFixtureGroupKey=1_431850056&"
    "selectedSeason=158072627"
)

OUTPUT = Path("docs/knaresborough-town-u18-women.ics")

TEAM_NAME = "Knaresborough Town U18 Women"


def clean_name(name):
    """Clean a team name while preserving the display name used by Full-Time."""
    name = re.sub(r"\s+", " ", name).strip()
    return name


def parse_date_time(date_text, time_text):
    """Convert Full-Time date/time into a datetime."""
    return datetime.strptime(
        f"{date_text} {time_text}",
        "%d/%m/%y %H:%M"
    )


def find_fixture_url(text):
    """Find a Full-Time fixture URL in a line."""
    match = re.search(
        r"https://fulltime\.thefa\.com/"
        r"(?:displayFixture|displayCountyFixture)\.html\?id=\d+",
        text
    )
    return match.group(0) if match else ""


def normal_links(text):
    """
    Return normal Markdown links from a Jina page.

    Image links (![...](...)) are deliberately ignored. This lets us
    distinguish the actual displayed team name from the image alt text.
    """
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)


def parse_future_fixtures(html):
    """Extract future fixtures involving Knaresborough Town U18 Women."""
    fixtures = []

    lines = html.splitlines()

    for line in lines:
        if TEAM_NAME.lower() not in line.lower():
            continue

        # Match dates and times such as:
        # 19/09/26 10:30
        match = re.search(
            r"(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})",
            line
        )

        if not match:
            continue

        date_text = match.group(1)
        time_text = match.group(2)

        try:
            dt = parse_date_time(date_text, time_text)
        except ValueError:
            continue

        links = normal_links(line)

        # We need the actual displayed team names.
        # Normally the line contains:
        #
        # [Home Team](fixture)
        # ![Home image](...)
        # VS
        # ![Away image](...)
        # [Away Team](fixture)
        #
        # The first and last normal links are therefore the team names.
        team_links = [
            text for text, href in links
            if "fulltime.thefa.com/display" in href
        ]

        if len(team_links) < 2:
            continue

        home = clean_name(team_links[0])
        away = clean_name(team_links[-1])

        if TEAM_NAME.lower() not in (home.lower(), away.lower()):
            continue

        fixture_url = find_fixture_url(line)

        fixtures.append({
            "dt": dt,
            "home": home,
            "away": away,
            "score": None,
            "fixture_url": fixture_url
        })

    # Remove accidental duplicates
    unique = {}
    for fixture in fixtures:
        key = (
            fixture["dt"],
            fixture["home"].lower(),
            fixture["away"].lower()
        )
        unique[key] = fixture

    return sorted(unique.values(), key=lambda x: x["dt"])


def parse_results(html):
    """
    Extract completed Knaresborough results.

    Important:
    We use the actual Markdown link text for the teams rather than the
    image alt text. This avoids names such as:
        Dunnington U18 Girls
    when Full-Time's displayed fixture name is:
        Dunnington U18
    """
    results = []

    lines = html.splitlines()

    for line in lines:
        if not re.search(r"\b\d{2}/\d{2}/\d{2}\b", line):
            continue

        # Look for a score such as 6 - 2 or 8 - 4
        score_match = re.search(
            r"\[(\d+)\s*-\s*(\d+)\]\("
            r"https://fulltime\.thefa\.com/"
            r"(?:displayFixture|displayCountyFixture)\.html\?id=\d+"
            r"\)",
            line
        )

        if not score_match:
            continue

        home_score = int(score_match.group(1))
        away_score = int(score_match.group(2))

        date_match = re.search(r"(\d{2}/\d{2}/\d{2})", line)
        if not date_match:
            continue

        date_text = date_match.group(1)

        # Results pages do not reliably expose the kick-off time.
        # Knaresborough's league fixtures are 10:30, so retain that
        # as the calendar time for completed league matches.
        time_text = "10:30"

        try:
            dt = parse_date_time(date_text, time_text)
        except ValueError:
            continue

        links = normal_links(line)

        # Find the normal Markdown link containing the score.
        score_index = None

        for i, (text, href) in enumerate(links):
            if (
                text.strip() == f"{home_score} - {away_score}"
                and "displayFixture" in href
            ):
                score_index = i
                break

        if score_index is None:
            continue

        # The normal link immediately before the score is the home team.
        # The normal link immediately after the score is the away team.
        if score_index == 0 or score_index + 1 >= len(links):
            continue

        home = clean_name(links[score_index - 1][0])
        away = clean_name(links[score_index + 1][0])

        if TEAM_NAME.lower() not in (home.lower(), away.lower()):
            continue

        fixture_url = score_match.group(0)
        fixture_url = fixture_url[
            fixture_url.find("https://fulltime.thefa.com/")
        :]

        results.append({
            "dt": dt,
            "home": home,
            "away": away,
            "score": f"{home_score} - {away_score}",
            "fixture_url": fixture_url
        })

    # Remove duplicates
    unique = {}

    for result in results:
        key = (
            result["dt"],
            result["home"].lower(),
            result["away"].lower()
        )
        unique[key] = result

    return sorted(unique.values(), key=lambda x: x["dt"])


def make_uid(fixture):
    """Create a stable UID for the calendar event."""
    date_part = fixture["dt"].strftime("%Y%m%d%H%M")
    home = re.sub(r"[^A-Za-z0-9]", "", fixture["home"])
    away = re.sub(r"[^A-Za-z0-9]", "", fixture["away"])

    return f"{date_part}-{home}-{away}@knaresborough-town-u18-calendar"


def escape_ics(text):
    """Escape text for iCalendar."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def make_event(fixture):
    """Create one VEVENT."""
    dt = fixture["dt"]
    dt_end = dt.replace(hour=dt.hour, minute=dt.minute + 90)

    if fixture["score"]:
        summary = (
            f"{fixture['home']} {fixture['score']} {fixture['away']}"
        )
    else:
        summary = f"{fixture['home']} v {fixture['away']}"

    description = (
        "Knaresborough Town U18 Women fixture"
    )

    if fixture["fixture_url"]:
        description += f"\\n{fixture['fixture_url']}"

    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{make_uid(fixture)}",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{escape_ics(summary)}",
        f"DESCRIPTION:{escape_ics(description)}",
        "END:VEVENT"
    ])


def write_calendar(fixtures):
    """Write the complete ICS calendar."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    events = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Knaresborough Town U18 Women//Football Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Knaresborough Town U18 Women",
        "X-WR-CALDESC:Knaresborough Town U18 Women football fixtures",
        "X-WR-TIMEZONE:Europe/London",
    ]

    for fixture in fixtures:
        events.append(make_event(fixture))

    events.append("END:VCALENDAR")

    OUTPUT.write_text(
        "\r\n".join(events) + "\r\n",
        encoding="utf-8"
    )


def main():
    print("Downloading Full-Time team page...")
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    team_html = response.text
    print(f"Team page characters downloaded: {len(team_html)}")

    print("Downloading Full-Time results page...")
    results_response = requests.get(
        "https://r.jina.ai/" + RESULTS_URL,
        timeout=30
    )
    results_response.raise_for_status()

    results_html = results_response.text
    print(f"Results page characters downloaded: {len(results_html)}")

    fixtures = parse_future_fixtures(team_html)
    results = parse_results(results_html)

    # Results take priority over future fixtures.
    # If a fixture has now been played, the completed result replaces it.
    all_events = {}

    for fixture in fixtures:
        key = (
            fixture["dt"].date(),
            fixture["home"].lower(),
            fixture["away"].lower()
        )
        all_events[key] = fixture

    for result in results:
        key = (
            result["dt"].date(),
            result["home"].lower(),
            result["away"].lower()
        )
        all_events[key] = result

    events = sorted(
        all_events.values(),
        key=lambda x: x["dt"]
    )

    print()
    print(f"RESULTS FOUND: {len(results)}")

    for result in results:
        print(
            f"{result['dt'].strftime('%d/%m/%y %H:%M')} - "
            f"{result['home']} {result['score']} {result['away']}"
        )

    print()
    print(f"FUTURE FIXTURES FOUND: {len(fixtures)}")

    for fixture in fixtures:
        print(
            f"{fixture['dt'].strftime('%d/%m/%y %H:%M')} - "
            f"{fixture['home']} v {fixture['away']}"
        )

    print()
    print(f"TOTAL CALENDAR EVENTS: {len(events)}")

    write_calendar(events)

    print(f"Calendar written to: {OUTPUT}")


if __name__ == "__main__":
    main()
