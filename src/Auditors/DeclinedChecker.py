""" doc string"""

class DeclinedChecker(object):
    """ doc string """
    def __init__(self):
        pass

    def decline_check(self, event, declining_email):
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
