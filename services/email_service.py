import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("EMAIL_HOST")
SMTP_PORT = int(os.getenv("EMAIL_PORT", 465))
YANDEX_EMAIL = os.getenv("EMAIL_HOST_USER")
YANDEX_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")


async def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg['From'] = YANDEX_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(YANDEX_EMAIL, YANDEX_PASSWORD)
        server.sendmail(YANDEX_EMAIL, to_email, msg.as_string())