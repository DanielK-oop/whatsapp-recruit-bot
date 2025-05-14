from flask import Flask, request, jsonify
import os
import requests
import datetime
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

user_data = {}
steps = ["name", "city", "location", "phone", "email", "experience"]

locations = [
    "פתח תקווה",
    "בני ברק",
    "ירושלים",
    "ביתר עלית",
    "בית שמש",
    "טבריה",
    "צפת",
    "נהריה",
    "נתיבות"
]

PHONE_NUMBER_ID = "653930387804211"
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")

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
            reply = "מה הכתובת מייל שלך ?"

        elif current_step == "email":
            user_data[phone]["data"]["email"] = text
            reply = "ולסיום שאלה קטנה 😊\nהאם יש לך ניסיון קודם במוקד מכירות או מוקד התרמות?"

        elif current_step == "experience":
            user_data[phone]["data"]["experience"] = text
            reply = "תודה רבה על המידע! 🙏\nהפרטים התקבלו ונחזור אליך בהקדם עם עדכון לגבי ההתאמה 😊"
            save_to_sheet(user_data[phone]["data"])

        user_data[phone]["step"] += 1
        return respond(phone, reply)

    except Exception as e:
        print("❌ Error:", e)
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
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_path = "/etc/secrets/credentials.json"
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open("לידים-מוקדים").worksheet("גיליון1")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [
            data.get("name", ""),        # A
            data.get("city", ""),        # B
            data.get("location", ""),    # C
            data.get("phone", ""),       # D
            data.get("experience", ""),  # E
            data.get("email", ""),       # F
            now,                         # G
            ""                           # H (הערות)
        ]
        sheet.append_row(row)
        print("✅ Saved to Google Sheets")
    except Exception as e:
        print("❌ Error saving to sheet:", e)

if __name__ == "__main__":
    app.run(debug=True)
