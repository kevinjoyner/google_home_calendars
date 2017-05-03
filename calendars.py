#!/usr/bin/python3

"""
This script manages my Google calendars so that Google Home works better.

It copies a version of my work calendar events into my personal calendar. It then copies my
personal calendar's events into two secondary calendars in the same personal Google account: one
secondary calendar for just the work events, and one for the personal ones.

"""

import datetime
from datetime import timedelta
from time import sleep
import argparse
import httplib2
from apiclient import discovery
from apiclient.errors import HttpError
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# Import your private configuration variables.

from config import *

# These are
# - CLIENT_SECRET_FILE
# (Set this to the file name of your client secret JSON file.)
# - WORK_EMAIL
# - PERSONAL_EMAIL
# - PERSONAL_PERSONAL_CAL_ID
# - WORK_PERSONAL_CAL_ID
# (Create secondary calendars in your personal Google account, one for work and one for
# personal events. These are the IDs for each.)

# Sets things needed to authenticate with Google API
FLAGS = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
SCOPES = [
    'https://www.googleapis.com/auth/calendar'
]
# I don't think this name matters, but you might update it
APPLICATION_NAME = 'API thing'

def get_credentials(flags):
    """ A function for retrieving and storing Google credentials. It returns a Google APIs
     credentials object. """
    credential_path = CREDENTIALS_DIR + 'google-credentials.json'
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        flags = tools.argparser.parse_args(args=[])
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials

