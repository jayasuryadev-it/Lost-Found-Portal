import os
import requests
from dotenv import load_dotenv

load_dotenv()

EMAILJS_SERVICE_ID = os.getenv("EMAILJS_SERVICE_ID")
EMAILJS_TEMPLATE_ID = os.getenv("EMAILJS_TEMPLATE_ID")
EMAILJS_PUBLIC_KEY = os.getenv("EMAILJS_PUBLIC_KEY")
EMAILJS_PRIVATE_KEY = os.getenv("EMAILJS_PRIVATE_KEY")

EMAILJS_API_URL = "https://api.emailjs.com/api/v1.0/email/send"


def send_match_notification(
    to_email: str,
    to_name: str,
    lost_item_title: str,
    found_item_title: str,
    finder_name: str,
    finder_email: str,
    found_location: str,
) -> bool:
    """Send email to the LOST item owner when a matching FOUND item is posted."""
    if not all([EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID, EMAILJS_PUBLIC_KEY]):
        print("EmailJS not configured, skipping notification")
        return False

    payload = {
        "service_id": EMAILJS_SERVICE_ID,
        "template_id": EMAILJS_TEMPLATE_ID,
        "user_id": EMAILJS_PUBLIC_KEY,
        "accessToken": EMAILJS_PRIVATE_KEY,
        "template_params": {
            "to_email": to_email,
            "to_name": to_name,
            "item_title": lost_item_title,
            "finder_name": finder_name,
            "finder_email": finder_email,
            "message": (
                f"A matching item was found!\n\n"
                f"Your lost item: {lost_item_title}\n"
                f"Matching found item: {found_item_title}\n"
                f"Found at: {found_location or 'Not specified'}\n\n"
                f"Please contact {finder_name} at {finder_email} to recover your item."
            ),
        },
    }

    try:
        resp = requests.post(EMAILJS_API_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"Match notification sent to {to_email}")
            return True
        else:
            print(f"EmailJS error: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
