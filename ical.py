from datetime import datetime, timedelta
from binascii import hexlify
from os import urandom
import caldav
from caldav.elements import dav


class Event:
    """A variant of event formatted to my liking for use with iCloud"""

    def __init__(self, event_object: caldav.Event = None):
        # Generate new event
        uid_parts = [4, 2, 2, 2, 6]
        for index, size in enumerate(uid_parts):
            uid_parts[index] = str(hexlify(urandom(size)))[2:-1]
        self._uid = '-'.join(uid_parts)

        # Free to edit these variables at will
        self.summary = ''
        self.description = ''
        self.location = ''
        self.timezone = ''

        # These attributes are monitored, but free
        self._start = self._end = self._dtstamp = self._created = datetime.now().strftime('%Y%m%dT%H%M%S')

        # These really shouldnt be used
        self._original_object = event_object
        self.__set_lastmodified__()
        self._sequence = 0

        # Overwrite with passed event
        if event_object is not None:
            self.__process_event_string_(event_object.data)
            return

    def __str__(self):
        return self.summary + \
               ' on ' + \
               self.start.strftime('%m%/%d%/%Y') + \
               ' from ' + \
               self.start.strftime('%H%:%M') + \
               ' to ' + \
               self.end.strftime('%H%:%M')

    def remove(self):
        self._original_object.delete()

    @property
    def sequence(self):
        return self._sequence

    @property
    def uid(self):
        return self._uid

    @property
    def start(self):
        year = int(self._start[:4])
        month = int(self._start[4:6])
        day = int(self._start[6:8])
        hour = int(self._start[9:11])
        minute = int(self._start[11:13])
        return datetime(year, month, day, hour, minute)

    @start.setter
    def start(self, to: datetime):
        self.__set_lastmodified__()
        self._start = to.strftime('%Y%m%dT%H%M%S')

    @property
    def end(self):
        year = int(self._end[:4])
        month = int(self._end[4:6])
        day = int(self._end[6:8])
        hour = int(self._end[9:11])
        minute = int(self._end[11:13])
        return datetime(year, month, day, hour, minute)

    @end.setter
    def end(self, to: datetime):
        self.__set_lastmodified__()
        self._end = to.strftime('%Y%m%dT%H%M%S')

    def __set_lastmodified__(self):
        self.lastmodified = datetime.now().strftime('%Y%m%dT%H%M%S')

    def ical_string(self) -> str:
        """Gathers all of the events data into a push string"""
        tz = ''
        if self.timezone != '':
            tz = ';TZID=' + self.timezone
        result = ['BEGIN:VCALENDAR',
                  'BEGIN:VEVENT',
                  'CREATED:' + self._created,
                  'DESCRIPTION:' + self.description,
                  'DTEND' + tz + ':' + self._end,
                  'DTSTAMP' + tz + ':' + self._dtstamp,
                  'DTSTART' + tz + ':' + self._start,
                  'LAST-MODIFIED:' + self.lastmodified,
                  'LOCATION:' + self.location,
                  'SEQUENCE:' + str(self._sequence),
                  'SUMMARY:' + self.summary,
                  'UID:' + self._uid,
                  'END:VEVENT',
                  'END:VCALENDAR']
        return '\n'.join(result)

    def __process_event_string_(self, event_string: str):
        details = []
        ignore_previous = False

        # Convert the raw data into more workable data (mostly just removing Apple's weird stuff)
        for line in event_string.split('\n'):
            if ':' in line:
                ignore_previous = False
                details.append(line)
            elif not ignore_previous \
                    and 'x-apple' not in line.lower() \
                    and 'x-master' not in line.lower():
                details[len(details) - 1] = details[len(details) - 1] + ' ' + line
            else:
                ignore_previous = True

        # Go through all of the details
        for detail in details:
            # Todo: Figure out what causes this
            if detail.count(':') > 2:
                print('Warning: I assumed something wrong and it might break')
                print(detail)

            heading, value = detail.split(':', 1)
            # Try to update timezone first
            if self.timezone == '' and 'tzid' in heading.lower():
                self.timezone = heading.split(';TZID=')[1]
            heading = heading.lower()

            # Map all attributes to proper space
            if 'created' in heading:
                self._created = value
                continue
            if 'dtend' in heading:
                self._end = value
                continue
            if 'dtstart' in heading:
                self._start = value
                continue
            if 'last-modified' in heading:
                self.lastmodified = value
                continue
            if 'dtstamp' in heading:
                self._dtstamp = value
                continue
            if 'summary' in heading:
                self.summary = value
                continue
            if 'description' in heading:
                self.description = value
                continue
            if 'location' in heading:
                self.location = value
                continue
            if 'uid' in heading:
                self._uid = value
                continue
            if 'sequence' in heading:
                self._sequence = value
                continue

    def push(self, calendar: caldav.objects.Calendar):
        # TODO: Check calendar if event already exists to increment sequence
        if self._original_object is None:
            self._original_object = caldav.Event(calendar.client, None, self.ical_string())
        calendar.add_event(self.ical_string())


class Calendar:
    """A CalDav variant formatted to my liking for use with iCloud"""

    important_labels = ['summary', 'description', 'dtend', 'dtstart']
    time_labels = ['dtend', 'dtstart', 'dtstamp', 'last-modified', 'created']
    active_calendar = None

    def __init__(self, username, password, calendar_name=None):
        url = 'https://' + username + ':' + password + '@caldav.icloud.com:443'
        self.client = caldav.DAVClient(url)
        self.principal = self.client.principal()
        self.events = []
        self._calendar = None
        if calendar_name is not None:
            self.calendar = calendar_name

    @property
    def calendars(self):
        calendar_names = []
        for calendar in self.principal.calendars():
            calendar_names.append(calendar.get_properties([dav.DisplayName(), ])['{DAV:}displayname'])
        return calendar_names

    @property
    def calendar(self):
        return self._calendar.get_properties([dav.DisplayName(), ])['{DAV:}displayname']

    @calendar.setter
    def calendar(self, calendar_name):
        for calendar in self.principal.calendars():
            if calendar.get_properties([dav.DisplayName(), ])['{DAV:}displayname'].lower() == calendar_name.lower():
                self._calendar = calendar
                return
        raise ValueError('Calendar does not exist on this user')

    def get_events(self, start_date: datetime, end_date: datetime):
        """Return events over specified amount of time"""

        events = []
        # Iterate through all events over the given
        for event_string in self._calendar.date_search(start_date, end_date):
            events.append(Event(event_string))
        return events

    def add_event(self, event: Event):
        events = self.get_events(event.start - timedelta(1), event.end + timedelta(1))
        print('looking at', len(events))
        for comparable in events:
            print('  Comparing', comparable)
            if str(event) == str(comparable):
                if event.summary == comparable.summary and \
                   event.description == comparable.description and \
                   event.location == comparable.location:
                    # Events are the same in terms of important details
                    print('Skipping', event)
                    return
                else:
                    print('Deleting', comparable)
                    comparable.remove()
                    break
        print('Adding', event)
        self._calendar.add_event(event.ical_string())

    def clear_thirty(self):
        now = datetime.today()
        start = datetime(now.year, now.month, now.day, 0, 0)
        for event in self.get_events(start, start + timedelta(30)):
            event.remove()
