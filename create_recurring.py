#!/usr/bin/env python3
# Copyright (c) 2026 Simon Thompson
"""Create "recurring" events for a wordpess site with events plugin added.

Events that are created a not recurring (which requires paid plugin), but
will create multiple instances of the event.
"""

import base64
import html
import logging
import os
import re
import sys
import time
import unicodedata
from typing import Annotated

import pendulum
import requests
import typer
import yaml
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from rich.console import Console
from rich.logging import RichHandler

load_dotenv()

WORDPRESS_USER = os.getenv("WORDPRESS_USER")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
WORDPRESS_CREDS = WORDPRESS_USER + ":" + WORDPRESS_PASSWORD
wordpress_token = base64.b64encode(WORDPRESS_CREDS.encode())
wordpress_header = {"Authorization": "Basic " + wordpress_token.decode("utf-8")}

WORDPRESS_SERVER = os.getenv("WORDPRESS_SERVER")
CONFIG_FILE = os.getenv("CONFIG_FILE")
EVENT_API_BASE = os.getenv("EVENT_API_BASE")
DEFAULT_ORGANISER = os.getenv("DEFAULT_ORGANISER")
DEFAULT_VENUE = os.getenv("DEFAULT_VENUE")

summer = {8}

with open(CONFIG_FILE, encoding="utf-8") as configfile:
    # Use safe_load to prevent execution of arbitrary code
    configdata = yaml.safe_load(configfile)

CATMAP = {}
TAGMAP = {}
ORGMAP = {}
VENUEMAP = {}
EVENTCACHE = {}
events = configdata["events"]

# this is the max number of wordpress pages to gather
MAXPAGES = 50

console = Console()
cli = typer.Typer(rich_markup_mode="rich")


def setup_logging(verbose: bool) -> None:
    """Setup logging using Rich for beautiful CLI output."""
    level = logging.DEBUG if verbose else logging.INFO

    # Configure the root logger to use RichHandler
    logging.basicConfig(
        level=level,
        format="%(message)s",  # Rich handles the timestamp and level formatting
        # show_time - should the time stamp be shown?
        # show_level - should the log level be shown?
        # show_path - should the script and line number be included?
        handlers=[RichHandler(rich_tracebacks=True, markup=True, show_time=False, show_level=False, show_path=False)],
    )

    # Silence noisy third-party libraries
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def cache_events(startdate: str, weekcount: int, api_url: bool = None) -> None:
    """Read the current events from wordpress.

    Args:
        startdate: ISO formatted date to start from
        weekcount: Number of weeks to cache
        api_url: The URL for the wordpress event API
    """
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events"

    # calculate the end date
    enddate = pendulum.parse(startdate).add(weeks=int(weekcount)).format("YYYY-MM-DD")

    page = 1
    total_pages = 1
    params = {
        "start_date": f"{startdate} 00:00:00",
        "end_date": f"{enddate} 23:59:59",
        "per_page": 50,  # Get as many as possible in one go
        "page": page,
    }

    console.print("Caching existing events")
    while page <= total_pages:
        response = requests.get(api_url, params=params)

        if response.status_code != requests.codes.ok:
            raise HTTPError(f"Unexpected error code: {response.status_code} with {response.text}", response=response)

        data = response.json()
        if page == 1:
            total_pages = data["total_pages"]

        for event in data["events"]:
            EVENTCACHE[event["slug"]] = {"id": event["id"]}
        page += 1
        params["page"] = page


def create_wordpress_event(
    data: dict, api_url: str = None, headers: dict = None, dryrun: bool = False, update: bool = False
) -> None:
    """Create a wordpress event.

    Args:
        data: The Payload formatted data for the event
        api_url: The URL for the wordpress event API
        headers: Requests object additional headers to send
        dryrun: Dry run create or not
        update: Overwrite existing event?
    """
    api_url = api_url or f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events"
    headers = headers or wordpress_header

    method = "POST"

    if data["slug"] in EVENTCACHE:
        if not update:
            console.print(f"Event is present: {data['slug']} - skipping")
            return
        console.print(f"Update event {data['slug']}")
        method = "PATCH"
        data["id"] = int(EVENTCACHE[data["slug"]]["id"])
        api_url = f"{api_url}/{data['id']}"

    logging.debug(api_url)

    if not dryrun:
        response = requests.request(method=method, url=api_url, json=data, headers=headers, timeout=10)
        response_json = response.json()
        console.print(f"Event Title: {response_json['title']}")
        console.print(f"Event URL: {response_json['url']}")
        logging.debug(response_json)
        EVENTCACHE[data["slug"]] = response_json["id"]
    else:
        console.print(f"Would create {data['slug']} at {data['start_date']}")
        logging.debug(data)


