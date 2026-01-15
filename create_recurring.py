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
import json
import os
import sys
import time

import pendulum
import requests
from dotenv import load_dotenv

load_dotenv()

WORDPRESS_USER = os.getenv("WORDPRESS_USER")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
WORDPRESS_CREDS = WORDPRESS_USER + ":" + WORDPRESS_PASSWORD
wordpress_token = base64.b64encode(WORDPRESS_CREDS.encode())
wordpress_header = {"Authorization": "Basic " + wordpress_token.decode("utf-8")}

WORDPRESS_SERVER = os.getenv("WORDPRESS_SERVER")

daymap = {"01": "st", "21": "st", "31": "st", "02": "nd", "22": "nd", "03": "rd", "23": "rd"}  # codespell:ignore nd
summer = {8}

catmap = json.loads(os.getenv("CATMAP"))
tagmap = json.loads(os.getenv("TAGMAP"))
orgmap = json.loads(os.getenv("ORGMAP"))
venuemap = json.loads(os.getenv("VENUEMAP"))


def read_wordpress_events(api_url=WORDPRESS_SERVER):
    """Read the current events from wordpress.

    api_url (str): The URL for the wordpress event API
    """
    response = requests.get(api_url, timeout=10)
    response_json = response.json()
    print(response_json)


def create_wordpress_event(data, api_url=None, headers=None, dryrun=False):
    """Create a wordpress event.

    data (json): The Payload formatted data for the event
    api_url (str): The URL for the wordpress event API
    headers (dict): Requests object additional headers to send
    dryrun (bool): Dry run create or not
    """
    if api_url is None:
        api_url = WORDPRESS_SERVER
    if headers is None:
        headers = wordpress_header
    if dryrun:
        response = requests.post(url=api_url, data=data, headers=headers, timeout=10)
        response_json = response.json()
        print(response_json)
    else:
        print(f"URL: {api_url}")
        print(data)


def get_next_week_by_day(startdate, day):
    """Get the date of the next week by day.

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

    title (str): The title for the event
    description (str): HTML formatted string for the description
    excerpt (str): HTML formatted string for the except - usually a shorter version of description
    date (str): ISO formatted date for event
    date_info (dict): Representation of the date
    starttime (str): Start time of the event of format HH:MM:SS
    endtime (str): End time of the event of format HH:MM:SS
    tags (list): tags to apply to event in string format
    categories (list): categories to apply to event in string format
    venue (str): Index from venuemap of the venue
    organiser (str): Index from orgmap of the organiser
    image (int): The featured image reference id
    """
    if not tags:
        tags = []
    if not categories:
        categories = []
    if not venue:
        venue = venuemap["church"]
    if not organiser:
        organiser = orgmap["stmarys"]

    data = {
        "title": format_title(date_info=date_info, title=title),
        "description": description,
        "excerpt": excerpt,
        "start_date": f"{date} {starttime}",
        "end_date": f"{date} {endtime}",
        "venue": venue,
        "organizer": organiser,
        "status": "publish",
        "show_map": True,
        "show_map_link": True,
        "tags": [],
        "categories": [],
    }

    for tag in tags:
        data["tags"].append(tagmap[tag])

    for cat in categories:
        data["categories"].append(catmap[cat])

    if image:
        data["image"] = image

    return data


