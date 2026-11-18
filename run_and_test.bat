@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title NOTHING OS // Multi-Role AI-Agentic Student Management System

echo ============================================================================
echo   NOTHING OS - MULTI-ROLE AI-AGENTIC SMS (STUDENT + 5 STAFF + 1 HOD)
echo ============================================================================
echo [DIR] Working directory: %CD%
echo.

if not exist "manage.py" (
    echo [ERROR] manage.py not found in %CD%!
    pause
    exit /b 1
)

set "PY_CMD="
where py >nul 2>nul && (
    py -3 --version >nul 2>nul && set "PY_CMD=py -3"
)
if not defined PY_CMD (
    python --version >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [ERROR] Python 3.10+ was not found!
    pause
    exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

if exist "venv" (
    if not exist "venv\Scripts\activate.bat" rmdir /s /q venv
)
if not exist "venv" (
    echo [1/5] Creating virtual environment...
    %PY_CMD% -m venv venv
)

echo [2/5] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org
python -m pip install "Django>=5.1,<6.2" "python-dotenv>=1.0.0" "pydantic>=2.0.0" --trusted-host pypi.org --trusted-host files.pythonhosted.org
python -m pip install "google-genai>=1.0.0" --trusted-host pypi.org --trusted-host files.pythonhosted.org

echo.
echo [3/5] Running Django database migrations (SQLite WAL mode)...
python manage.py makemigrations students staff_hod --noinput
python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo [ERROR] Migration failed! Check error above.
    pause
    exit /b 1
)

echo [4/5] Seeding 1 Student, 5 Staff Tutors, 1 HOD, Quizzes, Homework & LINE AI...
python manage.py seed_nothing_sms

echo [5/5] Running automated test suite across Student, Staff & HOD portals...
python manage.py test students staff_hod -v 2
if %errorlevel% neq 0 (
    echo [WARNING] Some tests failed! Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   ALL TESTS PASSED! STARTING NOTHING OS SERVER AT http://127.0.0.1:8000/
echo   --------------------------------------------------------------------------
echo   STUDENT LOGIN : student  / nothing123
echo   HOD LOGIN     : hod      / nothing123
echo   5 STAFF LOGINS: staff1 .. staff5 / nothing123
echo   SHORTCUT      : Press Alt+E anywhere for Nothing Essential Key!
echo ============================================================================
start "" "http://127.0.0.1:8000/"
python manage.py runserver 127.0.0.1:8000
pause
