import firebase_admin
from firebase_admin import credentials, db
import pandas as pd

# Initialize Firebase
def initialize_firebase(service_account_key_path):
    try:
        # Initialize Firebase
        cred = credentials.Certificate(service_account_key_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://booking-appointment-agent-default-rtdb.firebaseio.com/'
        })
        return True
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")
        return False

def load_appointments_from_csv(file_path='appointments.csv'):
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError:
        # If the file does not exist, create an empty DataFrame with the correct columns
        return pd.DataFrame(columns=['Name', 'Date', 'Start', 'End', 'Email', 'Contact Number', 'Booking Time'])

def save_appointments_to_firebase(df):
    ref = db.reference('appointments')
    ref.set(df.to_dict('records'))

def load_appointments_from_firebase():
    ref = db.reference('appointments')
    data = ref.get()
    if data:
        return pd.DataFrame(data)
    else:
        return load_appointments_from_csv()
    