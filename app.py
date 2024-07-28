import os
import openai
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
import appointment_utils
import backup_utils
import firebase_utils
import re
from flask import Flask, request, jsonify, render_template, session
import base64
import json
import tempfile

# Load environment variables
_ = load_dotenv(find_dotenv())
openai.api_key = os.getenv('OPENAI_API_KEY')

# Retrieve the service account key from environment variables
service_account_key_base64 = os.getenv('SERVICE_ACCOUNT_KEY_BASE64')

# Decode the base64 service account key
service_account_key_json = base64.b64decode(service_account_key_base64).decode()

# Create a temporary directory
tmpdirname = tempfile.mkdtemp()
# Write the decoded service account key JSON to a file
service_account_key_path = os.path.join(tmpdirname, 'serviceAccountKey.json')
with open(service_account_key_path, 'w') as key_file:
    key_file.write(service_account_key_json)

# Initialize Firebase with the service account key
if not firebase_utils.initialize_firebase(service_account_key_path):
    raise Exception("Failed to initialize Firebase")

# Load appointments from Firebase at the start
df = firebase_utils.load_appointments_from_firebase()

# Initialize context dictionary
context = {}

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

def get_completion_from_messages(messages, model="gpt-4o-mini", temperature=0.2, max_tokens=250):
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature, 
        max_tokens=max_tokens, 
    )
    return response.choices[0].message["content"]

def get_dates():
    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    next_monday = today + timedelta(days=-today.weekday(), weeks=1)
    next_week = [next_monday + timedelta(days=i) for i in range(7)]
    return {
        "today": today.strftime('%Y-%m-%d'),
        "tomorrow": tomorrow.strftime('%Y-%m-%d'),
        "next_week": [day.strftime('%Y-%m-%d') for day in next_week]
    }

def get_date_from_day_name(day_name):
    today = datetime.today()
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_day = days_of_week.index(day_name.lower())
    current_day = today.weekday()
    if target_day >= current_day:
        days_until_target = target_day - current_day
    else:
        days_until_target = 7 - (current_day - target_day)
    target_date = today + timedelta(days=days_until_target)
    return target_date.strftime('%Y-%m-%d')

def handle_relative_time(relative_time):
    now = datetime.now()
    
    if relative_time.lower() == "later today":
        return now.strftime('%Y-%m-%d')
    
    elif relative_time.lower() == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.strftime('%Y-%m-%d')
    
    elif relative_time.lower() == "next week":
        next_week = now + timedelta(weeks=1)
        return next_week.strftime('%Y-%m-%d')
    
    elif relative_time.lower().startswith("next"):
        days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        today_index = now.weekday()
        day_name = relative_time.lower().split("next ")[1]
        if day_name in days_of_week:
            target_index = days_of_week.index(day_name)
            delta_days = (target_index - today_index + 7) % 7
            target_date = now + timedelta(days=delta_days + 7)
            return target_date.strftime('%Y-%m-%d')
    
    else:
        days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        today_index = now.weekday()
        if relative_time.lower() in days_of_week:
            target_index = days_of_week.index(relative_time.lower())
            delta_days = (target_index - today_index + 7) % 7
            target_date = now + timedelta(days=delta_days)
            return target_date.strftime('%Y-%m-%d')
    
    return now.strftime('%Y-%m-%d')

def find_available_slots(date):
    date = pd.to_datetime(date).strftime('%Y-%m-%d')
    print(f"Checking availability for date: {date}")
    
    working_hours = pd.date_range(start='09:00', end='18:00', freq='30min').time
    appointments = df[df['Date'] == date]
    print(f"Appointments on {date}: {appointments}")
    
    booked_slots = [(row['Start'], row['End']) for _, row in appointments.iterrows()]
    print(f"Booked slots: {booked_slots}")

    available_slots = []
    slot_start = None

    for slot in working_hours:
        slot_str = slot.strftime('%H:%M:%S')
        is_booked = any(start <= slot_str < end for start, end in booked_slots)
        if not is_booked:
            if slot_start is None:
                slot_start = slot
        else:
            if slot_start is not None:
                available_slots.append(f"{slot_start.strftime('%I:%M %p')} - {slot.strftime('%I:%M %p')}")
                slot_start = None

    if slot_start is not None and slot_start.strftime('%H:%M:%S') != '18:00:00':
        available_slots.append(f"{slot_start.strftime('%I:%M %p')} - 06:00 PM")

    print(f"Available slots: {available_slots}")
    
    return available_slots