def get_next_week_by_day(startdate: str, day: str) -> str:
    """Get the date of the next week by day.

    Args:
        startdate: ISO formatted date to start lookging for the next instance of day
        day: The index of the day number (e.g. Sunday = 6)

    Returns:
        An ISO formatted date of the next day
    """
    # either "today" or the startdate
    base_dt = pendulum.parse(startdate) if startdate else pendulum.now()
    # find the next day instance after the date
    next_date = base_dt.next(day).to_date_string()
    logging.debug(f"With {startdate} the next {day} is {next_date}")
    return next_date


def get_dates_for_n_weeks(startdate: str, weekcount: int) -> list:
    """Get the date of the day for the next N weeks.

    Args:
        startdate: ISO formatted date to start lookging for the next instance of day
        weekcount: The number of weeks to look forward to

    Returns:
        A list of dates for the same date for the next N weeks
    """
    # start with the first date
    dates = [startdate]
    for i in range(1, weekcount):
        dates.append(pendulum.parse(startdate).add(weeks=i).to_date_string())
    return dates


def decode_date(date: str) -> dict:
    """Decode the date string to something nicer.

    Args:
        date: ISO formatted date string

    Returns:
        dict of data represented by the date
    """
    dt = pendulum.parse(date)
    day = dt.day

    # work out the suffis for the day, i.e. 1st or 5th etc
    if 11 <= day <= 13:  # noqa: PLR2004
        # these are the teens so 11th instead of 11st
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")  # codespell:ignore nd

    date_info = {
        "daystr": dt.format("dddd"),
        "datenum": dt.format("DD"),
        "monthstr": dt.format("MMMM"),
        "monthnum": dt.format("MM"),
        "yearstr": dt.format("YYYY"),
        "suffixstr": suffix,
        "week_num": (day - 1) // 7 + 1,
    }

    logging.debug(f"{date_info}")
    return date_info


def format_title(date_info: dict, title: str, include_date: bool = False) -> str:
    """Format the title of an event.

    Args:
        date_info: Dict from decode_date with information about the date
        title: The title text to include
        include_date: Include the date in the title?

    Returns:
        A formatted string for the title
    """
    if include_date:
        return (
            f"{title} "
            f"[{date_info['daystr']} {date_info['datenum'].lstrip('0')}{date_info['suffixstr']} "
            f"{date_info['monthstr']} {date_info['yearstr']}]"
        )
    return f"{title}"


def build_slug(date_info: dict, title: str) -> str:
    """Build the slug for the event.

    This function will remove characters from the slug that cannot appear, for
    example HTML encoded entities or brackets and so on

    Args:
        date_info: Dict from decode_date with information about the date
        title: The title text to include

    Returns:
        The constructing string slug
    """
    slug = f"{date_info['yearstr']}-{date_info['monthnum']}-{date_info['datenum']}-{(title.lower()).replace(' ', '-')}"
    logging.debug(f"Initial slug:\t{slug}")

    # build unicode version of slug with HTML stripped
    slug = html.unescape(slug)
    # Normalize Unicode to decompose combined characters (e.g., é -> e + ´)
    # NFD (Normalization Form Decomposition) separates the character from its accent
    slug = unicodedata.normalize("NFD", slug)
    # now strip out the non mark spaces (the accents)
    slug = "".join(c for c in slug if unicodedata.category(c) != "Mn")

    # now remove any left over unwanted characters
    slug = slug.translate(str.maketrans("", "", "()&$'[]{}"))
    slug = re.sub(r"\-+", "-", slug)
    slug = slug.strip("-")
    logging.debug(f"Final slug:\t{slug}")
    return slug


