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
import sys
import time

import pendulum
import requests

WORDPRESS_USER = "stmaryos"
WORDPRESS_PASSWORD = "QETF Ic1E pp4F pnIw vXL3 5ZS9"
WORDPRESS_CREDS = WORDPRESS_USER + ":" + WORDPRESS_PASSWORD
wordpress_token = base64.b64encode(WORDPRESS_CREDS.encode())
wordpress_header = {"Authorization": "Basic " + wordpress_token.decode("utf-8")}

WORDPRESS_SERVER = "https://stmaryos.sthompson.org.uk/wp-json/tribe/events/v1/events"
# WORDPRESS_SERVER = "https://stmaryos.sthompson.org.uk/wp-json/wp/v2/tribe_events"

daymap = {"01": "st", "21": "st", "31": "st", "02": "nd", "22": "nd", "03": "rd", "23": "rd"}  # codespell:ignore nd
summer = {8}

catmap = {"service": 25, "communion": 26, "evensong": 27, "family": 28, "choirrehearsal": 30, "choralevensong": 31}
tagmap = {
    "worship": 14,
    "service": 16,
    "morning": 17,
    "evening": 18,
    "afternoon": 19,
    "communion": 20,
    "evensong": 21,
    "family": 22,
    "choirrehearsal": 29,
    "choralevensong": 32,
}
orgmap = {"stmarys": 278}
venuemap = {"church": 282, "churchhall": 289}


def read_wordpress_events(api_url=WORDPRESS_SERVER):
    """Read the current events from wordpress."""
    response = requests.get(api_url, timeout=10)
    response_json = response.json()
    print(response_json)


def create_wordpress_event(data, api_url=None, headers=None, docreate=False):
    """Create a workpress event."""
    if api_url is None:
        api_url = WORDPRESS_SERVER
    if headers is None:
        headers = wordpress_header
    if docreate:
        response = requests.post(url=api_url, data=data, headers=headers, timeout=10)
        response_json = response.json()
        print(response_json)
    else:
        print(f"URL: {api_url}")
        print(data)


def create_sundays(api_url=None, headers=None, startdate=None, weekcount=52, docreate=False, delay=1):
    """Create Sunday recurring events."""
    if api_url is None:
        api_url = WORDPRESS_SERVER
    if headers is None:
        headers = wordpress_header
    if startdate is None:
        nextweekdate = pendulum.now().next(pendulum.SUNDAY).strftime("%Y-%m-%d")
    else:
        nextweekdate = pendulum.parse(startdate).next(pendulum.SUNDAY).strftime("%Y-%m-%d")
    weekdates = [nextweekdate]

    for i in range(1, weekcount):
        weekdates.append(
            (datetime.datetime.strptime(nextweekdate, "%Y-%m-%d") + datetime.timedelta(days=7 * i)).strftime("%Y-%m-%d")
        )

    for day in weekdates:
        daystr = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%A")
        datenum = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%d")
        suffixstr = daymap.get(datenum, "th")
        datestr = int(datenum)
        monthstr = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%B")
        monthnum = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%m")
        yearstr = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%Y")
        cal = calendar.monthcalendar(int(yearstr), int(monthnum))
        first_week = cal[0]
        second_week = cal[1]
        third_week = cal[2]

        if first_week[calendar.SUNDAY]:
            second_day_month = second_week[calendar.SUNDAY]
        else:
            second_day_month = third_week[calendar.SUNDAY]

        if first_week[calendar.SUNDAY]:
            first_day_month = first_week[calendar.SUNDAY]
        else:
            first_day_month = second_week[calendar.SUNDAY]

        data = {
            "title": f"{daystr} {datestr}{suffixstr} {monthstr} {yearstr}: Holy Communion from the Book of Common \
                      Worship (morning)",
            "description": f"<p>{daystr} morning Holy Communion Service</p>",
            "excerpt": f"<p>{daystr} morning Holy Communion Service</p>",
            "start_date": f"{day} 10:00:00",
            "end_date": f"{day} 11:15:00",
            "venue": venuemap["church"],
            "organizer": orgmap["stmarys"],
            "status": "publish",
            "show_map": True,
            "show_map_link": True,
            "tags": [tagmap["communion"]],
            "categories": [catmap["communion"]],
        }
        create_wordpress_event(data, api_url=api_url, headers=headers, docreate=docreate)

        service = "Evensong"
        tags = [tagmap["evensong"]]
        categories = [catmap["evensong"]]
        # second Sunday of the month unless it is August
        if int(second_day_month) == int(datenum) and int(monthnum) not in summer:
            service = "Choral Evensong"
            tags = [tagmap["choralevensong"]]
            categories = [catmap["choralevensong"]]

        data = {
            "title": f"{daystr} {datestr}{suffixstr} {monthstr} {yearstr}: A service of {service} (evening)",
            "description": f"<p>{daystr} Evening service of {service}</p>",
            "excerpt": f"<p>{daystr} Evening service of {service}</p>",
            "start_date": f"{day} 18:30:00",
            "end_date": f"{day} 19:45:00",
            "venue": venuemap["church"],
            "organizer": orgmap["stmarys"],
            "status": "publish",
            "show_map": True,
            "show_map_link": True,
            "tags": tags,
            "categories": categories,
        }
        create_wordpress_event(data, api_url=api_url, headers=headers, docreate=docreate)

        # on the first Sunday of the month, unless it is August
        if int(first_day_month) == int(datenum) and int(monthnum) not in summer:
            data = {
                "title": f"{daystr} {datestr}{suffixstr} {monthstr} {yearstr}: 4 O'clock Church - Family Service \
                           (afternoon)",
                "description": "<p>A family service with arts and craft activities.</p>",
                "excerpt": "<p>A family service with arts and craft activities.</p>",
                "start_date": f"{day} 16:00:00",
                "end_date": f"{day} 17:00:00",
                "venue": venuemap["church"],
                "organizer": orgmap["stmarys"],
                "status": "publish",
                "show_map": True,
                "show_map_link": True,
                "tags": [tagmap["family"]],
                "categories": [catmap["family"]],
            }
            create_wordpress_event(data, api_url=api_url, headers=headers, docreate=docreate)
        time.sleep(delay)


