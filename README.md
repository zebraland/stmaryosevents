# Wordpress events

This tool is indented to create "recurring" events using the Events Calendar plugin for Wordpress. The events
are not really recurring but multiple instances of the event.

## Running

```shell
./create_recurring.py --startdate 2026-01-01 --enddate 2026-02-28 --days Tuesday --update --dryrun
```

`--startdate` ISO formatted date to start creating events

`--enddate` ISO formatted date to stop creating events

`--weeks` Alternative to `--enddate` to create number of weeks

`--days` Comma separated list of days to create events for, e.g. to limit to Tueday and Friday `--days Tuesday,Friday`

`--limit` Comma separated list of events to limit to, this is the key from the config file, e.g.
`--limit taize,evensong`

`--dryrun` Show what would happen without actually creating

`--debug` Show extensive debugging information

## Setup

Ensure that the required packages are installed for the Python script:

Create a virtual env:

```shell
python -m venv ~/foobar
source ~/foobar/bin/activate
```

Remember to activate the virtualenv each time you are using it.

### Using pip

Install packages and dependencies in editable mode:

```shell
pip install -e .
```

If using pip and developing, you need to manually install each item from `dependency-groups` to make the tools
available.

You can now use the script with:

```shell
create_recurring
```

### Using UV

```shell
pip install uv
uv sync --editable --active
uv sync --group lint --editable --active
```

Note that in this case, uv has not installed the script:

```shell
./create_recurring.py
```

### Configuration

Configure the `.env` file (see `.env.example` for syntax) with the Wordpress URL, username and password to use to
connect to the Wordpress API.

The password to use should be configured in the Wordpress UI as an application and hence an Application Password.

To create an Application Password, navigate to the user in the Wordpress Admin, at the bottom of the edit user
settings is "Application Passwords".

Enter the application name, for example "Event creator" and click "Add Application Password", ensure that you
copy the password and place that in the `.env` configuration file.

You also need to configure the event types in the `config.yml` file:

Example yaml file:

```yaml
---
events:
  sundaymoring:
    days:
      - Sunday
    weeks:
    disabled: False
    desc: "<p>Parish Holy Communion Service from the Book of Common Worship.</p>"
    title: "Parish Communion (morning)"
    starttime: "10:00:00"
    endtime: "11:15:00"
    tags:
      - communion
      - bcp
      - service
      - morning
      - worship
      - hymns
      - music
      - singing
    categories:
      - communion
      - worship
    image: 963
```

`days` is a list of days the event occurs on
`weeks` when empty or missing means every day occurrence in the month, by setting to 1 and 3, that would mean
repeat on the first and third occurrence day in the month. When used something like:

```yaml
events:
  sundaymoring:
    days:
      - Sunday
    weeks:
      - 1
      - 3
    skipmonths:
      - January
```

This would mean thr first and fourth Sunday in the month.

Set `disabled: True` if you want the event to be ignored, for example if something is temporarily not happening.

`desc` is the long HTML formatted text that appears in the event page.

`title` is the name of the event that appears on the pages, it will have the date of the event appended to it.

`excerpt` is optional text that is displayed when the short form of the event is show, for example when the event
list is displayed. By default `desc` is used if missing, set this if you have long text etc in `desc`

`starttime` is the time the events starts of the from HH:MM:SS

`endtime` is the time the events ends of the from HH:MM:SS

`tags` and `categories` are the slug names for any tags and categories to be assigned to the event. Note that these
must have been pre-created in the Events Calendar via the Wordpress UI.

`image` is the media ID of the featured image to use, typically this should be something like 16x4.5 aspect ratio
and is intended to be a banner bar that appears at the top of the event page and to the side when in listing mode.

As the code uses python `dotenv`, anything set in an environment variable will override the content of the `.env`
file, for example to use a testing `config.yml` you could do:

```shell
CONFIG_FILE=test.yml ./create_recurring.py --sunday --weeks 5 --startdate 2026-01-01 --dryrun
```
