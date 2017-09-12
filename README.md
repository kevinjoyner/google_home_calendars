# google_home_calendars
Python script for organising work and personal calendars to make Google Home better

## The problem
Your most important calendar is your work one, but Google Home needs to be connected to your peronsal Google account. Google has added support for multiple linked accounts, but it doesn't handle multiple accounts for the same voice (i.e. for the same person).

## The solution
You can give your work Google user account full permission over your personal calendars. This script uses your work credentials to copy - safely! - your work events into your primary personal calendar, and then also to copy your work and personal events into two separate secondary calendars in your personal account.

You keep the separation you need for yourself, but the Google Assistant can now see appointments for everything you're doing, and be much more helpful.

I run the script hourly with cron, from a linux server.

## Feature details
The script
- Configurable to work with events within a specific relative date range, e.g. as old as six months ago, and up to six months into the future
- Tags your work events as they're copied into your personal account, by adding a line to the description, "## sync'd from work ##"
- Removes all attendees from the copies of your events...
- ... and so also fixes you (at your personal email address) as the organiser of copied events. Removing attendees removes the risk of accidentally inviting people to duplicate events; and it keeps any of your contacts' email addresses from being copied anywhere.
- Transfers changed and cancelled events, to keep your calendars sync'd
- Converts having declined to attend an origin calendar event into a cancellation in the destination (where you are the organizer of events that have no attendees)
- In the work secondary calendar in your personal Google account, the events are all set to Private visibility, ensuring restricted access to work information.

## Apologies
- There are bits of the code that I'm sure are inelegant and inefficient.
- I've used OAuth for authentication with Google. I run the script locally and then allow the credentials token to be pushed to my server. This works okay, but I need to get round to swapping this for service account credentials, which are better suited to a script running from a server.

## Authentication and privacy
- The .gitignore file on Github excludes files in the credentials folder. If you use git to deploy to a server that the script runs from, you can move your credentials files to the server manually.
- To avoid them being posted on Github, configuration variables (including email addresses and calendar IDs) are in a separate JSON file that's accessed by the main script. This file, "config.json", is also excluded from the repo with the .gitignore file.
