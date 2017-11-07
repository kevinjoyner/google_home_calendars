""" doc string"""

import json
import httplib2
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# Sets things needed to authenticate with Google API
SCOPES = [
    'https://www.googleapis.com/auth/calendar'
]
# I don't think this name matters, but you might update it
APPLICATION_NAME = 'API thing'

# Load your private configuration variables.
with open('config.json', 'r') as config_file:
    CONFIG_JSON = json.load(config_file)
    CREDENTIALS_DIR = CONFIG_JSON[0]["credentials"]["CREDENTIALS_DIR"]
    CLIENT_SECRET_PATH = CONFIG_JSON[0]["credentials"]["CLIENT_SECRET_PATH"]


class CalConnector(object):
    """ doc string """
    def __init__(self):
        self.credentials = self.get_credentials()
        self.service = self.setup(self.credentials)

    @staticmethod
    def get_credentials():
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

    @staticmethod
    def setup(credentials):
        """ doc string """
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('calendar', 'v3', http=http)

        return service
