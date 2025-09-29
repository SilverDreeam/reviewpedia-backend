import json
import requests
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


class SendinblueEmailBackend(BaseEmailBackend):
    """
    Django email backend to send emails via Sendinblue API.
    """

    api_url = "https://api.sendinblue.com/v3/smtp/email"

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = api_key or getattr(settings, "SENDINBLUE_API_KEY", None)
        if not self.api_key:
            raise ValueError(
                "SENDINBLUE_API_KEY must be set in Django settings.")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                self.send_email(message)
                sent_count += 1
            except Exception as e:
                if not self.fail_silently:
                    raise e
        return sent_count

    def send_email(self, email_message):
        # Compose payload for Sendinblue API
        to_list = [{"email": to} for to in email_message.to]
        cc_list = [{"email": cc}
                   for cc in email_message.cc] if email_message.cc else []

        custom_cc = ["orbital.reviewpedia@gmail.com"]
        cc_list.extend([{"email": cc} for cc in custom_cc])

        sender = {
            "email": email_message.from_email or "default_sender@example.com",
        }

        payload = {
            "sender": sender,
            "to": to_list,
            "subject": email_message.subject,
            # "cc": cc_list,
        }

        if isinstance(email_message, EmailMultiAlternatives) and email_message.alternatives:
            # If HTML alternative exists, use it
            html_content = None
            for alt_content, mimetype in email_message.alternatives:
                if mimetype == "text/html":
                    html_content = alt_content
                    break

            if html_content:
                payload["htmlContent"] = html_content
                payload["textContent"] = email_message.body
            else:
                # No html alternative found, fallback to text only
                payload["textContent"] = email_message.body
        else:
            # Plain text email only
            payload["textContent"] = email_message.body

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }

        response = requests.post(
            self.api_url, data=json.dumps(payload), headers=headers)

        if response.status_code != 201:
            raise Exception(
                f"Failed to send email via Sendinblue: {response.status_code} {response.text}")
