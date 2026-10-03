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
- SQLite for local development; PostgreSQL for deployment
- Bootstrap 5
- Pillow
- Gunicorn and WhiteNoise for production serving

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

## Deploying to Render

1. Push this repository to GitHub and create a PostgreSQL database in Render.
2. Create a Render Blueprint from the repository, or create a Python web service and use the commands from `render.yaml`.
3. Set the web service's `DATABASE_URL` to the database's internal connection URL. Set `DJANGO_SECRET_KEY` to a persistent secret and `DEBUG` to `False`. The Blueprint generates a secret key automatically.
4. Deploy. The start command applies database migrations before starting Gunicorn. Static files are collected during the build and served by WhiteNoise.
5. In the web service's Shell, run `python manage.py createsuperuser` to create your admin account.

Do not commit production secret keys or database URLs. The local SQLite database is not copied to Render; create any production users and records on the deployed service.

## Notes

- Biometric device ID verification is supported for mobile phones, fingerprint scanners, and RFID readers.