def format_event(
    title: str,
    description: str,
    excerpt: str,
    date: str,
    date_info: dict,
    starttime: str,
    endtime: str,
    tags: list[str] = None,
    categories: list[str] = None,
    venue: str = None,
    organiser: str = None,
    image: int = None,
) -> dict:
    """Format an event for wordpress events calendar.

    Args:
        title: The title for the event
        description: HTML formatted string for the description
        excerpt: HTML formatted string for the except - usually a shorter version of description
        date: ISO formatted date for event
        date_info: Representation of the date
        starttime: Start time of the event of format HH:MM:SS
        endtime: End time of the event of format HH:MM:SS
        tags: tags to apply to event in string format
        categories: categories to apply to event in string format
        venue: Name of the venue slug
        organiser: Name of the organiser slug
        image: The featured image reference id

    Returns:
        dict of the data for the wordpress API
    """
    tags = tags or []
    categories = categories or []
    venue = get_venueid(venue=venue)
    organiser = get_orgid(organiser=organiser)

    data = {
        "title": str(format_title(date_info=date_info, title=title)),
        "slug": str(build_slug(date_info=date_info, title=title)),
        "description": str(description),
        "excerpt": str(excerpt),
        "start_date": f"{date} {starttime}",
        "end_date": f"{date} {endtime}",
        "venue": str(venue),
        "organizer": str(organiser),
        "status": "publish",
        "show_map": True,
        "show_map_link": True,
        "tags": [],
        "categories": [],
    }

    for tag in tags:
        data["tags"].append(get_tagid(tag))

    for cat in categories:
        data["categories"].append(get_catid(cat))

    if image:
        data["image"] = str(image)

    logging.debug("Formatted event:")
    logging.debug(data)
    return data


def get_venueid(venue: str = None, api_url: str = None, headers: dict = None) -> int:
    """Lookup or read cache of venue id for the venue.

    Args:
        venue: Venue slug name
        api_url: The URL for the wordpress events venues API
        headers: Requests object additional headers to send

    Returns:
        integer ID of the venue
    """
    venue = venue or DEFAULT_VENUE
    api_url = api_url or f"{WORDPRESS_SERVER}{EVENT_API_BASE}/venues?&hide_empty=0"

    try:
        return int(VENUEMAP[venue])
    except KeyError:
        if not VENUEMAP:
            console.print("Venuemap is empty, try to populate it")
            response = requests.get(f"{api_url}", timeout=10)
            data = response.json()
            for venuedata in data["venues"]:
                VENUEMAP[venuedata["slug"]] = venuedata["id"]
            logging.debug(f"VENUEMAP after populate: {VENUEMAP}")

        # we need to use a different lookup to the organiser API by-slug
        if venue not in VENUEMAP:
            console.print(f"Lookup venue {venue}")
            slug_api_url = api_url.replace("?", f"/by-slug/{venue}?")
            response = requests.get(f"{slug_api_url}", timeout=10)
            data = response.json()
            if not data:
                raise ValueError(f"lookup venue {venue} failed") from None
            VENUEMAP[venue] = int(data["id"])
            logging.debug(f"VENUEMAP after lookup {venue}: {VENUEMAP}")

    try:
        return int(VENUEMAP[venue])
    except KeyError:
        raise ValueError(f"lookup venue {venue} failed") from None


def get_orgid(organiser: str = None, api_url: str = None, headers: dict = None) -> int:
    """Lookup or read cache of organiser id from organiser.

    Args:
        organiser: Organiser slugname
        api_url: The URL for the wordpress events organisers API
        headers: Requests object additional headers to send

    Returns:
        integer ID of the organiser
    """
    organiser = organiser or DEFAULT_ORGANISER
    api_url = api_url or f"{WORDPRESS_SERVER}{EVENT_API_BASE}/organizers?hide_empty=0"

    try:
        return int(ORGMAP[organiser])
    except KeyError:
        if not ORGMAP:
            console.print("Orgmap is empty, try to populate it")
            response = requests.get(f"{api_url}", timeout=10)
            data = response.json()
            for org in data["organizers"]:
                ORGMAP[org["slug"]] = org["id"]
            logging.debug(f"ORGMAP after populate: {ORGMAP}")

        # we need to use a different lookup to the organiser API by-slug
        if organiser not in ORGMAP:
            console.print(f"Lookup organiser {organiser}")
            slug_api_url = api_url.replace("?", f"/by-slug/{organiser}?")
            response = requests.get(f"{slug_api_url}", timeout=10)
            data = response.json()
            if not data:
                raise ValueError(f"lookup organiser {organiser} failed") from None
            ORGMAP[organiser] = int(data["id"])
            logging.debug(f"ORGMAP after lookup {organiser}: {ORGMAP}")

    try:
        return int(ORGMAP[organiser])
    except KeyError:
        raise ValueError(f"lookup organiser {organiser} failed") from None


