#!/usr/bin/python3

"""
This script manages my Google calendars so that Google Home works better.

It copies a version of my work calendar events into my personal calendar. It then copies my
personal calendar's events into two secondary calendars in the same personal Google account: one
secondary calendar for just the work events, and one for the personal ones.

"""

import json
# from Connectors.CalConnector import CalConnector
from Providers.EventsFetcher import EventsFetcher
from Auditors.DeclinedChecker import DeclinedChecker
from Transformers.Transformer import Transformer
from Actions.Command import Command


# Load your private configuration variables.
with open('config.json', 'r') as config_file:
    CONFIG_JSON = json.load(config_file)

    WORK_SYNC_TOKEN = CONFIG_JSON[0]["calendars"]["work"]["sync_token"]
    WORK_EMAIL = CONFIG_JSON[0]["calendars"]["work"]["email"]

    PERSONAL_SYNC_TOKEN = CONFIG_JSON[0]["calendars"]["personal"]["sync_token"]
    PERSONAL_DISPLAY_NAME = CONFIG_JSON[0]["calendars"]["personal"]["display_name"]
    PERSONAL_EMAIL = CONFIG_JSON[0]["calendars"]["personal"]["email"]

    PERSONAL_PERSONAL_DISPLAY_NAME = CONFIG_JSON[0]["calendars"]["personal"]["calendars"]\
        ["personal"]["display_name"]
    PERSONAL_PERSONAL_CAL_ID = CONFIG_JSON[0]["calendars"]["personal"]["calendars"]\
        ["personal"]["email"]

    WORK_PERSONAL_DISPLAY_NAME = CONFIG_JSON[0]["calendars"]["personal"]["calendars"]\
        ["work"]["display_name"]
    WORK_PERSONAL_CAL_ID = CONFIG_JSON[0]["calendars"]["personal"]["calendars"]\
        ["work"]["email"]


def main():
    """ The main function of the script """

    events_fetcher = EventsFetcher()
    declined_checker = DeclinedChecker()
    transformer = Transformer()
    command = Command()

    # Fills a biz_events list with the events from the business calendar
    biz_events = events_fetcher.fetch_events(WORK_EMAIL, WORK_SYNC_TOKEN)

    # Fills a biz_import list with the work events modified for import to personal account
    biz_import = []
    for event in biz_events:
        declined = declined_checker.decline_check(event, WORK_EMAIL)

        # If personal email is organiser or attendee, then skip this event
        if event['organizer']['email'] == PERSONAL_EMAIL:
            continue
        if 'attendees' in event:
            for attendee in event['attendees']:
                if attendee['email'] == PERSONAL_EMAIL:
                    continue

        # Tags the events in the description field with something distinctive
        event = transformer.append_to_description(event, '\n\n## sync\'d from work ##')

        # Strips off attendees so that you don't accidentally re-invite all your client
        # contacts to meetings that have been cancelled, or execute some similarly
        # career-limiting mistake.
        event = transformer.remove_attendees(event)

        # Fixes your personal self as the organizer, because a calendar requires
        # that you are either attending or organising a meeting that's in your calendar.
        event = transformer.set_organiser_on_events(event, PERSONAL_DISPLAY_NAME, PERSONAL_EMAIL)

        # Converts declined attendence into having cancelled your own appointment.
        if declined is True:
            event = transformer.set_as_cancelled(event)
        biz_import.append(event)

    # Delete all work events previously sync'd to main personal calendar
    command.delete_events(PERSONAL_EMAIL, '## sync\'d from work ##')

    # Delete all events previously sync'd to the secondary personal calendars
    command.delete_events(PERSONAL_PERSONAL_CAL_ID)
    command.delete_events(WORK_PERSONAL_CAL_ID)

    # Imports the remaining work events into the primary personal calendar
    for event in biz_import:
        command.import_event(PERSONAL_EMAIL, event)

    # Fills an all_events list with a complete list of eveything taken back from the
    # primary personal calendar
    all_events = EventsFetcher.fetch_events(PERSONAL_EMAIL, PERSONAL_SYNC_TOKEN)

    # Fills work_ and personal_events lists with the personal account versions of events
    work_events = personal_events = []
    for event in all_events:
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
        event = transformer.set_organiser_on_events(
            event, WORK_PERSONAL_DISPLAY_NAME, WORK_PERSONAL_CAL_ID
        )

        # This next line makes sure that access to events in the work secondary
        # calendar (i.e. in the personal account) is restricted, with
        # 'private' visibility.
        event = transformer.set_private(event)

        # Strips off attendees so that you don't accidentally re-invite all your client
        # contacts to meetings that have been cancelled, or execute some similarly
        # career-limiting mistake.
        event = transformer.remove_attendees(event)
    for event in personal_events:
        declined = declined_checker.decline_check(event, PERSONAL_EMAIL)

        # Sets the right organiser for the calendar the event is going into.
        event = transformer.set_organiser_on_events(
            event, PERSONAL_PERSONAL_DISPLAY_NAME, PERSONAL_PERSONAL_CAL_ID
        )

        # Converts declined attendence into having cancelled your own appointment.
        if declined is True:
            event = transformer.set_as_cancelled(event)
        event = transformer.remove_attendees(event)

    # Imports the personal events into the personal secondary calendar in the personal account
    for event in personal_events:
        command.import_event(event, PERSONAL_PERSONAL_CAL_ID)

    # Imports the work events into the work secondary calendar in the personal account
    for event in personal_events:
        command.import_event(event, WORK_PERSONAL_CAL_ID)

if __name__ == '__main__':
    main()
