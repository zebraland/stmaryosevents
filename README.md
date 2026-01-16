# Wordpress events

This tool is indented to create "recurring" events using the Events Calendar plugin for Wordpress. The events
are not really recurring but multiple instances of the event.

## Setup

Ensure that the required packages are installed for the Python script:

```shell
pip install -r requirements.txt
```

Configure the `.env` file (see `.env.example` for syntax) with the Wordpress URL, username and password to use to
connect to the Wordpress API.

The password to use should be configured in the Wordpress UI as an application and hence an Application Password.

To create an Application Password, navigate to the user in the Wordpress Admin, at the bottom of the edit user
settings is "Application Passwords".

Enter the application name, for example "Event creator" and click "Add Application Password", ensure that you
copy the password and place that in the `.env` configuration file.

For the categories, tags, organisers and venues, these should be yaml encoded to map the data into a python dict.

For example create the Organiser in the Wordpress UI, and then go back to edit it, in the URL bar you will see
something like `post.php?post=821`, in this case the "page id" for the Organiser would map to 821.

Example yaml file:

```yaml
---
catmap:
    worship: 22
    communion: 25
    evensong: 23
    family: 24
tagmap:
    worship: 13
    service: 12
    morning: 11
    evening: 7
    family: 9
orgmap:
    stmarys: 821
venuemap:
    church: 822
    churchhall: 824
```

As the code uses python `dotenv`, anything set in an environment variable will override the content of the `.env`
file, for example to use a testing `config.yml` you could do:

```shell
CONFIG_FILE=test.yml ./create_recurring.py --sunday --weeks 5 --startdate 2026-01-01 --dryrun
```
