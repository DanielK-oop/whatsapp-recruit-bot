from flask import Flask, request
import os
import requests
import datetime
import gspread
from google.oauth2.service_account import Credentials
import re

app = Flask(__name__)

user_data = {}
steps = ["full_name", "city", "location", "phone", "email", "experience"]

locations = [
    "פתח תקווה", "בני ברק", "ירושלים", "ביתר עלית", "בית שמש",
    "טבריה", "צפת", "נהריה", "נתיבות"
]

PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "704326896086247")
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "moked123")

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Unauthorized", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")
        if not messages:
            return "ok", 200

        message = messages[0]
        phone = message["from"]
        text = message["text"]["body"] if "text" in message else ""
        text = text.strip()
        now = datetime.datetime.now()

        # התחלה חדשה אם אין משתמש כלל
        if phone not in user_data:
            user_data[phone] = {
                "step": 0,
                "data": {},
                "last_active": now
            }
            return respond(phone, "שלום! 👋\nהגעת לבוט של מוקדי הידברות.\nנשמח לבדוק התאמה למשרה ✍️\n\nמה שמך המלא? (שם פרטי + שם משפחה)")

        # בדיקה אם עברו יותר מ־3 דקות
        last_time = user_data[phone].get("last_active", now)
        if isinstance(last_time, str):
            last_time = datetime.datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
        if (now - last_time).total_seconds() > 180:
            user_data[phone] = {
                "step": 0,
                "data": {},
                "last_active": now
            }
            return respond(phone, "שלום! 👋\nהתחלנו שיחה חדשה כי עבר זמן מה 🕒\nמה שמך המלא? (שם פרטי + שם משפחה)")

        # שיחה הסתיימה
