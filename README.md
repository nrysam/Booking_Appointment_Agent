# Booking Appointment Agent

This project implements a Booking Appointment Agent using OpenAI's GPT-4o-mini model. The agent can have human-like conversations to assist customers with booking appointments, checking availability, and canceling bookings. The agent is deployed using Google Cloud Run.

## Features

- **Human-like Conversations**: Utilizes OpenAI's GPT-4o-mini model to generate natural and engaging responses.
- **Appointment Booking**: Users can book appointments by providing necessary details such as date, time, name, email, and contact number.
- **Availability Check**: Users can inquire about available time slots for appointments.
- **Appointment Cancellation**: Users can cancel existing appointments by providing the booking details.
- **Firebase Integration**: Appointment data is stored in Firebase Realtime Database.
- **Backup and Recovery**: Supports local backups of appointment data.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- OpenAI API key
- Firebase service account key

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/nrysam/Booking_Appointment_Agent.git
   cd Booking_Appointment_Agent
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:

   Create a .env file in the root directory with the following content:

   ```env
   Copy code
   OPENAI_API_KEY=your_openai_api_key
   SERVICE_ACCOUNT_KEY_BASE64=your_base64_encoded_service_account_key
   ```
   
   The SERVICE_ACCOUNT_KEY_BASE64 is the base64 encoded content of your serviceAccountKey.json file from Firebase. This encoding is done to securely pass the contents of the service account key as an environment variable.
   You can encode it using the following command in Python:
   
   ```python
   import base64
   with open('path/to/serviceAccountKey.json', 'rb') as f:
       print(base64.b64encode(f.read()).decode())
   ```
   
6. **Run the application locally**:
   
   ```bash
   python app.py
   ```

### Deployment

#### Docker
1. **Build Docker Image**:

   ```bash
   docker build -t booking_appointment .
   ```
2. **Run Docker Container**:

   ```bash
   docker run -p 8080:8080 booking_appointment
   ```

#### Google Cloud Run
1. **Authenticate with Google Cloud**:

   ```bash
   gcloud auth login
   gcloud config set project your_project_id
   ```

2. **Build and push Docker image to Google Container Registry**:

   ```bash
   docker build -t gcr.io/your_project_id/booking_appointment .
   docker push gcr.io/your_project_id/booking_appointment
   ```
3. **Deploy to Google Cloud Run**:

   ```bash
   gcloud run deploy booking-appointment-service --image gcr.io/your_project_id/booking_appointment --platform managed --region us-central1 --allow-unauthenticated --project your-project-id
   ```

4. **Access the deployed service**:
    - Visit [Booking Appointment Agent](https://booking-appointment-service-uwgqlufcmq-uc.a.run.app/).

      
### Usage
1. Access the web interface:

   Open your browser and go to the URL provided by Google Cloud Run after deployment.

2. Interact with the agent:

   Start a conversation in the chat interface to book appointments, check availability, or cancel bookings.


## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](https://github.com/apache/.github/blob/main/LICENSE) file for details.
