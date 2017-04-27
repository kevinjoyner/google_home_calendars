# google_home_calendars
Python script for organising work and personal calendars to make Google Home better

## The problem
Your most important calendar is your work one, but Google Home needs to be connected to your peronsal Google account. Google is adding support for multiple linked accounts, but it won't handle multiple accounts for the same voice (person).

## The solution
You can give your work Google account full permission over your personal calendars. This script uses your work credentials to copy - safely! - your work events into your primary personal calendar, and then also into two separate secondary calendars in your personal account.

You keep the separation you need for yourself, but the Google Assistant can now see everything you're doing, and be much more helpful.

I run the script hourly with cron, from a linux server.

## Feature details
The script
- Works with events as old as six months ago, and up to six months into the future
- Ignores events that have been cancelled
- Ignores events that you've declined, because you don't need multiple records of stuff you're not doing
- Tags your work events as they're copied into your personal account, by adding a line to the description, "## sync'd from work ##
- Removes all attendees from the copies of your work events...
- ... and fixes you as the organiser of everything, in those copies. Your work account should remain in control.
- In the work secondary calendar in your personal Google account, the events are all set to Private visibility, ensuring restricted access to work information.

## Apologies
- There are bits of the code that I'm sure are inelegant and inefficient.
- I've used OAuth for authentication with Google. I run the script locally and then allow the credentials token to be pushed to my server. This which works for me, but no doubt it's stupid and bad pratice or something.

## On that note
- The .gitignore file on Github excludes files in the credentials folder so that would need changing if you're going to handle the credentials like I do.

