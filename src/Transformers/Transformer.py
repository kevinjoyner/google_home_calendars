""" doc string"""

class Transformer(object):
    """ doc string """
    def __init__(self):
        pass

    def set_organiser_on_events(self, event, display_name, email):
        """ doc string """
        event['organizer'] = {
            'displayName': display_name,
            'email': email,
            'self': True
        }
        return event

    def set_as_cancelled(self, event):
        """ doc string """
        event['status'] = 'cancelled'
        return event

    def remove_attendees(self, event):
        """ doc string """
        event.pop('attendees', None)
        return event

    def append_to_description(self, event, string):
        """ doc string """
        event['description'] = event.get('description', '') + string
        return event

    def set_private(self, event):
        """ doc string """
        event['visibility']	= 'private'
        return event
