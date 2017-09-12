#!/usr/bin/python3

"""
This script manages my Google calendars so that Google Home works better.

It copies a version of my work calendar events into my personal calendar. It then copies my
personal calendar's events into two secondary calendars in the same personal Google account: one
secondary calendar for just the work events, and one for the personal ones.

"""

import json
import datetime
from datetime import timedelta
from time import sleep
import argparse
# import dateutil.parser
# import pytz
import httplib2
from apiclient import discovery
from apiclient.errors import HttpError
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage


# Load your private configuration variables.
with open('config.json', 'r') as config_file:
    CONFIG_JSON = json.load(config_file)
    CREDENTIALS_DIR = CONFIG_JSON[1]["CREDENTIALS_DIR"]
    CLIENT_SECRET_PATH = CONFIG_JSON[1]["CLIENT_SECRET_PATH"]
    WORK_EMAIL = CONFIG_JSON[1]["WORK_EMAIL"]
    PERSONAL_EMAIL = CONFIG_JSON[1]["PERSONAL_EMAIL"]
    WORK_SYNC_TOKEN = CONFIG_JSON[1]["WORK_SYNC_TOKEN"]
    PERSONAL_SYNC_TOKEN = CONFIG_JSON[1]["PERSONAL_SYNC_TOKEN"]
    PERSONAL_PERSONAL_CAL_ID = CONFIG_JSON[1]["PERSONAL_PERSONAL_CAL_ID"]
    WORK_PERSONAL_CAL_ID = CONFIG_JSON[1]["WORK_PERSONAL_CAL_ID"]
    MY_DISPLAY_NAME = CONFIG_JSON[1]["MY_DISPLAY_NAME"]

# Sets things needed to authenticate with Google API
FLAGS = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
SCOPES = [
    'https://www.googleapis.com/auth/calendar'
]
# I don't think this name matters, but you might update it
APPLICATION_NAME = 'API thing'

# Prepares min and max dates for the oldest and newest events to handle
MONTHS_AGO = (datetime.datetime.utcnow() - timedelta(days=93)).isoformat() + 'Z'
MONTHS_AWAY = (datetime.datetime.utcnow() + timedelta(days=93)).isoformat() + 'Z'


def get_credentials(flags):
    """ A function for retrieving and storing Google credentials. It returns a Google APIs
        credentials object. """
    credential_path = CREDENTIALS_DIR + 'google-credentials.json'
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_PATH, SCOPES)
        flow.user_agent = APPLICATION_NAME
        flags = tools.argparser.parse_args(args=[])
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials

def get_events_list(service, cal_id, sync_token):
    """ Fetches list of events from specified calendar ID. """
    output = []
    page_token = None
    while True:
        if sync_token:
            try:
                events_result = service.events().list(
                    calendarId=cal_id,
                    pageToken=page_token,
                    syncToken=sync_token,
                    timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
                ).execute()
            except HttpError as err:
                if err.resp.status in [401]:
                    if cal_id == WORK_EMAIL:
                        CONFIG_JSON[1]["WORK_SYNC_TOKEN"] = sync_token = None
                    elif cal_id == PERSONAL_EMAIL:
                        CONFIG_JSON[1]["PERSONAL_SYNC_TOKEN"] = sync_token = None
                    with open('config.json', 'w') as config_out_file:
                        json.dump(CONFIG_JSON, config_out_file)
                    events_result = service.events().list(
                        calendarId=cal_id, pageToken=page_token,
                        singleEvents=True, orderBy='startTime',
                        showDeleted=True, showHiddenInvitations=True,
                        timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
                    ).execute()
                else: raise
        else:
            events_result = service.events().list(
                calendarId=cal_id, pageToken=page_token,
                singleEvents=True, orderBy='startTime',
                showDeleted=True, showHiddenInvitations=True,
                timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
            ).execute()
        output.extend(events_result.get('items'))
        page_token = events_result.get('nextPageToken')
        if not page_token:
            if cal_id == WORK_EMAIL:
                CONFIG_JSON[1]["WORK_SYNC_TOKEN"] = events_result.get('nextSyncToken')
            elif cal_id == PERSONAL_EMAIL:
                CONFIG_JSON[1]["PERSONAL_SYNC_TOKEN"] = events_result.get('nextSyncToken')
            with open('config.json', 'w') as config_out_file:
                json.dump(CONFIG_JSON, config_out_file)
            break
    return output

def decline_check(event, declining_email):
    """ Returns boolean indicating whether an event has been declined by the
        specified email address. """
    declined = False
    if 'attendees' in event: # not all events have attendees
        for attendee in event['attendees']:
            # finds you in the list of attendees
            if attendee['email'] == declining_email:
                if attendee['responseStatus'] == 'declined':
                    # Having discovered that you're not planning to attend, saves
                    # this for later.
                    declined = True
                    break
    return declined

