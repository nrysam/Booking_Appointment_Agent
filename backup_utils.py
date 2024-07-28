import shutil
from datetime import datetime

def create_backup(file_path='appointments.csv', backup_dir='backup'):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'{backup_dir}/appointments_backup_{timestamp}.csv'
    shutil.copy(file_path, backup_path)
