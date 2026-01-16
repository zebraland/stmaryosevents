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

load_dotenv()

WORDPRESS_USER = os.getenv("WORDPRESS_USER")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
WORDPRESS_CREDS = WORDPRESS_USER + ":" + WORDPRESS_PASSWORD
wordpress_token = base64.b64encode(WORDPRESS_CREDS.encode())
wordpress_header = {"Authorization": "Basic " + wordpress_token.decode("utf-8")}

WORDPRESS_SERVER = os.getenv("WORDPRESS_SERVER")
CONFIG_FILE = os.getenv("CONFIG_FILE")
EVENT_API = os.getenv("EVENT_API")

daymap = {"01": "st", "21": "st", "31": "st", "02": "nd", "22": "nd", "03": "rd", "23": "rd"}  # codespell:ignore nd
summer = {8}

with open(CONFIG_FILE, encoding="utf-8") as configfile:
    # Use safe_load to prevent execution of arbitrary code
    configdata = yaml.safe_load(configfile)

CATMAP = {}
TAGMAP = {}
ORGMAP = {}
VENUEMAP = {}
events = configdata["events"]


def read_wordpress_events(api_url=WORDPRESS_SERVER):
    """Read the current events from wordpress.

    Args:
        api_url (str): The URL for the wordpress event API
    """
    response = requests.get(api_url, timeout=10)
    response_json = response.json()
    print(response_json)


def create_wordpress_event(data, api_url=None, headers=None, dryrun=False):
    """Create a wordpress event.

    Args:
        data (json): The Payload formatted data for the event
        api_url (str): The URL for the wordpress event API
        headers (dict): Requests object additional headers to send
        dryrun (bool): Dry run create or not
    """
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API}"
    if headers is None:
        headers = wordpress_header
    if dryrun:
        response = requests.post(url=api_url, json=data, headers=headers, timeout=10)
        response_json = response.json()
        # print(response_json)
        print(f"Event Title: {response_json['title']}")
        print(f"Event URL: {response_json['url']}")
    else:
        print(f"URL: {api_url}")
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


def format_title(date_info, title):
    """Format the title of an event.

    Args:
        date_info (dict): Dict from decode_date with information about the date
        title (str): The title text to include
    """
    return (
        f"{title} "
        f"[{date_info['daystr']} {date_info['datenum'].lstrip('0')}{date_info['suffixstr']} "
        f"{date_info['monthstr']} {date_info['yearstr']}]"
    )


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
    print(data["tags"])

    return data


def get_venueid(venue=None, api_url=None, headers=None):
    """Lookup or read cache of venue id for the venue.

    Args:
        venue (str): Venue slug name
        api_url (str): The URL for the wordpress events venues API
        headers (dict): Requests object additional headers to send
    """
    if venue is None:
        venue = "stmarys"

    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}/wp-json/tribe/events/v1/venues?slug={venue}&hide_empty=0"

    if venue not in VENUEMAP:
        print(f"Lookup venue {venue}")
        response = requests.get(api_url, timeout=10)
        data = response.json()
        if not data:
            print(f"lookup venue {venue} failed")
            raise Exception
        VENUEMAP[venue] = int(data["venues"][0]["id"])
    return int(VENUEMAP[venue])


def get_orgid(organiser=None, api_url=None, headers=None):
    """Lookup or read cache of cat id for category.

    Args:
        organiser (str): Organiser slugname
        api_url (str): The URL for the wordpress events organisers API
        headers (dict): Requests object additional headers to send
    """
    if organiser is None:
        organiser = "stmarys"

    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}/wp-json/tribe/events/v1/organizers?slug={organiser}&hide_empty=0"

    if organiser not in ORGMAP:
        print(f"Lookup organiser {organiser}")
        response = requests.get(api_url, timeout=10)
        data = response.json()
        if not data:
            print(f"lookup organiser {organiser} failed")
            raise Exception
        ORGMAP[organiser] = int(data["organizers"][0]["id"])
    return int(ORGMAP[organiser])


def get_tagid(tag, api_url=None, headers=None):
    """Lookup or read cache of cat id for category.

    Args:
        tag (str): Tag slug
        api_url (str): The URL for the wordpress tags API
        headers (dict): Requests object additional headers to send
    """
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}/wp-json/wp/v2/tags?slug={tag}&hide_empty=0"

    if tag not in TAGMAP:
        print(f"Lookup tag {tag}")
        response = requests.get(api_url, timeout=10)
        data = response.json()
        if not data:
            print(f"lookup tag {tag} failed")
            raise Exception
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
        api_url = f"{WORDPRESS_SERVER}/wp-json/tribe/events/v1/categories?slug={cat}&hide_empty=0"

    if cat not in CATMAP:
        print(f"Lookup category {cat}")
        response = requests.get(api_url, timeout=10)
        data = response.json()
        if not data:
            print(f"lookup cat {cat} failed")
            raise Exception
        print(data)
        CATMAP[cat] = int(data["categories"][0]["id"])
    return int(CATMAP[cat])