def check_availability(df, date, start, end):
    date = pd.to_datetime(date).strftime('%Y-%m-%d')
    start = pd.to_datetime(start, format='%H:%M:%S').strftime('%H:%M:%S')
    end = pd.to_datetime(end, format='%H:%M:%S').strftime('%H:%M:%S')
    
    print(f"Checking availability: Date: {date}, Start: {start}, End: {end}")
    
    day_appointments = df[df['Date'] == date]
    
    for _, row in day_appointments.iterrows():
        if (start < row['End'] and end > row['Start']):
            return False
    return True

def save_appointments(df):
    return firebase_utils.save_appointments_to_firebase(df), appointment_utils.save_appointments_local(df), backup_utils.create_backup()

def cancel_booking(df, name, date, email):
    df_filtered = df[(df['Name'] == name) & (df['Date'] == date) & (df['Email'] == email)]
    if df_filtered.empty:
        return df, False
    df = df.drop(df_filtered.index)
    return df, True

def call_assistant_function(intent, user_data):
    global df, context

    if intent == 'check_availability':
        date = user_data.get('date')
        if not date:
            date = handle_relative_time(user_data.get('relative_time'))
        
        print(f"Checking availability for date: {date}")
        available_slots = find_available_slots(date)
        context['last_available_slots'] = available_slots
        context['last_date'] = date
        return f"Available slots for {date}: {available_slots}. Would you like to book one of these slots, or would you prefer to consider another date?"
    
    elif intent == 'book_appointment':
        date = user_data.get('date') or context.get('last_date')
        start = user_data.get('start')
        end = user_data.get('end')
        
        if not date or not start or not end:
            return "Please provide the date, start time, and end time for the booking."
        
        print(f"Booking request: Date: {date}, Start: {start}, End: {end}")
        
        if not check_availability(df, date, start, end):
            available_slots = find_available_slots(date)
            return f"Sorry, the slot from {start} to {end} on {date} is not available. Available slots: {available_slots}. Would you like to book one of these?"
        else:
            name = user_data.get('name') or context.get('name')
            email = user_data.get('email') or context.get('email')
            contact_number = user_data.get('contact_number') or context.get('contact_number')
            booking_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if not name or not email or not contact_number:
                context['pending_booking'] = {'date': date, 'start': start, 'end': end}
                return "Please provide your name, email, and contact number for the booking."

            new_appointment = {
                'Name': name,
                'Date': date,
                'Start': start,
                'End': end,
                'Email': email,
                'Contact Number': contact_number,
                'Booking Time': booking_time
            }
            
            df = appointment_utils.update_appointments(df, new_appointment)
            save_appointments(df)
            
            return f"Booking confirmed for {name} on {date} from {start} to {end}."

    elif intent == 'cancel_appointment':
        name = user_data.get('name')
        date = user_data.get('date')
        email = user_data.get('email')

        if not name or not date or not email:
            return "Please provide your name, date of the booking, and email to cancel the booking."
        
        print(f"Cancellation request: Name: {name}, Date: {date}, Email: {email}")
        
        df, success = cancel_booking(df, name, date, email)
        
        if success:
            save_appointments(df)
            return f"Booking for {name} on {date} has been successfully cancelled."
        else:
            return f"No booking found for {name} on {date} with the email {email}."

    else:
        return "Sorry, I didn't understand your request."

def extract_times(time_str):
    time_range = time_str.lower().split(' to ')
    if len(time_range) == 2:
        start_time = time_range[0].strip()
        end_time = time_range[1].strip()
        
        if 'am' in start_time or 'pm' in start_time:
            start_time = pd.to_datetime(start_time, format='%I %p').strftime('%H:%M:%S')
        else:
            start_time = pd.to_datetime(start_time, format='%H').strftime('%H:%M:%S')

        if 'am' in end_time or 'pm' in end_time:
            end_time = pd.to_datetime(end_time, format='%I %p').strftime('%H:%M:%S')
        else:
            end_time = pd.to_datetime(end_time, format='%H').strftime('%H:%M:%S')

        return start_time, end_time
    return None, None

