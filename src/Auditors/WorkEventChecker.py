""" doc string"""

class WorkEventChecker(object):
    """ doc string """
    def __init__(self):
        pass

    def work_event_check(self, event):
        """ doc string """
        if 'description' in event:
            if '## sync\'d from work ##' in event['description']:
                work_event = True
            else:
                work_event = False
        else:
            work_event = False

        return work_event
