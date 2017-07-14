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
import dateutil.parser
import pytz
import httplib2
from apiclient import discovery
from apiclient.errors import HttpError
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# Import your private configuration variables.
from config import *

# which are
# - CLIENT_SECRET_FILE
# (Set this to the file name of your client secret JSON file.)
# - WORK_EMAIL
# - PERSONAL_EMAIL
# - PERSONAL_PERSONAL_CAL_ID
# - WORK_PERSONAL_CAL_ID
# (Create secondary calendars in your personal Google account, one for work and one for
# personal events. These are the IDs for each.)
# - MY_DISPLAY_NAME

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
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        flags = tools.argparser.parse_args(args=[])
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials

def get_events_list(service, cal_id):
    """ Fetches list of events from specified calendar ID. """

    output = []
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId=cal_id, pageToken=page_token,
            singleEvents=True, orderBy='startTime',
            showDeleted=True, showHiddenInvitations=True,
            timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
        ).execute()
        output.extend(events_result.get('items'))
        page_token = events_result.get('nextPageToken')
        if not page_token:
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

        personally_invited = False
        if 'attendees' in event:
            for attendee in event['attendees']:
                if attendee['email'] == PERSONAL_EMAIL:
                    personally_invited = True
        if personally_invited is True:
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


def del_cancels(service, events_list, cal_id):
    """ Deletes from the specified calendar, based on the iCalUID, all events in the list that
     are cancelled. Returns the events list with the deleted events removed. """

    for_deletion = []
    for event in events_list:
        if event.get('status', None) == 'cancelled':
            # The prep_import_from_work function has already 'converted' declines
            # into cancellations.
            for_deletion.append(event)
            events_list.remove(event)

    for event in for_deletion:
        matching_events = []
        page_token = None
        while True:
            # On this list request, no need to show deleted events
            events_result = service.events().list(
                calendarId=cal_id, pageToken=page_token,
                singleEvents=True, orderBy='startTime',
                showDeleted=False, showHiddenInvitations=True,
                timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY,
                iCalUID=event.get('iCalUID', '')
            ).execute()
            matching_events.extend(events_result.get('items'))
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break

        # Builds a list of event IDs to delete, so as to be able to avoid duplication
        ids_to_delete = []
        # for item in matching_events:
        #     # Avoids deleting whole series of recurring events by building IDs for
        #     # individual event cancellations
        #     if 'recurringEventId' in item:
        #         item['id'] = item['recurringEventId'] + '_' + \
        #         datetime.datetime.strftime(
        #             dateutil.parser.parse(item['start']['dateTime'])
        #             .astimezone(pytz.timezone('UTC')),
        #             '%Y%m%dT%H%M%SZ'
        #         )
        #     ids_to_delete.append(item.get('id', ''))

        # Dedupes the list of IDs for deletion
        ids_to_delete = list(set(ids_to_delete))

        # Deletes the events you've (declined or) cancelled from the destination calendar
        for item in ids_to_delete:
            request_backoff(service, cal_id, 'delete', item)

    return events_list


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
    """ Divides the list of all events take back out of the personal calendar into separate
     personal and work lists. """

    work_events = personal_events = []
    for event in all_events:
        # declined = decline_check(event, PERSONAL_EMAIL)

        # Strips off attendees so that you don't accidentally re-invite all your client
        # contacts to meetings that have been cancelled, or execute some similarly
        # career-limiting mistake.
        event.pop('attendees', None)

        # Fills the two lists based on the presence of the description field work tag.
        if 'description' in event:
            if '## sync\'d from work ##' in event['description']:
                # # Sets the right organiser for the calendar the event is going into.
                # event['organizer'] = {
                #     'displayName': 'Kevin - Work only',
                #     'email': WORK_PERSONAL_CAL_ID,
                #     'self': True
                # }
                # # This next line makes sure that access to events in the work secondary
                # # calendar (i.e. in the personal account) is restricted, with
                # # 'private' visibility.
                # event['visibility']	= 'private'
                work_events.append(event)
            else:
                # Sets the right organiser for the calendar the event is going into.
                # event['organizer'] = {
                #     'displayName': 'Kevin - Personal only',
                #     'email': PERSONAL_PERSONAL_CAL_ID,
                #     'self': True
                # }
                # # Converts declined attendence into having cancelled your own appointment.
                # if declined is True:
                #     event['status'] = 'cancelled'
                personal_events.append(event)
        else:
            # I don't know if this happens but if there was no description at all, it couldn't
            # be a work event.
            # event['organizer'] = {
            #     'displayName': 'Kevin - Personal only',
            #     'email': PERSONAL_PERSONAL_CAL_ID,
            #     'self': True
            # }
            # if declined is True:
            #     event['status'] = 'cancelled'
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
    biz_events = get_events_list(service, WORK_EMAIL)

    # Fills a biz_import list with the work events modified for import to personal account
    all_biz_import = prep_import_from_work(biz_events)

    # Deletes work (declines and) cancellations from the primary personal calendar
    biz_import = del_cancels(service, all_biz_import, PERSONAL_EMAIL)

    # Imports the remaining work events into the primary personal calendar
    import_events(service, biz_import, PERSONAL_EMAIL)

    # Fills an all_events list with a complete list of eveything taken back from the
    # primary personal calendar
    all_events = get_events_list(service, PERSONAL_EMAIL)

    # Fills work_ and personal_events lists with the personal account versions of events
    divided_lists = divide_all_events(all_events)

    # Deletes cancellations from the personal secondary calendar in the personal account
    pp_import = del_cancels(
        service, divided_lists.get('personal_events', None), PERSONAL_PERSONAL_CAL_ID
    )
    # Imports the personal events into the personal secondary calendar in the personal account
    import_events(service, pp_import, PERSONAL_PERSONAL_CAL_ID)

    # Deletes cancellations from the work secondary calendar in the personal account
    pw_import = del_cancels(service, divided_lists.get('work_events', None), WORK_PERSONAL_CAL_ID)
    # Imports the work events into the work secondary calendar in the personal account
    import_events(service, pw_import, WORK_PERSONAL_CAL_ID)

if __name__ == '__main__':
    main()
