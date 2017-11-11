""" doc string"""

class WorkEventChecker(object):
    """ doc string """
    def __init__(self):
        pass

    def work_event_check(self, event):
        """ doc string """
        work_event = False
        if 'description' in event:
            if '## sync\'d from work ##' in event['description']:
                work_event = True

        return work_event
