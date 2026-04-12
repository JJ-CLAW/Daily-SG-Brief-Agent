# Schedules a daily run at 09:30 in YOUR PC's local time zone.
# For guaranteed 09:30 Singapore time on a PC outside SG, use instead:
#   python -m brief_agent serve
# (APScheduler uses Asia/Singapore regardless of system clock zone.)

param(
    [string] $ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$TaskName = "DailyBriefTelegram"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe. Create it: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "-m brief_agent once" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:30"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Registered scheduled task: $TaskName (daily 09:30 local time)."