def events_by_day(day, api_url=None, headers=None, startdate=None, weekcount=52, dryrun=False, delay=1):
    """Create a recurring events for a day.

    Args:
        day (str): The day name to process
        api_url (str): The URL for the wordpress event API
        headers (dict): Requests object additional headers to send
        startdate (str): ISO formatted date to start from
        weekcount (int): The number of weeks to work forward through
        dryrun (bool): Dry run create or not
        delay (int): Seconds to pause between each day to process to help prevent server overload
    """
    daynum = list(calendar.day_name).index(day)
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API}"
    if headers is None:
        headers = wordpress_header
    nextweekdate = get_next_week_by_day(startdate=startdate, day=daynum)
    dates_for_day = get_dates_for_n_weeks(startdate=nextweekdate, weekcount=weekcount)

    # find the events which are on this day and ignore disabled ones
    filtered_events = {k: v for k, v in events.items() if daynum in v["days"] and (not v.get("disabled", False))}

    for date in dates_for_day:
        # gather some useful data about the date
        date_info = decode_date(date=date)

        for _id, event in filtered_events.items():
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
            create_wordpress_event(data=edata, api_url=api_url, headers=headers, dryrun=dryrun)

        time.sleep(delay)


def create_choir(api_url=None, headers=None, startdate=None, weekcount=52, dryrun=False, delay=1):
    """Create Choir rehearsal events.

    api_url (str): The URL for the wordpress event API
    headers (dict): Requests object additional headers to send
    startdate (str): ISO formatted date to start from
    weekcount (int): The number of weeks to work forward through
    dryrun (bool): Dry run create or not
    delay (int): Seconds to pause between each day to process to help prevent server overload
    """
    friday = calendar.FRIDAY
    if api_url is None:
        api_url = f"{WORDPRESS_SERVER}{EVENT_API}"
    if headers is None:
        headers = wordpress_header
    nextweekdate = get_next_week_by_day(startdate=startdate, day=friday)
    dates_for_day = get_dates_for_n_weeks(startdate=nextweekdate, weekcount=weekcount)

    choir = {
        "junior": {
            "title": "Junior",
            "start": "19:00:00",
            "end": "20:30:00",
            "enabled": False,
        },
        "adult": {
            "title": "Adult",
            "start": "19:30:00",
            "end": "21:00:00",
            "enabled": True,
        },
    }

    for date in dates_for_day:
        date_info = decode_date(date=date)

        # choir is not in August
        if int(date_info["monthnum"]) not in summer:
            for _choir, info in choir.items():
                if not info["enabled"]:
                    continue
                desc = (
                    (
                        f"<h1>{info['title']} Choir Rehearsal</h1>"
                        "<p>Our choir normally rehearses on a Friday evening, the Junior Choir start "
                        "rehearsal earlier than the Adult choir and are joined by the Adult Choir.</p>"
                        "<p>Music plays an important part in the life of St Mary's Church, information "
                        "on <a href='/music-at-st-marys/'>joining the choir</a> is available.</p>"
                    ),
                )
                data = format_event(
                    title=f"{info['title']} Choir Rehearsal",
                    description=desc,
                    excerpt=f"{info['title']} Choir Rehearsal",
                    date=date,
                    date_info=date_info,
                    starttime=info["start"],
                    endtime=info["end"],
                    tags=["choirrehearsal"],
                    categories=["choirrehearsal"],
                    image=962,
                )
                create_wordpress_event(data, api_url=api_url, headers=headers, dryrun=dryrun)

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
    parser.add_argument("--dryrun", help="Do not create the actual event", action="store_false")
    parser.add_argument(
        "--weeks", help="Number of weeks to create", type=int, metavar="{1-52}", choices=range(1, 53), default=12
    )
    parser.add_argument("--startdate", help="Date after which to start events: yyyy-mm-dd", type=str, default=None)
    args = parser.parse_args()

    for day in args.days:
        events_by_day(
            api_url=f"{WORDPRESS_SERVER}{EVENT_API}",
            headers=wordpress_header,
            startdate=args.startdate,
            weekcount=args.weeks,
            dryrun=args.dryrun,
            day=day,
        )

    print(args.days)
    # read_wordpress_events()


if __name__ == "__main__":
    main()
    sys.exit(0)