def get_tagid(tag: str, api_url: str = None, headers: dict = None) -> int:
    """Lookup or read cache of tag id for tag.

    Args:
        tag: Tag slug
        api_url: The URL for the wordpress tags API
        headers: Requests object additional headers to send

    Returns:
        integer ID of the tag
    """
    api_url = api_url or f"{WORDPRESS_SERVER}/wp-json/wp/v2/tags?hide_empty=0"

    try:
        # fast path - already cached
        return int(TAGMAP[tag])
    except KeyError:
        if not TAGMAP:
            console.print("Tagmap is empty, try to populate it")
            page = 1
            while page < MAXPAGES:
                response = requests.get(f"{api_url}&per_page=50&page={page}", timeout=10)
                data = response.json()
                if not data:
                    break
                for tagdata in data:
                    TAGMAP[tagdata["slug"]] = int(tagdata["id"])
                page += 1
            logging.debug(f"TAGMAP after lookup: {TAGMAP}")

        if tag not in TAGMAP:
            console.print(f"Lookup tag {tag}")
            response = requests.get(f"{api_url}&slug={tag}", timeout=10)
            data = response.json()
            if not data:
                raise ValueError(f"lookup tag {tag} failed") from None
            TAGMAP[tag] = int(data[0]["id"])
            logging.debug(f"TAGMAP after lookup {tag}: {TAGMAP}")
    try:
        return int(TAGMAP[tag])
    except KeyError:
        raise ValueError(f"lookup tag {tag} failed") from None


def get_catid(cat: str, api_url: str = None, headers: dict = None) -> int:
    """Lookup or read cache of cat id for category.

    Args:
        cat: Category name
        api_url: The URL for the wordpress events category API
        headers: Requests object additional headers to send

    Returns:
        integer ID of the category
    """
    api_url = api_url or f"{WORDPRESS_SERVER}{EVENT_API_BASE}/categories?hide_empty=0"

    try:
        return int(CATMAP[cat])
    except KeyError:
        if not CATMAP:
            console.print("Catmap is empty, try to populate it")
            page = 1
            while page < MAXPAGES:
                response = requests.get(f"{api_url}&per_page=50&page={page}", timeout=10)
                data = response.json()
                if not data or not data["categories"]:
                    break
                for catdata in data["categories"]:
                    CATMAP[catdata["slug"]] = int(catdata["id"])
                if page == data["total_pages"]:
                    break
                page += 1
            logging.debug(f"CATMAP after lookup: {CATMAP}")

        if cat not in CATMAP:
            console.print(f"Lookup category {cat}")
            page = 1
            while page < MAXPAGES:
                # you cannot lookup by slug=cat, Events API returns all
                # so we use search and filter that to find the category
                # using ?slug=[{cat}]&hide_empty=false might also work
                response = requests.get(f"{api_url}&search={cat}", timeout=10)
                data = response.json()
                if not data or not data["categories"]:
                    break
                for catdata in data["categories"]:
                    if catdata["slug"] == cat:
                        CATMAP[cat] = int(catdata["id"])
                        break
                if page == data["total_pages"]:
                    break
                page += 1
            logging.debug(f"CATMAP after lookup {cat}: {CATMAP}")

    try:
        return int(CATMAP[cat])
    except KeyError:
        raise ValueError(f"lookup cat {cat} failed") from None


