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

PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
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
        text = text.strip()

        if text.lower() == "חדש":
            user_data[phone] = {"step": 0, "data": {}}
            return respond(phone, "השיחה אופסה ✅\n\nמה שמך המלא? (שם פרטי + שם משפחה)")

        if phone in user_data and user_data[phone]["step"] == "done":
            return "ok", 200

        if phone not in user_data:
            user_data[phone] = {"step": 0, "data": {}}
            return respond(phone, "שלום! 👋\nהגעת לבוט החכם של מוקד הידברות.\nנשמח לבדוק התאמה למשרה עבורך – זה לוקח פחות מדקה ⏱\n\nמה שמך המלא? (שם פרטי + שם משפחה)")

        step_index = user_data[phone]["step"]
        current_step = steps[step_index]

        if current_step == "full_name":
            if len(text.split()) < 2:
                return respond(phone, "נראה ששלחת רק שם אחד 😊\nאנא כתוב את *שמך המלא* (כולל שם משפחה)")
            user_data[phone]["data"]["full_name"] = text
            reply = f"נעים מאוד {text}!\nמה כתובת המגורים שלך? (רחוב + עיר)"

        elif current_step == "city":
            if len(text) < 5 or len(text.split()) < 2 or text.isdigit():
                return respond(phone, "נראה שכתובת המגורים ששלחת קצרה או לא ברורה 🏠\nאנא כתוב כתובת מלאה – לדוגמה: 'רחוב הרצל 12, ירושלים'")
            user_data[phone]["data"]["city"] = text
            loc_list = "\n".join([f"{i+1}. {loc}" for i, loc in enumerate(locations)])
            reply = f"אלו המוקדים שפתוחים כרגע לגיוס:\n\n{loc_list}\n\nלאיזה מוקד הכי נוח לך להגיע? (כתוב את שם העיר או מספר)"

        elif current_step == "location":
            selected = text
            if selected.isdigit():
                index = int(selected) - 1
                if 0 <= index < len(locations):
                    selected = locations[index]
                else:
                    return respond(phone, "אנא הקש מספר בין 1 ל־9 ✍️ או כתוב את שם העיר כפי שמופיע ברשימה")
            elif selected not in locations:
                return respond(phone, "לא זיהינו את שם העיר ששלחת 🤔\nאנא כתוב את *שם העיר בדיוק כפי שמופיע ברשימה* או הקש מספר בין 1 ל־9")
            user_data[phone]["data"]["location"] = selected
            reply = "מה מספר הטלפון שלך ליצירת קשר?"

        elif current_step == "phone":
            if not re.match(r"^05\d{8}$", text):
                return respond(phone, "נראה שמספר הטלפון ששלחת לא תקין 📱\nאנא כתוב מספר ישראלי בפורמט מלא, לדוגמה: 0521234567")
            user_data[phone]["data"]["phone"] = text
            reply = "ולסיום – כתובת המייל שלך?"

        elif current_step == "email":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", text):
                return respond(phone, "נראה שכתובת המייל לא תקינה 📧\nאנא נסה שוב עם כתובת תקינה לדוגמה: daniel@gmail.com")
            user_data[phone]["data"]["email"] = text
            reply = "ולפני סיום שאלה קטנה 😊\nהאם יש לך ניסיון קודם במוקד מכירות או מוקד התרמות?"

        elif current_step == "experience":
            user_data[phone]["data"]["experience"] = text
            respond(phone, "תודה רבה על המידע! 🙏\nהפרטים התקבלו ונחזור אליך בהקדם עם עדכון לגבי ההתאמה 😊")
            save_to_sheet(user_data[phone]["data"])
            closing = "הפרטים הועברו בהצלחה ✅\nנחזור אליך בהקדם בקשר לפרטים ששלחת.\nתודה רבה על פנייתך 🙏\nצוות מוקדי הידברות"
            user_data[phone]["step"] = "done"
            return respond(phone, closing)

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
            data.get("full_name", ""),
            data.get("city", ""),
            data.get("location", ""),
            data.get("phone", ""),
            data.get("experience", ""),
            data.get("email", ""),
            now,
            ""
        ]
        sheet.append_row(row)
        print("✅ Saved to Google Sheets")
    except Exception as e:
        print("❌ Error saving to sheet:", e)

if __name__ == "__main__":
    app.run(debug=True)
