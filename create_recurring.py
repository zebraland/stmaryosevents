#!/usr/bin/env python3
# Copyright (c) 2026 Simon Thompson
"""Create "recurring" events for a wordpess site with events plugin added.

Events that are created a not recurring (which requires paid plugin), but
will create multiple instances of the event.
"""

import argparse
import base64
import calendar
import datetime
import os
import sys
import time

import pendulum
import requests
import yaml
from dotenv import load_dotenv
from requests.exceptions import HTTPError

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

daymap = {"01": "st", "21": "st", "31": "st", "02": "nd", "22": "nd", "03": "rd", "23": "rd"}  # codespell:ignore nd
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


def cache_events(startdate, weekcount, api_url=None):
    """Read the current events from wordpress.

    Args:
        startdate (str): ISO formatted date to start from
        weekcount (int): Number of weeks to cache
        api_url (str): The URL for the wordpress event API
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
        "per_page": 2,  # Get as many as possible in one go
        "page": page,
    }

    print("Caching existing events")
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


def create_wordpress_event(data, api_url=None, headers=None, dryrun=False, update=False):
    """Create a wordpress event.

    Args:
        data (json): The Payload formatted data for the event
        api_url (str): The URL for the wordpress event API
        headers (dict): Requests object additional headers to send
        dryrun (bool): Dry run create or not
        update (bool): Overwrite existing event?
    """
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events"
    if headers is None:
        headers = wordpress_header

    method = "POST"

    if data["slug"] in EVENTCACHE:
        if not update:
            print(f"Event is present: {data['slug']} - skipping")
            return
        print(f"Update event {data['slug']}")
        method = "PATCH"
        data["id"] = int(EVENTCACHE[data["slug"]]["id"])
        api_url = f"{api_url}/{data['id']}"

    if not dryrun:
        response = requests.request(method=method, url=api_url, json=data, headers=headers, timeout=10)
        response_json = response.json()
        print(f"Event Title: {response_json['title']}")
        print(f"Event URL: {response_json['url']}")
        EVENTCACHE[data["slug"]] = response_json["id"]
    else:
        print(f"URL: {api_url}")
        # EVENTCACHE.add(data["slug"])
        print(data)


def get_next_week_by_day(startdate, day):
    """Get the date of the next week by day.

    Args:
        startdate (str): ISO formatted date to start lookging for the next instance of day
        day (str): The index of the day number (e.g. Sunday = 6)
    """
    if startdate is None:
        nextweekdate = pendulum.now().next(day).strftime("%Y-%m-%d")
    else:
        nextweekdate = pendulum.parse(startdate).next(day).strftime("%Y-%m-%d")
    return nextweekdate


def get_dates_for_n_weeks(startdate, weekcount):
    """Get the date of the day for the next N weeks.

    Args:
        startdate (str): ISO formatted date to start lookging for the next instance of day
        weekcount (int): The number of weeks to look forward to
    """
    # start with the first date
    dates = [startdate]
    for i in range(1, weekcount):
        dates.append(
            (datetime.datetime.strptime(startdate, "%Y-%m-%d") + datetime.timedelta(days=7 * i)).strftime("%Y-%m-%d")
        )
    return dates


def decode_date(date):
    """Decode the date string to something nicer.

    Args:
        date (str): ISO formatted date string
    """
    date_info = {
        "daystr": datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%A"),
        "datenum": datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%d"),
        "monthstr": datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%B"),
        "monthnum": datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%m"),
        "yearstr": datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%Y"),
    }

    # look up e.g. 1"st" or 2"nd", default to 20"th"  # codespell:ignore nd
    date_info["suffixstr"] = daymap.get(date_info["datenum"], "th")
    # lookup the week number for the current date, i.e. first in the month
    date_info["week_num"] = find_date_week(date=date)
    return date_info


def find_date_week(date):
    """Find the week number a date is in.

    Args:
        date(str): ISO formatted date string
    """
    # get the list of weeks which for the month
    weeks = calendar.monthcalendar(
        int(datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%Y")),
        int(datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%m")),
    )

    date_num = int(datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%d"))
    # lookup the day index from the day name for the week
    day_idx = list(calendar.day_name).index(datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%A"))

    # loop over the weeks and if the date is in the index for the day of the week, we know the week number
    for index, week in enumerate(weeks):
        if week[day_idx] == date_num:
            return index + 1

    return None


def format_title(date_info, title, include_date=False):
    """Format the title of an event.

    Args:
        date_info (dict): Dict from decode_date with information about the date
        title (str): The title text to include
        include_date (bool): Include the date in the title?
    """
    if include_date:
        return (
            f"{title} "
            f"[{date_info['daystr']} {date_info['datenum'].lstrip('0')}{date_info['suffixstr']} "
            f"{date_info['monthstr']} {date_info['yearstr']}]"
        )
    return f"{title}"


def build_slug(date_info, title):
    """Build the slug for the event.

    Args:
        date_info (dict): Dict from decode_date with information about the date
        title (str): The title text to include
    """
    slug = f"{date_info['yearstr']}-{date_info['monthnum']}-{date_info['datenum']}-{(title.lower()).replace(' ', '-')}"
    return slug


def format_event(
    title,
    description,
    excerpt,
    date,
    date_info,
    starttime,
    endtime,
    tags=None,
    categories=None,
    venue=None,
    organiser=None,
    image=None,
):
    """Format an event for wordpress events calendar.

    Args:
        title (str): The title for the event
        description (str): HTML formatted string for the description
        excerpt (str): HTML formatted string for the except - usually a shorter version of description
        date (str): ISO formatted date for event
        date_info (dict): Representation of the date
        starttime (str): Start time of the event of format HH:MM:SS
        endtime (str): End time of the event of format HH:MM:SS
        tags (list): tags to apply to event in string format
        categories (list): categories to apply to event in string format
        venue (str): Name of the venue slug
        organiser (str): Name of the organiser slug
        image (int): The featured image reference id
    """
    if not tags:
        tags = []
    if not categories:
        categories = []
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

    return data


def get_venueid(venue=None, api_url=None, headers=None):
    """Lookup or read cache of venue id for the venue.

    Args:
        venue (str): Venue slug name
        api_url (str): The URL for the wordpress events venues API
        headers (dict): Requests object additional headers to send
    """
    if venue is None:
        venue = DEFAULT_VENUE

    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API_BASE}/venues?&hide_empty=0"

    if not VENUEMAP:
        print("Venuemap is empty, try to populate it")
        response = requests.get(f"{api_url}", timeout=10)
        data = response.json()
        for venuedata in data["venues"]:
            VENUEMAP[venuedata["slug"]] = venuedata["id"]

    # we need to use a different lookup to the organiser API by-slug
    if venue not in VENUEMAP:
        print(f"Lookup venue {venue}")
        slug_api_url = api_url.replace("?", f"/by-slug/{venue}?")
        response = requests.get(f"{slug_api_url}", timeout=10)
        data = response.json()
        if not data:
            raise ValueError(f"lookup venue {venue} failed")
        VENUEMAP[venue] = int(data["id"])

    if venue not in VENUEMAP:
        raise ValueError(f"lookup venue {venue} failed")

    return int(VENUEMAP[venue])


def get_orgid(organiser=None, api_url=None, headers=None):
    """Lookup or read cache of organiser id from organiser.

    Args:
        organiser (str): Organiser slugname
        api_url (str): The URL for the wordpress events organisers API
        headers (dict): Requests object additional headers to send
    """
    if organiser is None:
        organiser = DEFAULT_ORGANISER

    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API_BASE}/organizers?hide_empty=0"

    if not ORGMAP:
        print("Orgmap is empty, try to populate it")
        response = requests.get(f"{api_url}", timeout=10)
        data = response.json()
        for org in data["organizers"]:
            ORGMAP[org["slug"]] = org["id"]

    # we need to use a different lookup to the organiser API by-slug
    if organiser not in ORGMAP:
        print(f"Lookup organiser {organiser}")
        slug_api_url = api_url.replace("?", f"/by-slug/{organiser}?")
        response = requests.get(f"{slug_api_url}", timeout=10)
        data = response.json()
        if not data:
            raise ValueError(f"lookup organiser {organiser} failed")
        ORGMAP[organiser] = int(data["id"])

    if organiser not in ORGMAP:
        raise ValueError(f"lookup organiser {organiser} failed")

    return int(ORGMAP[organiser])


def get_tagid(tag, api_url=None, headers=None):
    """Lookup or read cache of tag id for tag.

    Args:
        tag (str): Tag slug
        api_url (str): The URL for the wordpress tags API
        headers (dict): Requests object additional headers to send
    """
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}/wp-json/wp/v2/tags?hide_empty=0"

    if not TAGMAP:
        print("Tagmap is empty, try to populate it")
        page = 1
        while page < MAXPAGES:
            response = requests.get(f"{api_url}&per_page=50&page={page}", timeout=10)
            data = response.json()
            if not data:
                break
            for tagdata in data:
                TAGMAP[tagdata["slug"]] = int(tagdata["id"])
            page += 1

    if tag not in TAGMAP:
        print(f"Lookup tag {tag}")
        response = requests.get(f"{api_url}&slug={tag}", timeout=10)
        data = response.json()
        if not data:
            raise ValueError(f"lookup tag {tag} failed")
        TAGMAP[tag] = int(data[0]["id"])
    return int(TAGMAP[tag])


def get_catid(cat, api_url=None, headers=None):
    """Lookup or read cache of cat id for category.

    Args:
        cat (str): Category name
        api_url (str): The URL for the wordpress events category API
        headers (dict): Requests object additional headers to send
    """
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API_BASE}/categories?hide_empty=0"

    if not CATMAP:
        print("Catmap is empty, try to populate it")
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

    if cat not in CATMAP:
        print(f"Lookup category {cat}")
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

    if cat not in CATMAP:
        raise ValueError(f"lookup cat {cat} failed")
    return int(CATMAP[cat])


def events_by_day(
    day, api_url=None, headers=None, startdate=None, weekcount=52, dryrun=False, update=False, limit=None, delay=1
):
    """Create a recurring events for a day.

    Args:
        day (str): The day name to process
        api_url (str): The URL for the wordpress event API
        headers (dict): Requests object additional headers to send
        startdate (str): ISO formatted date to start from
        weekcount (int): The number of weeks to work forward through
        dryrun (bool): Dry run create or not
        update (bool): Overwrite existing event?
        limit (list): List of short event names (the index in events config) to limit to
        delay (int): Seconds to pause between each day to process to help prevent server overload
    """
    daynum = list(calendar.day_name).index(day)
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events"
    if headers is None:
        headers = wordpress_header
    if limit is None:
        limit = []

    nextweekdate = get_next_week_by_day(startdate=startdate, day=daynum)
    dates_for_day = get_dates_for_n_weeks(startdate=nextweekdate, weekcount=weekcount)

    # find the events which are on this day and ignore disabled ones
    filtered_events = {k: v for k, v in events.items() if daynum in v["days"] and (not v.get("disabled", False))}

    for date in dates_for_day:
        # gather some useful data about the date
        date_info = decode_date(date=date)

        for id, event in filtered_events.items():
            if limit and id not in limit:
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
            )
            create_wordpress_event(data=edata, api_url=api_url, headers=headers, dryrun=dryrun, update=update)

        time.sleep(delay)


def comma_separated_choices(choices):
    """Argparse helper function for comma separated choices.

    Args:
        choices (list): List of valid choices that can be picked
    """

    def check_types(arg):
        # 1. Split the string by commas
        items = [item.strip() for item in arg.split(",")]

        # 2. Validate each item against the allowed choices
        for item in items:
            if item not in choices:
                raise argparse.ArgumentTypeError(f"'{item}' is not a valid choice. Choose from: {', '.join(choices)}")
        return items

    return check_types


def main():
    """The main function of the code."""
    parser = argparse.ArgumentParser(description="Create multiple WP Events Calendar events")
    parser.add_argument(
        "--days",
        type=comma_separated_choices(list(calendar.day_name)),
        help=f"Comma-separated list of days (e.g., {','.join(list(calendar.day_name))})",
        required=True,
    )
    parser.add_argument("--dryrun", help="Do not create the actual event", action="store_true")
    parser.add_argument("--update", help="Update existing events if found", action="store_true")
    parser.add_argument(
        "--weeks", help="Number of weeks to create", type=int, metavar="{1-52}", choices=range(1, 53), default=12
    )
    parser.add_argument(
        "--startdate",
        help="Date after which to start events: yyyy-mm-dd, defaults to today",
        type=str,
        default=pendulum.now().strftime("%Y-%m-%d"),
    )
    parser.add_argument("--limit", help="Comma separated list of event shortnames to limit to", type=str, default="")
    args = parser.parse_args()

    limit = args.limit.split(",") if args.limit else []
    cache_events(startdate=args.startdate, weekcount=args.weeks)
    for day in args.days:
        events_by_day(
            api_url=f"{WORDPRESS_SERVER}{EVENT_API_BASE}/events",
            headers=wordpress_header,
            startdate=args.startdate,
            weekcount=args.weeks,
            dryrun=args.dryrun,
            update=args.update,
            limit=limit,
            day=day,
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
