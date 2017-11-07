""" doc string"""

import json
import datetime
from datetime import timedelta
from Connectors.CalConnector import CalConnector
from apiclient.errors import HttpError

# Load your private configuration variables.
with open('config.json', 'r') as config_file:
    CONFIG_JSON = json.load(config_file)
    WORK_EMAIL = CONFIG_JSON[0]["calendars"]["work"]["email"]
    PERSONAL_EMAIL = CONFIG_JSON[0]["calendars"]["personal"]["email"]

# Prepares min and max dates for the oldest and newest events to handle
MONTHS_AGO = (datetime.datetime.utcnow() - timedelta(days=93)).isoformat() + 'Z'
MONTHS_AWAY = (datetime.datetime.utcnow() + timedelta(days=93)).isoformat() + 'Z'


class EventsFetcher(object):
    """ doc string """
    def __init__(self):
        connector = CalConnector()
        credentials = connector.get_credentials()
        self.service = connector.setup(credentials)

    def fetch_events(self, cal_id, sync_token):
        """ Fetches list of events from specified calendar ID. """
        output = []
        page_token = None
        while True:
            if sync_token:
                try:
                    events_result = self.service.events().list(
                        calendarId=cal_id,
                        pageToken=page_token,
                        syncToken=sync_token,
                        timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
                    ).execute()
                except HttpError as err:
                    if err.resp.status in [401]:
                        if cal_id == WORK_EMAIL:
                            CONFIG_JSON[0]["calendars"]["work"]["sync_token"] =\
                                sync_token = None
                        elif cal_id == PERSONAL_EMAIL:
                            CONFIG_JSON[0]["calendars"]["personal"]["sync_token"] =\
                                sync_token = None
                        with open('config.json', 'w') as config_out_file:
                            json.dump(CONFIG_JSON, config_out_file, indent=4)
                        events_result = self.service.events().list(
                            calendarId=cal_id, pageToken=page_token,
                            singleEvents=True, orderBy='startTime',
                            showDeleted=True, showHiddenInvitations=True,
                            timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
                        ).execute()
                    else: raise
            else:
                events_result = self.service.events().list(
                    calendarId=cal_id, pageToken=page_token,
                    singleEvents=True, orderBy='startTime',
                    showDeleted=True, showHiddenInvitations=True,
                    timeMin=MONTHS_AGO, timeMax=MONTHS_AWAY
                ).execute()
            output.extend(events_result.get('items'))
            page_token = events_result.get('nextPageToken')
            if not page_token:
                if cal_id == WORK_EMAIL:
                    CONFIG_JSON[0]["calendars"]["work"]["sync_token"] =\
                    events_result.get('nextSyncToken')
                elif cal_id == PERSONAL_EMAIL:
                    CONFIG_JSON[0]["calendars"]["personal"]["sync_token"] =\
                    events_result.get('nextSyncToken')
                with open('config.json', 'w') as config_out_file:
                    json.dump(CONFIG_JSON, config_out_file, indent=4)
                break
        return output