def prep_import_from_work(events_list):
    """ Prepares work events for import to personal calendar. """
    output = []
    for event in events_list:
        declined = decline_check(event, WORK_EMAIL)
        # If personal email is organiser or attendee, then skip this event
        if event['organizer']['email'] == PERSONAL_EMAIL:
            continue
        if 'attendees' in event:
            for attendee in event['attendees']:
                if attendee['email'] == PERSONAL_EMAIL:
                    continue
        # Tags the events in the description field with something distinctive
        event['description'] = event.get('description', '') + \
                                                        '\\n\\n## sync\'d from work ##'
        # Strips off attendees so that you don't accidentally re-invite all your client
        # contacts to meetings that have been cancelled, or execute some similarly
        # career-limiting mistake.
        event.pop('attendees', None)
        # Fixes your personal self as the organizer, because a calendar requires
        # that you are either attending or organising a meeting that's in your calendar.
        event['organizer'] = {
            'displayName': MY_DISPLAY_NAME,
            'email': PERSONAL_EMAIL,
            'self': True
            }
        # Converts declined attendence into having cancelled your own appointment.
        if declined is True:
            event['status'] = 'cancelled'
        output.append(event)
    return output

def request_backoff(service, cal_id, request_type, request_data):
    """ Wraps either a delete or import request in an "exponential backoff,"
        I think... """
    # The Google Calendar API can take 5 requests per second, apparently. I don't know
    # how you're really supposed to implement "exponential backoff" but I think I need
    # this 'wait' value number - the seconds to wait between requests - to be greater
    # than zero - so it's divided by ten a little later...
    wait = 2.25
    while True:
        try:
            sleep(wait / 10) # waits 0.225 seconds
            # then calls the function
            if request_type == 'delete':
                service.events().delete(calendarId=cal_id, eventId=request_data).execute()
            elif request_type == 'import':
                service.events().import_(calendarId=cal_id, body=request_data).execute()
        except HttpError as err:
            if err.resp.status in [403, 500, 503]:
                wait = wait * wait # If e.g. Rate Limit Exceeded, squares the wait time
            else: raise
        else: break

def import_events(service, events_list, dest_cal_id):
    """ Imports list of events to the destination calendar. Uses the originating calendar to work
        around sequence number errors if they occur. """
    for event in events_list:
        # Removes the immutable IDs from the event. I think it's the standard iCalUID,
        # which remains on the events, that means this script can run every hour without
        # causing duplicate events.
        event.pop('id', None)
        event.pop('recurringEventId', None)
        request_backoff(service, dest_cal_id, 'import', event)

def divide_all_events(all_events):
    """ Divides the list of all events taken back out of the personal calendar into separate
        personal and work lists. """
    work_events = personal_events = []
    for event in all_events:
        # Strips off attendees so that you don't accidentally re-invite all your client
        # contacts to meetings that have been cancelled, or execute some similarly
        # career-limiting mistake.
        event.pop('attendees', None)
        # Fills the two lists based on the presence of the description field work tag.
        if 'description' in event:
            if '## sync\'d from work ##' in event['description']:
                work_events.append(event)
            else:
                personal_events.append(event)
        else:
            # I don't know if this happens but if there was no description at all, it couldn't
            # be a work event.
            personal_events.append(event)
    for event in work_events:
        # Sets the right organiser for the calendar the event is going into.
        event['organizer'] = {
            'displayName': 'Kevin - Work only',
            'email': WORK_PERSONAL_CAL_ID,
            'self': True
        }
        # This next line makes sure that access to events in the work secondary
        # calendar (i.e. in the personal account) is restricted, with
        # 'private' visibility.
        event['visibility']	= 'private'
    for event in personal_events:
        declined = decline_check(event, PERSONAL_EMAIL)
        # Sets the right organiser for the calendar the event is going into.
        event['organizer'] = {
            'displayName': 'Kevin - Personal only',
            'email': PERSONAL_PERSONAL_CAL_ID,
            'self': True
        }
        # Converts declined attendence into having cancelled your own appointment.
        if declined is True:
            event['status'] = 'cancelled'
    return {'work_events': work_events, 'personal_events': personal_events}

def main():
    """ The main function of the script """

    credentials = get_credentials(FLAGS)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    # Fills a biz_events list with the events from the business calendar
    biz_events = get_events_list(service, WORK_EMAIL, WORK_SYNC_TOKEN)

    # Fills a biz_import list with the work events modified for import to personal account
    biz_import = prep_import_from_work(biz_events)

    # Deletes work (declines and) cancellations from the primary personal calendar
    # biz_import = del_cancels(service, all_biz_import, PERSONAL_EMAIL)

    # Imports the remaining work events into the primary personal calendar
    import_events(service, biz_import, PERSONAL_EMAIL)

    # Fills an all_events list with a complete list of eveything taken back from the
    # primary personal calendar
    all_events = get_events_list(service, PERSONAL_EMAIL, PERSONAL_SYNC_TOKEN)

    # Fills work_ and personal_events lists with the personal account versions of events
    divided_lists = divide_all_events(all_events)

    # Deletes cancellations from the personal secondary calendar in the personal account
    # pp_import = del_cancels(
    #     service, divided_lists.get('personal_events', None), PERSONAL_PERSONAL_CAL_ID
    # )
    # Imports the personal events into the personal secondary calendar in the personal account
    import_events(service, divided_lists.get('personal_events', None), PERSONAL_PERSONAL_CAL_ID)

    # Deletes cancellations from the work secondary calendar in the personal account
    # pw_import = del_cancels(service, divided_lists.get('work_events', None), WORK_PERSONAL_CAL_ID)
    # Imports the work events into the work secondary calendar in the personal account
    import_events(service, divided_lists.get('work_events', None), WORK_PERSONAL_CAL_ID)

if __name__ == '__main__':
    main()
