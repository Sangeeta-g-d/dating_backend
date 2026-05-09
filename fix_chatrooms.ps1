# PowerShell script to check and create ChatRooms for matched users
# Run this from the dating_backend directory

Write-Host "========================================"
Write-Host "  ChatRoom Diagnostic & Repair Tool"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Verify we're in the right directory
$managePy = Get-Item "manage.py" -ErrorAction SilentlyContinue

if (-not $managePy) {
    Write-Host "ERROR: manage.py not found!" -ForegroundColor Red
    Write-Host "Please run this script from the dating_backend directory."
    pause
    exit 1
}

Write-Host "Running ChatRoom check and creation..." -ForegroundColor Yellow
Write-Host ""

# Run the diagnostic script
try {
    python manage.py shell < check_and_create_chatroom.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Script execution failed!" -ForegroundColor Red
        pause
        exit 1
    }
}
catch {
    Write-Host "ERROR: $($_)" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Process completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
pause