def extract_booking_details(response):
    date_pattern = r"(\d{4}-\d{2}-\d{2})"
    time_pattern = r"(\d{2}:\d{2}:\d{2})"
    name_pattern = r"([A-Za-z]+(?: [A-Za-z]+)*)"
    email_pattern = r"Email: (\S+@\S+\.\S+)"
    contact_pattern = r"(\d{10})"

    date_match = re.search(date_pattern, response)
    start_match, end_match = extract_times(response)
    name_match = re.search(name_pattern, response)
    email_match = re.search(email_pattern, response)
    contact_match = re.search(contact_pattern, response)

    booking_details = {}

    if date_match:
        booking_details['date'] = date_match.group(1)
    if start_match and end_match:
        booking_details['start'] = start_match
        booking_details['end'] = end_match
    if name_match:
        booking_details['name'] = name_match.group(1)
    if email_match:
        booking_details['email'] = email_match.group(1)
    if contact_match:
        booking_details['contact_number'] = contact_match.group(1)

    return booking_details


def extract_cancellation_details(response):
    name_pattern = r"Name: ([a-zA-Z\s]+)"
    date_pattern = r"(\d{4}-\d{2}-\d{2})"
    email_pattern = r"Email: (\S+@\S+\.\S+)"

    name_match = re.search(name_pattern, response)
    date_match = re.search(date_pattern, response)
    email_match = re.search(email_pattern, response)

    cancellation_details = {}
    
    if name_match:
        cancellation_details['name'] = name_match.group(1)
    if date_match:
        cancellation_details['date'] = date_match.group(1)
    if email_match:
        cancellation_details['email'] = email_match.group(1)

    return cancellation_details

def detect_intent_and_extract_data(query, context=None):
    intent_message = [
        {"role": "system", "content": "You are an intent detection assistant. Identify the intent (check_availability, book_appointment, cancel_appointment) and relevant details (date, start_time, end_time, name, email, contact number) from the user query. If the user provides contact number, assume the intent is book_appointment."},
        {"role": "user", "content": query}
    ]
    intent_response = get_completion_from_messages(intent_message, model="gpt-4o-mini", temperature=0.2, max_tokens=100)
    
    print("Intent Response:", intent_response)
    
    intents = ["check_availability", "book_appointment", "cancel_appointment"]
    detected_intent = None
    for intent in intents:
        if intent in intent_response.lower():
            detected_intent = intent
            break

    print("Detected Intent:", detected_intent)

    user_data = {}
    
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", query)
    contact_match = re.search(r"\b\d{10}\b", query)
    
    if email_match:
        user_data['email'] = email_match.group(0)
    if contact_match:
        user_data['contact_number'] = contact_match.group(0)
    
    if user_data.get('contact_number'):
        detected_intent = "book_appointment"
    
    if detected_intent == "check_availability":
        date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
        date_match = date_pattern.search(query)
        if date_match:
            user_data['date'] = date_match.group(0)
        else:
            relative_time_patterns = ["later today", "tomorrow", "next week", "next [a-zA-Z]+", "(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"]
            for pattern in relative_time_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    user_data['relative_time'] = match.group(0)
                    break
    elif detected_intent == "book_appointment":
        name_match = re.search(r"(\b[A-Za-z]+(?: [A-Za-z]+)+\b)", query)
        if name_match:
            user_data['name'] = name_match.group(0)
        user_data.update(extract_booking_details(query))
        if context and context.get('last_date') and not user_data.get('date'):
            user_data['date'] = context['last_date']
        
        time_pattern = re.compile(r"(\d{1,2}(:\d{2})?\s?(am|pm)?)\s?to\s?(\d{1,2}(:\d{2})?\s?(am|pm)?)", re.IGNORECASE)
        time_match = time_pattern.search(query)
        if time_match:
            start_time, end_time = extract_times(time_match.group())
            if start_time and end_time:
                user_data['start'] = start_time
                user_data['end'] = end_time
        
        # Preserve start and end times in context
        if context:
            if 'start' in user_data:
                context['start'] = user_data['start']
            if 'end' in user_data:
                context['end'] = user_data['end']
        
    elif detected_intent == "cancel_appointment":
        user_data.update(extract_cancellation_details(query))

    print("Extracted User Data:", user_data)
    
    if 'relative_time' in user_data and user_data['relative_time'].lower() in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        user_data['date'] = get_date_from_day_name(user_data['relative_time'])
        del user_data['relative_time']
    
    return detected_intent, user_data