def create_sundays(api_url=None, headers=None, startdate=None, weekcount=52, dryrun=False, delay=1):
    """Create Sunday recurring events.

    api_url (str): The URL for the wordpress event API
    headers (dict): Requests object additional headers to send
    startdate (str): ISO formatted date to start from
    weekcount (int): The number of weeks to work forward through
    dryrun (bool): Dry run create or not
    delay (int): Seconds to pause between each day to process to help prevent server overload
    """
    sunday = calendar.SUNDAY
    if api_url is None:
        api_url = WORDPRESS_SERVER
    if headers is None:
        headers = wordpress_header
    nextweekdate = get_next_week_by_day(startdate=startdate, day=sunday)
    dates_for_day = get_dates_for_n_weeks(startdate=nextweekdate, weekcount=weekcount)

    for date in dates_for_day:
        date_info = decode_date(date=date)

        desc = f"<p>{date_info['daystr']} morning Holy Communion Service</p>"

        data = format_event(
            title="Holy Communion from the Book of Common Worship (morning)",
            description=desc,
            excerpt=desc,
            date=date,
            date_info=date_info,
            starttime="10:00:00",
            endtime="11:15:00",
            tags=["communion"],
            categories=["communion"],
            image=963,
        )

        create_wordpress_event(data, api_url=api_url, headers=headers, dryrun=dryrun)

        service = "Evensong"
        tags = ["evensong"]
        categories = ["evensong"]
        # second Sunday of the month unless it is August
        if (date_info["week_num"] in {2}) and (int(date_info["monthnum"]) not in summer):
            service = "Choral Evensong"
            tags = ["choralevensong"]
            categories = ["choralevensong"]

        desc = f"<p>{date_info['daystr']} Evening service of {service}</p>"

        data = format_event(
            title=f"A service of {service} (evening)",
            description=desc,
            excerpt=desc,
            date=date,
            date_info=date_info,
            starttime="18:30:00",
            endtime="19:45:00",
            tags=tags,
            categories=categories,
            image=963,
        )
        create_wordpress_event(data, api_url=api_url, headers=headers, dryrun=dryrun)

        # on the first Sunday of the month, unless it is August
        if (date_info["week_num"] in {1}) and (int(date_info["monthnum"]) not in summer):
            desc = (
                "<h1>4 O&#8217;clock Church</h1>"
                '<p><img decoding="async" class="aligncenter wp-image-957 size-full" '
                'src="/wp-content/uploads/2026/01/4oclock-e1768496522387.jpg" alt="" width="1067" height="1453" '
                'srcset="/wp-content/uploads/2026/01/4oclock-e1768496522387.jpg 1067w, '
                "/wp-content/uploads/2026/01/4oclock-e1768496522387-220x300.jpg 220w, "
                "/wp-content/uploads/2026/01/4oclock-e1768496522387-752x1024.jpg 752w, "
                "/wp-content/uploads/2026/01/4oclock-e1768496522387-768x1046.jpg 768w, "
                "/wp-content/uploads/2026/01/4oclock-e1768496522387-1024x1394.jpg 1024w, "
                '/wp-content/uploads/2026/01/4oclock-e1768496522387-793x1080.jpg 793w" sizes="(max-width: 1067px) '
                '100vw, 1067px" /></p>'
                "<p>Our 4 O&#8217;clock Church is one of our family focused groups that takes place on the first "
                "Sunday of the month during school term time. Its lots of fun an features a mix of different themes "
                "with crafts and activities as well as some lovely food and drink!</p>"
            )
            excerpt = "<p>4 O'Clock Church is a family service with different themes, crafts and activities.</p>"

            data = format_event(
                title="4 O'clock Church - Family Service (afternoon)",
                description=desc,
                excerpt=excerpt,
                date=date,
                date_info=date_info,
                starttime="16:00:00",
                endtime="17:00:00",
                tags=["family", "4oclock"],
                categories=["family"],
                image=965,
            )
            create_wordpress_event(data, api_url=api_url, headers=headers, dryrun=dryrun)
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
        api_url = WORDPRESS_SERVER
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


def main():
    """The main function of the code."""
    parser = argparse.ArgumentParser(description="Create multiple WP Events Calendar events")
    parser.add_argument("--sunday", help="Create Sunday worship", action="store_true")
    # parser.add_argument('--thursday', help='Create Thursday events', action='store_true')
    parser.add_argument("--thursday", help=argparse.SUPPRESS, action="store_true")
    parser.add_argument("--friday", help=argparse.SUPPRESS, action="store_true")
    parser.add_argument("--choir", help="Create choir rehearsals", action="store_true")
    parser.add_argument("--dryrun", help="Do not create the actual event", action="store_false")
    parser.add_argument(
        "--weeks", help="Number of weeks to create", type=int, metavar="{1-52}", choices=range(1, 53), default=12
    )
    parser.add_argument("--startdate", help="Date after which to start events: yyyy-mm-dd", type=str, default=None)
    args = parser.parse_args()

    if not (args.sunday or args.thursday or args.friday):
        parser.error("No day specified")

    if args.sunday:
        create_sundays(
            api_url=WORDPRESS_SERVER,
            headers=wordpress_header,
            startdate=args.startdate,
            weekcount=args.weeks,
            dryrun=args.dryrun,
        )
    if args.friday:
        create_choir(
            api_url=WORDPRESS_SERVER,
            headers=wordpress_header,
            startdate=args.startdate,
            weekcount=args.weeks,
            dryrun=args.dryrun,
        )
    # read_wordpress_events()


if __name__ == "__main__":
    main()
    sys.exit(0)
