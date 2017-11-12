#!/usr/bin/python3

"""
This script manages my Google calendars so that Google Home works better.

It copies a version of my work calendar events into my personal calendar. It then copies my
personal calendar's events into two secondary calendars in the same personal Google account: one
secondary calendar for just the work events, and one for the personal ones.

"""

import json
from Providers.EventsFetcher import EventsFetcher
from Auditors.DeclinedChecker import DeclinedChecker
from Auditors.WorkEventChecker import WorkEventChecker
from Transformers.Transformer import Transformer
from Actions.Command import Command


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
    PERSONAL_WORK_DISPLAY_NAME = CONFIG_JSON[0]["calendars"]["personal"]["calendars"]\
        ["work"]["display_name"]
    PERSONAL_WORK_CAL_ID = CONFIG_JSON[0]["calendars"]["personal"]["calendars"]\
        ["work"]["email"]


def main():
    """ The main function """

    events_fetcher = EventsFetcher()
    events_from_work_cal, delete = events_fetcher.fetch_events(WORK_EMAIL, WORK_SYNC_TOKEN)

    declined_checker = DeclinedChecker()
    transformer = Transformer()
    events_for_import = []
    for event in events_from_work_cal:
        is_declined = declined_checker.decline_check(event, WORK_EMAIL)
        event_stripped_of_attendees = transformer.remove_attendees(event)
        event_tagged_as_from_work = transformer.append_to_description(
            event_stripped_of_attendees, '\n\n## sync\'d from work ##'
        )
        event_with_organiser = transformer.set_organiser_on_events(
            event_tagged_as_from_work,
            PERSONAL_DISPLAY_NAME, PERSONAL_EMAIL
        )
        if is_declined is True:
            event_for_import = transformer.set_as_cancelled(event_with_organiser)
            events_for_import.append(event_for_import)
        else:
            event_for_import = event_with_organiser
            events_for_import.append(event_for_import)

    command = Command()
    if delete = True:
        command.delete_events(PERSONAL_EMAIL, " sync\'d from work ")
    for event in events_for_import:
        command.import_event(PERSONAL_EMAIL, event)

    all_personal_events, delete = events_fetcher.fetch_events(PERSONAL_EMAIL, PERSONAL_SYNC_TOKEN)
    work_event_checker = WorkEventChecker()
    work_events = []
    personal_events = []
    for event in all_personal_events:
        is_work_event = work_event_checker.work_event_check(event)
        if is_work_event is True:
            work_events.append(event)
        else:
            personal_events.append(event)

    if delete = True:
        command.delete_events(PERSONAL_WORK_CAL_ID)
        command.delete_events(PERSONAL_PERSONAL_CAL_ID)

    for event in work_events:
        event = transformer.set_organiser_on_events(
            event, PERSONAL_WORK_DISPLAY_NAME, PERSONAL_WORK_CAL_ID
        )
        event = transformer.set_private(event)
        event = transformer.remove_attendees(event)
        command.import_event(PERSONAL_WORK_CAL_ID, event)

    for event in personal_events:
        declined = declined_checker.decline_check(event, PERSONAL_EMAIL)
        event = transformer.remove_attendees(event)
        event = transformer.set_organiser_on_events(
            event, PERSONAL_PERSONAL_DISPLAY_NAME, PERSONAL_PERSONAL_CAL_ID
        )
        if declined is True:
            event = transformer.set_as_cancelled(event)
        command.import_event(PERSONAL_PERSONAL_CAL_ID, event)

if __name__ == '__main__':
    main()
