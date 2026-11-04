# Office Archive System

Document archive for the office. See docs\ARCHIVE_SYSTEM_PLAN.md for the full plan.

## Setup
Run setup_archive_project.bat once, or:
    python -m pip install -r requirements.txt

## Run
    python app.py

## Build
    python -m PyInstaller --onefile --windowed app.py

## Data and backups
Data lives in data\ (database and archived files). It is NOT in Git.
Back up data\ regularly to an external drive.
