# SwimSyncEDU

SwimSyncEDU is a Django-based swimming class management system developed as a Final Year Project (FYP). It brings pool discovery, class booking, trainer management, attendance tracking, payments, certificates, and reviews into one role-based web platform for swimming centers and learners.

## Project Overview

Traditional swimming class administration often relies on manual record keeping, scattered communication, and paper-based tracking. SwimSyncEDU digitizes these workflows through a centralized system for:

- members who want to find pools, book classes, and track progress
- trainers who manage classes, attendance, certificates, and student activity
- administrators who oversee operations, trainers, pools, payments, and reports

The platform is designed to improve operational efficiency, reduce scheduling friction, and create a better experience for both swimming centers and students.

## Key Features

### Public and Member Features

- browse the landing page and discover platform offerings
- view nearby pools and pool details
- explore class types and available class sessions
- book group classes and private classes
- manage bookings from a personal dashboard
- view payment records and learning progress
- reset passwords through email-based recovery

### Trainer Features

- access a dedicated trainer dashboard
- manage assigned classes and private sessions
- mark student attendance
- view enrolled students
- issue completion certificates
- review student feedback and ratings

### Admin Features

- manage members and trainers
- create and manage class types and class sessions
- manage private class pricing
- assign trainers to pools
- monitor trainer attendance and substitute handling
- record daily pool quality data
- view payment and activity reports
- oversee certificates and reviews

### System Features

- custom authentication with role-based access control
- MySQL-backed data persistence
- image upload support for profile pictures, signatures, and pool images
- Cloudinary media storage in production
- WhiteNoise static file serving
- Khalti payment gateway integration
- Google Maps support for location-based pool discovery
- realistic demo data seeding for presentations and testing

## Modules

The project is organized into multiple Django apps:

- `accounts` - authentication, user roles, profiles, and demo data commands
- `classes` - group classes, private classes, bookings, and pricing
- `pool` - pools, pool images, water quality, and trainer-pool assignment
- `attendance` - trainer, group class, and private class attendance
- `payments` - payment records and gateway workflow
- `certificate` - completion certificate issuance
- `reviews` - trainer review and rating system

## Tech Stack

- Backend: Django 5
- Language: Python
- Database: MySQL
- Frontend: HTML, CSS, JavaScript, Django Templates
- Media Storage: Cloudinary
- Static File Serving: WhiteNoise
- Payments: Khalti
- Location Services: Google Maps API, Geopy

## Database and Roles

SwimSyncEDU uses a custom user model with three primary roles:

- `admin`
- `trainer`
- `user`

Core entities in the system include:

- users and trainer profiles
- pools and pool quality records
- class types and scheduled class sessions
- class bookings and private classes
- trainer attendance and student attendance
- payments
- completion certificates
- reviews

## Project Structure

```text
SwimSyncEDU/
|-- accounts/
|-- attendance/
|-- certificate/
|-- classes/
|-- payments/
|-- pool/
|-- reviews/
|-- static/
|-- templates/
|-- media/
|-- swimsyncedu/
|-- manage.py
|-- requirements.txt
`-- README.md
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Rinji47/SwimSyncEDU.git
cd SwimSyncEDU
```

### 2. Create and activate a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure MySQL

Create a MySQL database for the project, for example:

```sql
CREATE DATABASE swimsyncedu;
```

### 5. Add environment variables

Create a `.env` file in the project root and add the required configuration:

```env
SECRET_KEY=your_django_secret_key
DEBUG=True

DB_NAME=swimsyncedu
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306

DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

GOOGLE_MAPS_API_KEY=your_google_maps_api_key
PAYMENT_CALLBACK_BASE_URL=http://127.0.0.1:8000

KHALTI_SECRET_KEY=your_khalti_secret_key
KHALTI_INITIATE_URL=https://a.khalti.com/api/v2/epayment/initiate/
KHALTI_LOOKUP_URL=https://a.khalti.com/api/v2/epayment/lookup/

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password_or_app_password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=your_email@example.com

CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
```

Notes:

- `SECRET_KEY` is required or the project will not start.
- In development mode (`DEBUG=True`), media files are stored locally.
- In production mode (`DEBUG=False`), media files are configured to use Cloudinary.
- `PAYMENT_CALLBACK_BASE_URL` should point to a public tunnel URL when testing payment callbacks locally.

### 6. Apply migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create an admin user

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

Open the app in your browser:

```text
http://127.0.0.1:8000/
```

## Demo Data for FYP Presentation

The project includes management commands that are useful for supervisor demos and presentations.

### Seed demo data

```bash
python manage.py seed_demo_data
```

Optional example:

```bash
python manage.py seed_demo_data --members 36 --trainers 8 --wipe-all
```

This command generates:

- demo admin, trainer, and member accounts
- demo pools and pool quality history
- group and private classes
- bookings and payments
- attendance records
- certificates and reviews

Default sample credentials after seeding:

- Admin: `demo_admin` / `demo12345`

### Normalize demo class names

```bash
python manage.py normalize_demo_class_names
```

### Backfill attendance history

```bash
python manage.py backfill_attendance_data
```

## Workflow Summary

### Member Workflow

1. Register or log in
2. Browse pools and classes
3. Book a group class or private class
4. Make payment
5. Attend sessions and track progress
6. Receive certificate after completion
7. Leave a review for the trainer

### Trainer Workflow

1. View assigned classes
2. Manage attendance for students
3. Monitor student completion
4. Issue certificates
5. Review feedback

### Admin Workflow

1. Manage users, trainers, and pools
2. Schedule classes and set private pricing
3. Assign trainers to pools
4. Monitor attendance and pool quality
5. Track payments, reviews, and certificates

## Screenshots

You can add screenshots here before final submission, for example:

- landing page
- admin dashboard
- trainer dashboard
- member dashboard
- booking flow
- payment page
- attendance management
- certificate or review screens

## Future Enhancements

- analytics dashboard with charts and KPIs
- notification system for bookings and schedule changes
- downloadable reports in PDF format
- mobile app version
- online meeting or coaching support
- stronger automated test coverage

## Academic Context

This project was developed as a Final Year Project to solve real-world issues in swimming class administration through a practical web-based information system. It demonstrates:

- software requirements analysis
- role-based system design
- database-driven web development
- third-party API integration
- CRUD operations across multiple business modules
- deployment-oriented configuration practices

## Author

**SwimSyncEDU FYP Project**

If you want, you can replace this section with your:

- full name
- college or university name
- department
- supervisor name
- batch or academic year

## License

This project is intended for educational and academic use unless a separate license is added.
