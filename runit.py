import ical
import insite_scraper


def main(macy_id: str, macy_pass: str, icloud_email: str, icloud_app_pass: str, calendar_name: str):
    cal = ical.Calendar(icloud_email, icloud_app_pass, calendar_name)
    shifts = insite_scraper.scrape_website(macy_id, macy_pass)
    for shift in shifts:
        cal.add_event(shift)
