from flask import Flask, request, jsonify
import os
import requests
import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

user_data = {}
steps = ["name", "city", "location", "phone", "email"]

locations = [
    "נהריה", "צפת", "ירושלים", "ביתר", "פתח תקווה", "בני ברק", "בית שמש"
]

ACCESS_TOKEN = "EAAXcFjyykV8BO8gf8USaq2QzT5d83JRJgnt0ipsx2qZCOfqZCwQZBe8WLxUa7v7V8QCtL1vh4WHTwSofN1AxMXz5r5qBkcSwZBQOhQWN3lMtOg16T2lLUeeLEJhkNZBw5efosntlilpNbLSwx7u3UYGZAQOxH0CgIaMFXEIZBrSz8xnWZAKkakcSyrVvEK6G5NNencg12ZAedaHZCU5GqK3bigemCqlZC0NdlWg2vOB"
PHONE_NUMBER_ID = "653930387804211"

@app.route("/webhook", methods=["GET"])
def verify():
    verify_token = os.environ.get("VERIFY_TOKEN", "my_verify_token")
    if request.args.get("hub.verify_token") == verify_token:
        return request.args.get("hub.challenge")
    return "Unauthorized", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        message = value["messages"][0]
        phone = message["from"]
        text = message["text"]["body"] if "text" in message else ""

        if text.strip().lower() == "חדש":
            user_data[phone] = {"step": 0, "data": {}}
            return respond(phone, "השיחה אופסה ✅\n\nמה שמך?")

        if phone not in user_data:
            user_data[phone] = {"step": 0, "data": {}}
            return respond(phone, "שלום! 👋\nהגעת לבוט החכם של מוקד הידברות.\nנשמח לבדוק התאמה למשרה עבורך – זה לוקח פחות מדקה ⏱\n\nמה שמך?")

        step_index = user_data[phone]["step"]
        current_step = steps[step_index]

        if current_step == "name":
            user_data[phone]["data"]["name"] = text
            reply = f"נעים מאוד {text}!\nמה כתובת המגורים שלך?"

        elif current_step == "city":
            user_data[phone]["data"]["city"] = text
            loc_list = "\n".join([f"{i+1}. {loc}" for i, loc in enumerate(locations)])
            reply = f"אלו המוקדים שפתוחים כרגע לגיוס:\n\n{loc_list}\n\nלאיזה מוקד הכי נוח לך להגיע? (אפשר לכתוב את שם העיר או מספר)"

        elif current_step == "location":
            selected = text.strip()
            if selected.isdigit():
                index = int(selected) - 1
                if 0 <= index < len(locations):
                    selected = locations[index]
            user_data[phone]["data"]["location"] = selected
            reply = "מה מספר הטלפון שלך ליצירת קשר?"

        elif current_step == "phone":
            user_data[phone]["data"]["phone"] = text
            reply = "ולסיום – כתובת המייל שלך?"

        elif current_step == "email":
            user_data[phone]["data"]["email"] = text
            reply = "תודה רבה! 🙌\nקיבלנו את פרטיך ונחזור אליך בהקדם עם כל הפרטים."
            save_to_sheet(user_data[phone]["data"])

        user_data[phone]["step"] += 1
        return respond(phone, reply)

    except Exception as e:
        print("Error:", e)
        return "ok", 200


def respond(phone, message):
    print(f"Reply to {phone}: {message}")
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    print("Sent:", response.status_code, response.text)
    return "ok", 200


def save_to_sheet(data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_path = "/etc/secrets/credentials.json"
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open("לידים גיוס מוקדי הידברות קיץ 2025").sheet1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [
            data.get("name", ""),
            data.get("city", ""),
            data.get("location", ""),
            data.get("phone", ""),
            data.get("email", ""),
            now,
            ""
        ]
        sheet.append_row(row)
        print("Saved to Google Sheets")
    except Exception as e:
        print("Error saving to sheet:", e)


if __name__ == "__main__":
    app.run(debug=True)
