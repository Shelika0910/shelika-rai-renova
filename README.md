# ReNova
ReNova is a comprehensive web-based mental health platform designed to connect patients with professional therapists while promoting emotional well-being through digital tools. The system integrates real-time communication, AI support, secure payments, and personalized wellness tracking in a single platform. It supports multiple user roles including patients, therapists, and administrators, ensuring a structured and secure environment for mental health care.


## Project Objective
The main objective of this project is to develop a secure and user-friendly mental health platform that:
- Provide accessible mental health support digitally
- Enable secure communication between patients and therapists
- Offer personalized wellness tracking and insights
- Integrate modern technologies such as AI chatbot and real-time communication

## Features

**Shared Platform Features**
- Public home page and contact form  
- Email-based authentication system  
  - Register, Login, Logout  
  - Email verification (OTP)  
  - Forgot password (OTP)  
  - Django password reset  
- Google OAuth2 social login  
- Terms & Conditions acceptance enforcement  
- Role-based dashboard (Patient / Therapist)  
- Real-time notifications system  
- Secure 1:1 messaging with read receipts
- Live therapy rooms with:
  - WebSocket chat  
  - Audio/Video call signaling  
- eSewa payment integration  
- AI chatbot powered by Google Gemini  
- YouTube-based wellness resources with watch tracking  
- SMTP email system for verification and contact  

**Patient Features**
- One-time mental health MCQ assessment with category scoring  
- Personalized dashboard including:
  - Recommended therapists  
  - Daily motivational quotes  
  - Wellness tips  
  - Upcoming appointments & programs  
- Therapist discovery with:
  - Search  
  - Specialization filters  
  - Ratings & availability  
- Therapist profile viewing:
  - Booked slots  
  - Days off  
  - Ratings  
  - Completed sessions  
- Appointment booking:
  - Date, time, duration, session type  
  - Private notes  
- Duration-based session pricing  
- Appointment management:
  - View, cancel, reschedule  
  - Track requested, upcoming, past, missed, cancelled sessions  
- eSewa payment integration for sessions  
- Session status tracking (payment, refund, cancellation)  
- Therapist rating after sessions  
- Wellness resources (category-based videos)  
- Personalized video watch tracking  
- AI chatbot with multiple chat sessions & history  
- Daily activity logging:
  - Tasks  
  - Challenges  
  - Mood tracking  
- Patient profile management  
- Session report viewing  
- Messaging system with therapists  
- Join live therapy sessions  
- Notification center  

**Therapist Features**
- Therapist account requires admin approval  
- Dashboard showing:
  - Today's sessions  
  - Upcoming sessions  
  - Pending requests  
  - Total patients  
  - Completed sessions  
  - Reports count  
  - Earnings  
- Appointment management:
  - Accept/reject requests  
  - Mark sessions as completed  
- Availability management:
  - Weekly schedule  
  - Multiple time slots  
  - Days off  
- Session report management:
  - Summary  
  - Diagnosis notes  
  - Treatment plan  
  - Mood & progress rating  
  - Homework  
  - Private notes  
  - File attachments  
- Client management:
  - View profiles  
  - Appointment history  
  - MCQ results  
  - Mood/progress trends  
- Secure messaging with patients  
- Live therapy session access  
- Profile editing  
- Monthly payout tracking  
- Notifications and unread message counters  


## Technologies Used

**Frontend**
- HTML
- CSS
- JavaScript
- Django Templates

**Backend**
- Python
- Django
- Django Channels (Daphne) for WebSockets
- Celery (Task Queue)
- Google Generative AI integration

**Database**
- SQLite (Default `db.sqlite3` for development)

**Integrations**
- Google OAuth2  
- eSewa Payment Gateway  
- Google Gemini AI  
- YouTube API  

**Deployment**
- *To be determined (e.g., Vercel / Render / Railway)*

## System Requirements

**Hardware**
- Computer / Smartphone  
- Stable Internet Connection  

**Software**
- Web browser such as Google Chrome, Firefox, or Safari
- Python 3.x

## Installation and Setup
Steps to run the project locally.

1. **Clone the repository**
   ```bash
   git clone https://github.com/username/ReNova.git
   ```

2. **Go to the project folder**
   ```bash
   cd ReNova
   ```

3. **Set up virtual environment & Install required dependencies**
   ```bash
   python -m venv myenv
   # On Windows
   myenv\Scripts\activate
   # On macOS/Linux
   source myenv/bin/activate
   
   pip install -r requirements.txt
   ```

4. **Navigate to the Django project directory and run migrations**
   ```bash
   cd renova
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Run the application**
   ```bash
   python manage.py runserver
   ```

## Live Project
Live URL of the deployed system:
*(Add your live URL here once deployed)*
Example:
https://yourprojectlink.com

## Project Structure
```text
ReNova/
│
├── renova/                 # Main Django Django project settings
├── renova/accounts/        # Primary Django app (views, models, chatbot, services)
│   ├── templates/          # Frontend HTML templates
├── media/                  # User-uploaded media like profile images
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

## Screenshots
*Add some screenshots of the system here.*
Example:
- Login page
- Dashboard
- Chatbot interaction page
- Main feature pages

## Future Improvements
Possible improvements for the system:
- Improved user interface and animations
- Additional security features (2FA)
- More advanced analytics for user interactions
- Scalable database migration (MySQL) for production

## Authors
Shelika Rai
Student - Final Year Project
Itahari International College

## License
This project is created for educational purposes as part of a Final Year Project.
