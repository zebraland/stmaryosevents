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

For the categories, tags, organisers and venues, these should be json encoded dict formatted like a python dict
to map the "human name" to the "page id".

For example create the Organiser in the Wordpress UI, and then go back to edit it, in the URL bar you will see
something like `post.php?post=821`, in this case the "page id" for the Organiser would map to 821.