def create_choir(api_url=None, headers=None, startdate=None, weekcount=52, docreate=False, delay=1):
    """Create Choir rehearsal events."""
    if api_url is None:
        api_url = WORDPRESS_SERVER
    if headers is None:
        headers = wordpress_header
    if startdate is None:
        nextweekdate = pendulum.now().next(pendulum.FRIDAY).strftime("%Y-%m-%d")
    else:
        nextweekdate = pendulum.parse(startdate).next(pendulum.FRIDAY).strftime("%Y-%m-%d")
    weekdates = [nextweekdate]

    for i in range(1, weekcount):
        weekdates.append(
            (datetime.datetime.strptime(nextweekdate, "%Y-%m-%d") + datetime.timedelta(days=7 * i)).strftime("%Y-%m-%d")
        )

    for day in weekdates:
        daystr = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%A")
        datenum = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%d")
        suffixstr = daymap.get(datenum, "th")
        datestr = int(datenum)
        monthstr = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%B")
        monthnum = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%m")
        yearstr = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%Y")
        # cal = calendar.monthcalendar(int(yearstr), int(monthnum))
        # first_week = cal[0]
        # second_week = cal[1]
        # third_week = cal[2]

        # if first_week[calendar.FRIDAY]:
        #     second_day_month = second_week[calendar.FRIDAY]
        # else:
        #     second_day_month = third_week[calendar.FRIDAY]

        # if first_week[calendar.FRIDAY]:
        #     first_day_month = first_week[calendar.FRIDAY]
        # else:
        #     first_day_month = second_week[calendar.FRIDAY]

        # choir is not in August
        if int(monthnum) not in summer:
            data = {
                "title": f"{daystr} {datestr}{suffixstr} {monthstr} {yearstr}: Junior Choir Rehearsal",
                "description": f"<p>{daystr} Junior Choir Rehearsal</p>\
                                    <p>Our choir normally rehearses on a Friday evening, the Junior Choir start \
                                    rehearsal earlier than the Adult choir and are joined by the Adult Choir.</p>\
                                    <p>Music plays an important part in the life of St Mary's Church, information \
                                    on <a href='/music-at-st-marys/'>joining the choir</a> is available.</p>",
                "excerpt": f"<p>{daystr} Junior Choir Rehearsal</p>",
                "start_date": f"{day} 19:00:00",
                "end_date": f"{day} 20:30:00",
                "venue": venuemap["church"],
                "organizer": orgmap["stmarys"],
                "status": "publish",
                "show_map": True,
                "show_map_link": True,
                "tags": [tagmap["choirrehearsal"]],
                "categories": [catmap["choirrehearsal"]],
            }
            create_wordpress_event(data, api_url=api_url, headers=headers, docreate=docreate)

            data = {
                "title": f"{daystr} {datestr}{suffixstr} {monthstr} {yearstr}: Adult Choir Rehearsal",
                "description": f"<p>{daystr} Adult Choir Rehearsal</p>\
                                    <p>Our choir normally rehearses on a Friday evening, the Junior Choir start \
                                    rehearsal earlier than the Adult choir and are joined by the Adult Choir.</p>\
                                    <p>Music plays an important part in the life of St Mary's Church, information \
                                    on <a href='/music-at-st-marys/'>joining the choir</a> is available.</p>",
                "excerpt": f"<p>{daystr} Adult Choir Rehearsal</p>",
                "start_date": f"{day} 19:30:00",
                "end_date": f"{day} 21:00:00",
                "venue": venuemap["church"],
                "organizer": orgmap["stmarys"],
                "status": "publish",
                "show_map": True,
                "show_map_link": True,
                "tags": [tagmap["choirrehearsal"]],
                "categories": [catmap["choirrehearsal"]],
            }
            create_wordpress_event(data, api_url=api_url, headers=headers, docreate=docreate)
        time.sleep(delay)


def main():
    """The main function of the code."""
    parser = argparse.ArgumentParser(description="Create multiple WP Events Calendar events")
    parser.add_argument("--sunday", help="Create Sunday worship", action="store_true")
    # parser.add_argument('--thursday', help='Create Thursday events', action='store_true')
    parser.add_argument("--thursday", help=argparse.SUPPRESS, action="store_true")
    parser.add_argument("--choir", help="Create choir rehearsals", action="store_true")
    parser.add_argument("--debug", help="Do not create the actual event", action="store_false")
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
            docreate=args.debug,
        )
    if args.friday:
        create_choir(
            api_url=WORDPRESS_SERVER,
            headers=wordpress_header,
            startdate=args.startdate,
            weekcount=args.weeks,
            docreate=args.debug,
        )
    # read_wordpress_posts()


if __name__ == "__main__":
    main()
    sys.exit(0)
