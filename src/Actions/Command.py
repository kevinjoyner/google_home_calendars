""" doc string"""

from time import sleep
from Connectors.CalConnector import CalConnector
from apiclient.errors import HttpError


class Command(object):
    """ doc string """
    def __init__(self):
        connector = CalConnector()
        credentials = connector.get_credentials()
        self.service = connector.setup(credentials)

    def delete_event(self, cal_id, event_id):
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
                self.service.events().delete(calendarId=cal_id, eventId=event_id).execute()
            except HttpError as err:
                if err.resp.status in [403, 500, 503]:
                    wait = wait * wait # If e.g. Rate Limit Exceeded, squares the wait time
                else: raise
            else: break

    def delete_events(self, cal_id, query=None):
        """ Deletes work events from all three personal calendars. """
        matching_events = []
        page_token = None
        while True:
            events_result = self.service.events().list(
                calendarId=cal_id, pageToken=page_token,
                singleEvents=True, orderBy='startTime',
                showHiddenInvitations=True, q=query
            ).execute()
            matching_events.extend(events_result.get('items'))
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        for item in matching_events:
            try:
                wait = 2.25
                while True:
                    try:
                        sleep(wait / 10) # waits 0.225 seconds
                        # then calls the function
                        self.service.events().delete(calendarId=cal_id, eventId=item.get('id', '')).execute()
                    except HttpError as err:
                        if err.resp.status in [403, 500, 503]:
                            wait = wait * wait # If e.g. Rate Limit Exceeded, squares the wait time
                        else: raise
                    else: break
            except HttpError as err:
                if err.resp.status in [410]:
                    continue
                else:
                    raise
        return

    def import_event(self, cal_id, event):
        """ doc string """
        event.pop('id', None)
        event.pop('recurringEventId', None)
        wait = 2.25
        while True:
            try:
                sleep(wait / 10) # waits 0.225 seconds
                # then calls the function
                self.service.events().import_(calendarId=cal_id, body=event).execute()
            except HttpError as err:
                if err.resp.status in [403, 500, 503]:
                    wait = wait * wait # If e.g. Rate Limit Exceeded, squares the wait time
                else: raise
            else: break
