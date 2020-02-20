from webbot import Browser
from datetime import datetime, timedelta
from time import sleep
import re
from ical import Event


def scrape_website(username: str, password: str):
    def check_for_password_expire(browser: Browser):
        if browser.exists(text='Expiration Notice', tag='h1') and browser.exists(id='loginButton_0'):
            browser.click(id='loginButton_0')
            return True
        return False

    web = Browser(False)

    # TODO: Async this up if possible
    timeout = 10
    web.go_to('https://hr.macys.net/insite/common/home.aspx')
    while timeout > 0 and \
            (not web.exists(id='idToken1') or
             not web.exists(id='idToken2') or
             not web.exists(id='loginButton_0')):
        timeout = timeout - 1
        sleep(1)
    if timeout == 0:
        print('Couldn\'t load webpage.')
        web.close_current_tab()
        return None
    sleep(1)

    web.type(username, id='idToken1')
    web.type(password, id='idToken2')
    web.click(id='loginButton_0')

    timeout = 10
    while timeout > 0 and web.get_title().lower() != 'my insite':
        if check_for_password_expire(web):
            timeout = 10
        timeout = timeout - 1
        sleep(1)
    if timeout == 0:
        print('Couldn\'t successfully login')
        web.close_current_tab()

    timeout = 10
    web.go_to('https://hr.macys.net/msp/MySchedule/MySchedule.aspx')
    while timeout > 0 and not web.exists(id='form1'):
        timeout = timeout - 1
        sleep(1)
    if timeout == 0:
        print('Failed to load scheudle')
        web.close_current_tab()
        return None

    # TODO: Refine search so no regex is needed
    cells = web.find_elements(classname='myschedtblcell')
    shifts = []
    now = datetime.today()
    for cell in cells:
        # Only use the ones that match a schedule cell (Starts with 2 numbers or this/next month
        if re.match(r'[0-9]{2}', cell.text[:2]) \
                or re.match(now.strftime('%B'), cell.text) \
                or re.match(datetime(now.year, now.month + 1, 1).strftime('%B'), cell.text):
                shifts.append(re.sub(r'[\n]+', '\n', re.sub(r' - ', '\n',
                                                              re.sub(now.strftime('%B') + ' ', '', re.sub(
                                                                   datetime(now.year, now.month + 1,
                                                                            1).strftime('%B') + ' ', '',
                                                                   cell.text)))).split('\n'))

    web.close_current_tab()

    events = []
    now = datetime.today() - timedelta(1)
    for shift in shifts:
        now = now + timedelta(1)
        if now.day != int(shift[0]):
            error_message = shift[0] + ' does not match ' + str(now.month) + ' ' + str(now.day) + ', ' + str(now.year)
            raise ValueError(error_message)
        if 'Pick Up A Shift!' in shift:
            continue
        e = Event()
        e.location = 'Macys'
        e.description = ' '.join([shift[3], shift[4], shift[5]])
        e.summary = shift[4]
        hour, minute = shift[1][:-1].split(':')
        hour = int(hour)
        minute = int(minute)
        if shift[1][-1:] == 'a' and hour == 12:
            hour = 0
        if shift[1][-1:] == 'p' and hour != 12:
            hour = hour + 12
        e.start = datetime(now.year, now.month, now.day, hour, minute)
        hour, minute = shift[2][:-1].split(':')
        hour = int(hour)
        minute = int(minute)
        if shift[2][-1:] == 'a' and hour == 12:
            hour = 0
        if shift[2][-1:] == 'p' and hour != 12:
            hour = hour + 12
        e.end = datetime(now.year, now.month, now.day, hour, minute)
        events.append(e)

    return events
