@echo off
REM Script to check and create ChatRooms for matched users
REM Run this from the dating_backend directory

echo ========================================
echo  ChatRoom Diagnostic & Repair Tool
echo ========================================
echo.

REM Navigate to project directory
cd /d "%~dp0"

REM Check if manage.py exists
if not exist "manage.py" (
    echo ERROR: manage.py not found!
    echo Please run this script from the dating_backend directory.
    pause
    exit /b 1
)

REM Run the Python script via Django shell
echo Running ChatRoom check and creation...
echo.

python manage.py shell < check_and_create_chatroom.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Script execution failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Process completed successfully!
echo ========================================
pause