def events_by_day(
    day: str,
    api_url: str = None,
    headers: dict = None,
    startdate: str = None,
    weekcount: int = 52,
    dryrun: bool = False,
    update: bool = False,
    limit: list[str] = None,
    delay: int = 1,
) -> None:
    """Create a recurring events for a day.

    Args:
        day: The day name to process
        api_url: The URL for the wordpress event API
        headers: Requests object additional headers to send
        startdate: ISO formatted date to start from
        weekcount: The number of weeks to work forward through
        dryrun: Dry run create or not
        update: Overwrite existing event?
        limit: List of short event names (the index in events config) to limit to
        delay: Seconds to pause between each day to process to help prevent server overload
    """
    # Maps 'Saturday' -> 5 (0-indexed in Pendulum 3 WeekDay Enum)
    daynum = pendulum.WeekDay[day.upper()].value
    logging.debug(f"Day: {day} maps to {daynum}")
    api_url = api_url or f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events"
    headers = headers or wordpress_header
    limit = limit or []

    nextweekdate = get_next_week_by_day(startdate=startdate, day=daynum)
    dates_for_day = get_dates_for_n_weeks(startdate=nextweekdate, weekcount=weekcount)
    logging.debug(f"dates for {day}: {dates_for_day}")

    # find the events which are on this day and ignore disabled ones
    filtered_events = {k: v for k, v in events.items() if daynum in v["days"] and (not v.get("disabled", False))}

    for date in dates_for_day:
        # gather some useful data about the date
        date_info = decode_date(date=date)

        for event_id, event in filtered_events.items():
            if limit and event_id not in limit:
                continue
            # for this date, only if the week matches the date's week number
            # if weeks is not present or Null, then it is every week
            if event.get("weeks", False) and date_info["week_num"] not in event["weeks"]:
                continue
            # if its a month that we should skip, skip it
            if event.get("skipmonths", []) and int(date_info["monthnum"]) in event.get("skipmonths", []):
                continue
            edata = format_event(
                title=event["title"],
                description=event["desc"],
                excerpt=event.get("excerpt", event["desc"]),
                date=date,
                date_info=date_info,
                starttime=event["starttime"],
                endtime=event["endtime"],
                tags=event.get("tags", []),
                categories=event.get("categories", []),
                image=event.get("image", None),
                venue=event.get("venue", None),
            )
            create_wordpress_event(data=edata, api_url=api_url, headers=headers, dryrun=dryrun, update=update)

        time.sleep(delay)


def validate_days(value: list[str]) -> list[str]:
    """Split comma-separated days and validate them.

    Args:
        value: Comma seaprated listed of days
    """
    # Your existing logic using Pendulum 3
    DAYS_OF_WEEK = [day.name.capitalize() for day in pendulum.WeekDay]
    items = [item.strip() for item in value.split(",")]
    for item in items:
        if item not in DAYS_OF_WEEK:
            # Typer-specific error reporting
            raise typer.BadParameter(f"'{item}' is not a valid day. Valid choices are: {', '.join(DAYS_OF_WEEK)}")
    return items


def break_limit(value: str) -> list[str]:
    """Split comma-separated limit items.

    Args:
        value: Comma seaprated listed of limit flags
    """
    if not value:
        return []
    items = [item.strip() for item in value.split(",")]
    for item in items:
        if item not in configdata["events"]:
            raise typer.BadParameter(
                f"'{item}' is not a event key. Valid choices are: {', '.join(configdata['events'].keys())}"
            )

    return items


@cli.command()
def main(
    days: Annotated[
        str,
        typer.Option("--days", callback=validate_days, help="Comma-separated list of days (e.g., Monday,Saturday)"),
    ],
    limit: Annotated[
        str,
        typer.Option(callback=break_limit, help="Comma-separated list of keys from events file to limit to"),
    ] = None,
    weeks: Annotated[int, typer.Option(min=1, max=52)] = 12,
    startdate: Annotated[str, typer.Option()] = pendulum.now().to_date_string(),
    update: Annotated[bool, typer.Option(help="Update existing events if found")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "--debug")] = False,
    dryrun: Annotated[bool, typer.Option(help="Do not actually create/update")] = False,
) -> int:
    """The main function of the code."""
    setup_logging(verbose)
    cache_events(startdate=startdate, weekcount=weeks)
    for day in days:
        events_by_day(
            api_url=f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events",
            headers=wordpress_header,
            startdate=startdate,
            weekcount=weeks,
            dryrun=dryrun,
            update=update,
            limit=limit,
            day=day,
        )
    return 0


if __name__ == "__main__":
    sys.exit(cli())