def main():
    """ The main function of the script """
    credentials = get_credentials(FLAGS)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    # Prepares min and max dates for the oldest and newest events to handle
    months_ago = (datetime.datetime.utcnow() - timedelta(days=93)).isoformat() + 'Z'
    months_away = (datetime.datetime.utcnow() + timedelta(days=93)).isoformat() + 'Z'

    # Fills a biz_events list with the events from the business calendar
    biz_events = []
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId=WORK_EMAIL, pageToken=page_token,
            singleEvents=True, orderBy='startTime',
            showDeleted=True, showHiddenInvitations=True,
            timeMin=months_ago, timeMax=months_away
        ).execute()
        biz_events.extend(events_result.get('items'))
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break

    # Fills a biz_import list with the work events modified for import to personal account
    biz_import = []
    for event in biz_events:
        declined = False
        if 'attendees' in event: # not all events have attendees
            for attendee in event['attendees']:
                # finds you (at work) in the list of attendees
                if attendee['email'] == WORK_EMAIL:
                    if attendee['responseStatus'] == 'declined':
                        # Having discovered that you're not planning to attend, saves
                        # this for later.
                        declined = True
        new_event = event

        # Tags the events in the description field with something distinctive
        new_event['description'] = event.get('description', '') + \
                                                        '\n\n## sync\'d from work ##'

        # Strips off attendees so that you don't accidentally re-invite all your client
        # contacts to meetings that have been cancelled, or execute some similarly
        # career-limiting mistake.
        new_event.pop('attendees', None)

        # Fixes your personal self as the organizer, so that the events always remain
        # compatible with the fickle laws of calendars: i.e. you do need to be
        # either attending or organising a meeting that's in your calendar.
        new_event['organizer'] = {
            'displayName': 'Kevin Joyner',
            'email': PERSONAL_EMAIL,
            'self': True
            }
        # Converts declined attendence into having cancelled your own appointment.
        if declined is True:
            new_event['status'] = 'cancelled'
        biz_import.append(new_event)

    for event in biz_import:
        # Removes the immutable IDs from the event, but saves id in case it's needed.
        # I think it's the standard iCalUID, which remains on the events, that means
        # this script can run every hour without causing loads of duplicate events.
        originating_id = event.pop('id', None)
        event.pop('recurringEventId', None)

        # The Google Calendar API can take 5 imports per second, apparently. I don't know how you're
        # really supposed to implement "exponential backoff" but I thought I needed this
        # number - the seconds to wait between requests - to be greater than zero, so it's divided
        # by ten a little later...
        wait = 2.25
        while True:
            try:
                sleep(wait / 10) # waits 0.225 seconds
                # then imports the event to the primary personal calendar (which your work Google
                # account needs to be able to access)
                service.events().import_(calendarId=PERSONAL_EMAIL, body=event).execute()
            except HttpError as err:
                if err.resp.status in [403, 500, 503]:
                    wait = wait * wait # If e.g. a Rate Limit Exceeded error, squares the wait time
                elif 'Invalid sequence value.' in err.resp.get('message', ''):
                    event_lookup = service.events().get(
                        calendarId=WORK_EMAIL, eventId=originating_id
                    ).execute()
                    event['sequence'] = event_lookup.get('sequence', 99)
                else: raise
            else: break

    # Fills an all_events list with a complete list of eveything taken back from the
    # personal account.
    all_events = []
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId=PERSONAL_EMAIL, pageToken=page_token,
            singleEvents=True, orderBy='startTime',
            showDeleted=True, showHiddenInvitations=True,
            timeMin=months_ago, timeMax=months_away
        ).execute()
        all_events.extend(events_result.get('items'))
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break


    # Fills work_ and personal_events lists with the personal account versions of recent events
    work_events = []
    personal_events = []
    for event in all_events:
        new_event = event
        # Preps the events for import in the same way as before.
        # (I'm sure some of this could be factored into a separate function.)
        declined = False
        if 'attendees' in new_event: # not all events have attendees
            for attendee in new_event['attendees']:
                # finds you in the list of attendees
                if attendee['email'] == PERSONAL_EMAIL:
                    if attendee['responseStatus'] == 'declined':
                        # Having discovered that you're not planning to attend, saves
                        # this for later.
                        declined = True
        new_event.pop('attendees', None)
        # Fills the two lists based on the presence of the description field work tag.
        if 'description' in new_event:
            if '## sync\'d from work ##' in new_event['description']:
                # Sets the right organiser for the calendar the event is going into.
                new_event['organizer'] = {
                    'displayName': 'Kevin - Work only',
                    'email': WORK_PERSONAL_CAL_ID,
                    'self': True
                }
                # I share my work events with my wife. This next line makes sure that - except
                # for someone getting into my home and playing a recording of my voice to my
                # Google Home, I'm in-line with my employer's permissions - by forcing
                # 'private' visibility.
                new_event['visibility']	= 'private'
                work_events.append(new_event)
            else:
                # Sets the right organiser for the calendar the event is going into.
                new_event['organizer'] = {
                    'displayName': 'Kevin - Personal only',
                    'email': PERSONAL_PERSONAL_CAL_ID,
                    'self': True
                }
                # Converts declined attendence into having cancelled your own appointment.
                if declined is True:
                    new_event['status'] = 'cancelled'
                personal_events.append(new_event)
        else:
            # I don't know if this happens but if there was no description at all, it couldn't
            # be a work event.
            new_event['organizer'] = {
                'displayName': 'Kevin - Personal only',
                'email': PERSONAL_PERSONAL_CAL_ID,
                'self': True
            }
            if declined is True:
                new_event['status'] = 'cancelled'
            personal_events.append(new_event)

    # Imports the personal events into the personal secondary calendar in my personal account
    for event in personal_events:
        originating_id = event.pop('id', None)
        event.pop('recurringEventId', None)
        wait = 2.25
        while True:
            try:
                sleep(wait / 10)
                service.events().import_(
                    calendarId=PERSONAL_PERSONAL_CAL_ID,
                    body=event
                ).execute()
            except HttpError as err:
                if err.resp.status in [403, 500, 503]:
                    wait = wait * wait
                elif 'Invalid sequence value.' in err.resp.get('message', ''):
                    event_lookup = service.events().get(
                        calendarId=PERSONAL_PERSONAL_CAL_ID, eventId=originating_id
                    ).execute()
                    event['sequence'] = event_lookup.get('sequence', 99)
                else: raise
            else: break

    # Imports the work events into the work secondary calendar in my personal account
    for event in work_events:
        originating_id = event.pop('id', None)
        event.pop('recurringEventId', None)
        wait = 2.25
        while True:
            try:
                sleep(wait / 10)
                service.events().import_(
                    calendarId=WORK_PERSONAL_CAL_ID,
                    body=event
                ).execute()
            except HttpError as err:
                if err.resp.status in [403, 500, 503]:
                    wait = wait * wait
                elif 'Invalid sequence value.' in err.resp.get('message', ''):
                    event_lookup = service.events().get(
                        calendarId=WORK_PERSONAL_CAL_ID, eventId=originating_id
                    ).execute()
                    event['sequence'] = event_lookup.get('sequence', 99)
                else: raise
            else: break

if __name__ == '__main__':
    main()