# Handle user query
def handle_user_query(query):
    detected_intent, user_data = detect_intent_and_extract_data(query, context)
    
    if detected_intent:
        if detected_intent == 'check_availability' and context.get('last_date'):
            context['last_date'] = None
        
        # Retain context for booking details
        if detected_intent == 'book_appointment':
            if context.get('last_date'):
                user_data['date'] = context.get('last_date')
            if context.get('start') and 'start' not in user_data:
                user_data['start'] = context.get('start')
            if context.get('end') and 'end' not in user_data:
                user_data['end'] = context.get('end')
            if 'start' in user_data and 'end' in user_data:
                context['start'] = user_data['start']
                context['end'] = user_data['end']
        
        response = call_assistant_function(detected_intent, user_data)
    else:
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query}
        ]
        response = get_completion_from_messages(messages)
    
    return response


dates = get_dates()

system_message = f"""
You are Booking Appointment Agent, an automated service for booking appointments.
Your role is to assist customers with booking appointments, checking availability, and canceling bookings.

Follow these steps to assist customers:

1. **Greeting and Understanding the Query**:
   - Greet the customer warmly at the beginning.
   - Ask if they want to book an appointment, cancel a booking, or inquire about availability.
   - Remind the customer that bookings are only accepted from 9 AM to 6 PM.
   - Understand whether the customer wants to book an appointment, cancel a booking, or make an inquiry.

2. **Checking Availability**:
   - If the customer asks for specific dates or relative times without giving a specific time (e.g., "later today", "tomorrow", "Saturday", "next Monday"):
     - Interpret the asked date or day into a specific date in the "Month Date, Year" or "%Y-%m-%d" format.
     - Use the `find_available_slots(date)` function with the interpreted date to find available slots on that day.
     - Inform the customer of the available slots on that day, specifying the day.
   - If the customer asks for specific dates with a specific time range:
     - Check its availability using the `check_availability(df, date, start, end)` function.
     - If the asked time is unavailable, inform the customer of available slots using the `find_available_slots(date)` function and ask if they want to change the time or date.
   - If the proposed date is fully booked, inform the customer and ask for an alternative date.
   - Accept various time formats (e.g., "4 to 6 pm", "from 4 PM to 6 PM", "2 to 5").
   - Assume times provided without AM or PM as PM for times between 1 to 6.

3. **Collecting Customer Details**:
   - Once a slot is confirmed, collect the customer's name, email, and contact number.
   - Ask for any missing information if needed.

4. **Confirmation and Data Entry**:
   - Confirm all details (name, date, time, email, contact number) with the customer, specifying the day of the week.
   - After the customer confirms, verify availability once more.
   - If the slot is available, save the booking data using the `save_appointments(df)` function.
   - Inform the customer that the appointment has been booked.

5. **Booking Cancellation**:
   - Ask for the customer's name and the date of the booking they want to cancel.
   - Ask for the customer's email.
   - Verify the provided data with the database using the `cancel_booking(df, name, date, email)` function.
   - Confirm the cancellation with the customer.
   - Delete the booking from the database using the `cancel_booking(df, name, date, email)` function.
   - Save the latest appointments data using the `save_appointments(df)` function.
   - Notify the customer whether the cancellation was successful or not.

6. **Date Management**:
   - Today is {dates['today']}.
   - Tomorrow is {dates['tomorrow']}.
   - The dates for the next week (starting from Monday) are: {dates['next_week']}.

7. **Error Handling**:
   - Handle invalid dates/times and incomplete data gracefully.
   - Ask the customer for necessary information if any details are missing.

8. **Maintaining Conversation Context**:
   - Maintain the conversation context to avoid repeated information requests.
   - Continue from the previous conversation smoothly.

9. **Data Privacy**:
   - Never share another customer's data with the user.

Respond in a concise, friendly, and conversational style to ensure a smooth and pleasant booking experience for the customer.
"""

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_query = data.get('message', {}).get('content', '')
    user_id = data.get('message', {}).get('id', '')

    if user_query.lower() in ["exit", "quit"]:
        return jsonify({"message": {"content": "Exiting chatbot. Goodbye!", "id": user_id}})

    response = handle_user_query(user_query)
    return jsonify({"message": {"content": response, "id": user_id}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
