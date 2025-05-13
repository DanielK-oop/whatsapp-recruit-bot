from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# זיכרון זמני לשמירת הנתונים (בהמשך נחבר ל-Google Sheets)
user_data = {}

# שלבי שיחה לפי סדר
steps = ["name", "city", "location", "cv_question", "cv", "email", "phone"]

locations = [
    "נהריה", "צפת", "ירושלים", "ביתר", "פתח תקווה", "בני ברק", "בית שמש"
]

@app.route("/webhook", methods=["GET"])
def verify():
    # זה רק לצורך החיבור הראשוני מול Meta
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

        # אתחל אם המשתמש חדש
        if phone not in user_data:
            user_data[phone] = {"step": 0, "data": {}}

        step_index = user_data[phone]["step"]
        current_step = steps[step_index]

        if current_step == "name":
            user_data[phone]["data"]["name"] = text
            reply = "מה מקום מגוריך?"

        elif current_step == "city":
            user_data[phone]["data"]["city"] = text
            loc_list = "\n".join([f"{i+1}. {loc}" for i, loc in enumerate(locations)])
            reply = f"לאיזה מוקד תרצה להצטרף? נא לבחור מספר:\n{loc_list}"

        elif current_step == "location":
            try:
                index = int(text.strip()) - 1
                if 0 <= index < len(locations):
                    user_data[phone]["data"]["location"] = locations[index]
                    reply = "האם יש לך קובץ קורות חיים להעלות? (כן/לא)"
                else:
                    reply = "נא לבחור מספר תקף מהרשימה."
                    return respond(phone, reply)
            except:
                reply = "נא להכניס מספר בלבד לבחירת המוקד."
                return respond(phone, reply)

        elif current_step == "cv_question":
            if text.strip().lower() in ["כן", "yes"]:
                reply = "נא לצרף את קובץ קורות החיים שלך (PDF / Word)"
            else:
                user_data[phone]["data"]["cv"] = "לא סופק"
                user_data[phone]["step"] += 1  # דילוג על שלב הקובץ
                reply = "מה כתובת האימייל שלך?"
                return respond(phone, reply)

        elif current_step == "cv":
            if "document" in message:
                user_data[phone]["data"]["cv"] = message["document"]["filename"]
                reply = "מה כתובת האימייל שלך?"
            else:
                reply = "נא לשלוח קובץ קורות חיים (ולא טקסט)."
                return respond(phone, reply)

        elif current_step == "email":
            user_data[phone]["data"]["email"] = text
            reply = "מה מספר הטלפון שלך?"

        elif current_step == "phone":
            user_data[phone]["data"]["phone"] = text
            reply = "תודה רבה! פרטיך התקבלו ונחזור אליך בהקדם."

        user_data[phone]["step"] += 1
        return respond(phone, reply)

    except Exception as e:
        print("Error:", e)
        return "ok", 200


def respond(phone, message):
    print(f"Reply to {phone}: {message}")
    # בהמשך נוסיף שליחה אמיתית ל-API של וואטסאפ
    return "ok", 200


if __name__ == "__main__":
    app.run(debug=True)
