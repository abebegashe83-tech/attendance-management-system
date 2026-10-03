# Attendance Management System

A Django-based attendance management system for Rodas Paints Industry. The project uses SQLite for development, with Bootstrap 5 and Django templates for the interface.

## Features

- Employee management
- Department and shift management
- Daily attendance tracking with check-in and check-out, including mobile, fingerprint, and RFID device ID verification
- Leave request workflow
- Attendance and departmental reporting
- CSV export for report data
- Admin-ready structure using Django models and admin registration

## Technology Stack

- Python 3.11
- Django 5.2
- SQLite
- Bootstrap 5
- Pillow

## Project Setup

1. Create and activate a virtual environment:

   ```powershell
   py -3.11 -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Apply database migrations:

   ```powershell
   python manage.py migrate
   ```

For deployments, set a persistent `DJANGO_SECRET_KEY` environment variable before starting Django.

4. Create an admin user:

   ```powershell
   python manage.py createsuperuser
   ```

5. Start the development server:

   ```powershell
   python manage.py runserver 127.0.0.1:8000
   ```

6. Open the app in a browser:

   - Dashboard: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

## Running Tests

```powershell
python manage.py test attendance -v 1
```

## Notes

- Biometric device ID verification is supported for mobile phones, fingerprint scanners, and RFID readers.
