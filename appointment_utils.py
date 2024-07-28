import pandas as pd
from datetime import datetime

def load_appointments(file_path='appointments.csv'):
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError:
        # If the file does not exist, create an empty DataFrame with the correct columns
        return pd.DataFrame(columns=['Name', 'Date', 'Start', 'End', 'Email', 'Contact Number', 'Booking Time'])

def save_appointments_local(df, file_path='appointments.csv'):
    df.to_csv(file_path, index=False)

def update_appointments(df, new_appointment):
    new_appointment_df = pd.DataFrame([new_appointment])
    df = pd.concat([df, new_appointment_df], ignore_index=True)
    return df

def check_availability(df, date, start, end):
    start_time = datetime.strptime(start, '%H:%M').time()
    end_time = datetime.strptime(end, '%H:%M').time()

    appointments_on_date = df[df['Date'] == date]
    for _, row in appointments_on_date.iterrows():
        row_start_time = datetime.strptime(row['Start'], '%H:%M:%S').time()
        row_end_time = datetime.strptime(row['End'], '%H:%M:%S').time()
        if not (end_time <= row_start_time or start_time >= row_end_time):
            return False
    return True
