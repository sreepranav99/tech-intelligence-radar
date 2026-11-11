import base64
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from rich.console import Console
from rich.panel import Panel

from radar.config import PROJECT_ROOT, BRIEFING_TIME, DATA_DIR

console = Console()
TASK_NAME = "TechIntelligenceRadarMorningBriefing"
LOG_PATH = DATA_DIR / "morning_scheduler.log"


def _run_ps(ps_script: str) -> subprocess.CompletedProcess:
    """Execute a PowerShell script cleanly via UTF-16LE EncodedCommand."""
    encoded = base64.b64encode(ps_script.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
    )


def _format_ps_datetime(val: Any) -> str:
    """Format PowerShell JSON \/Date(ms)\/ or ISO timestamp into readable local time."""
    if not val:
        return "N/A"
    s = str(val)
    if s.startswith("/Date(") and s.endswith(")/"):
        try:
            ms = int(s[6:-2])
            if ms <= 950000000000:  # Year <= 2000 sentinel (Windows 1999 'Never run')
                return "Never"
            dt = datetime.fromtimestamp(ms / 1000.0)
            return dt.strftime("%Y-%m-%d %I:%M:%S %p")
        except Exception:
            return s
    return s


def get_schedule_details() -> Optional[Dict[str, Any]]:
    """Query structured settings and runtime info for the Windows scheduled task."""
    ps_script = f"""
$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue
if (-not $task) {{
    Write-Output 'null'
    exit 0
}}
$info = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}'
$action = $task.Actions | Select-Object -First 1
$trigger = $task.Triggers | Select-Object -First 1
$payload = [PSCustomObject]@{{
    TaskName = $task.TaskName
    State = [string]$task.State
    StartBoundary = [string]$trigger.StartBoundary
    Execute = [string]$action.Execute
    Arguments = [string]$action.Arguments
    WorkingDirectory = [string]$action.WorkingDirectory
    DisallowStartIfOnBatteries = [bool]$task.Settings.DisallowStartIfOnBatteries
    StopIfGoingOnBatteries = [bool]$task.Settings.StopIfGoingOnBatteries
    StartWhenAvailable = [bool]$task.Settings.StartWhenAvailable
    WakeToRun = [bool]$task.Settings.WakeToRun
    RestartCount = [int]$task.Settings.RestartCount
    ExecutionTimeLimit = [string]$task.Settings.ExecutionTimeLimit
    NextRunTime = $info.NextRunTime
    LastRunTime = $info.LastRunTime
    LastTaskResult = [int]$info.LastTaskResult
    NumberOfMissedRuns = [int]$info.NumberOfMissedRuns
}}
$payload | ConvertTo-Json -Compress
"""
    res = _run_ps(ps_script)
    if res.returncode != 0 or not res.stdout.strip():
        return None
    raw = res.stdout.strip()
    if raw == "null":
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def schedule_needs_repair(details: Optional[Dict[str, Any]]) -> bool:
    """Detect whether an existing task lacks laptop battery/catch-up/working-dir settings."""
    if not details:
        return False
    return (
        details.get("DisallowStartIfOnBatteries", True)
        or details.get("StopIfGoingOnBatteries", True)
        or not details.get("StartWhenAvailable", False)
        or not details.get("WorkingDirectory")
        or details.get("State") == "Disabled"
    )


def install_daily_schedule(time_str: str = BRIEFING_TIME) -> bool:
    """Register daily morning Task Scheduler job on Windows with laptop-safe reliability flags."""
    radar_bat = PROJECT_ROOT / "radar.bat"

    if not radar_bat.exists():
        console.print(f"[bold red]Cannot find launcher script at {radar_bat}[/bold red]")
        return False

    try:
        datetime.strptime(time_str.strip(), "%H:%M")
    except ValueError:
        console.print(f"[bold red]Invalid BRIEFING_TIME '{time_str}'. Expected 24-hour HH:MM (e.g. 08:00).[/bold red]")
        return False

    console.print(f"[cyan]Registering Windows Task Scheduler job at {time_str} IST...[/cyan]")

    bat_escaped = str(radar_bat).replace("'", "''")
    dir_escaped = str(PROJECT_ROOT).replace("'", "''")
    t_clean = time_str.strip()

    ps_script = f"""
$ErrorActionPreference = 'Stop'
$triggerTime = [datetime]::ParseExact('{t_clean}', 'HH:mm', [System.Globalization.CultureInfo]::InvariantCulture)
$action = New-ScheduledTaskAction `
    -Execute '{bat_escaped}' `
    -Argument 'morning' `
    -WorkingDirectory '{dir_escaped}'
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName '{TASK_NAME}' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'Autonomous Tech Intelligence Radar daily morning briefing email cycle.' `
    -Force | Out-Null
Write-Output 'REGISTERED_OK'
"""
    try:
        res = _run_ps(ps_script)
        if res.returncode == 0 and "REGISTERED_OK" in res.stdout:
            console.print(f"[bold green]✓ Successfully scheduled Daily Morning Radar at {t_clean} IST![/bold green]")
            console.print(f"[dim]Task Name: {TASK_NAME}[/dim]")
            console.print(f"[green]✓ Reliability:[/green] Runs on battery, wakes/catches up if laptop was asleep/off at {t_clean}, auto-retries if Wi-Fi is waking up.")
            console.print(f"[dim]Working Directory: {PROJECT_ROOT}[/dim]")
            console.print(f"[dim]To remove anytime, run: radar schedule --remove[/dim]\n")
            return True

        # Fallback to schtasks only if PowerShell ScheduledTasks module failed unexpectedly
        err_msg = (res.stderr or res.stdout or "").strip()
        console.print(f"[bold yellow]PowerShell registration issue ({res.returncode}): {err_msg}[/bold yellow]")
        console.print("[dim]Tip: If permissions error occurs, run your terminal once as Administrator.[/dim]")
        return False
    except Exception as e:
        console.print(f"[bold red]Failed to create task: {str(e)}[/bold red]")
        return False


def remove_daily_schedule() -> bool:
    """Remove the scheduled task from Windows Task Scheduler."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            console.print(f"[bold green]✓ Successfully removed scheduled task '{TASK_NAME}'.[/bold green]")
            return True
        else:
            console.print(f"[yellow]Task '{TASK_NAME}' was not found or already removed.[/yellow]")
            return False
    except Exception as e:
        console.print(f"[bold red]Failed to remove task: {str(e)}[/bold red]")
        return False


def query_daily_schedule() -> bool:
    """Check status, reliability flags, and recent execution logs of scheduled task."""
    details = get_schedule_details()
    if not details:
        console.print(f"[yellow]No active morning schedule found. Run 'radar schedule --install' to set it up.[/yellow]")
        return False

    last_res = details.get("LastTaskResult")
    if last_res == 267011:
        last_res_str = "267011 (Task has not run yet)"
    elif last_res == 0:
        last_res_str = "0 (Success)"
    else:
        last_res_str = f"{last_res} (Exit/Error Code)"

    on_battery_ok = (not details.get("DisallowStartIfOnBatteries", True)) and (
        not details.get("StopIfGoingOnBatteries", True)
    )
    catchup_ok = bool(details.get("StartWhenAvailable", False))
    wake_ok = bool(details.get("WakeToRun", False))
    workdir = details.get("WorkingDirectory") or "N/A (Missing)"

    body = (
        f"[bold]Task Name:[/bold] {details.get('TaskName')} ([cyan]{details.get('State')}[/cyan])\n"
        f"[bold]Next Run Time:[/bold] {_format_ps_datetime(details.get('NextRunTime'))}\n"
        f"[bold]Last Run Time:[/bold] {_format_ps_datetime(details.get('LastRunTime'))}\n"
        f"[bold]Last Result:[/bold] {last_res_str}\n"
        f"[bold]Run on Battery:[/bold] {'[green]Enabled[/green]' if on_battery_ok else '[red]Blocked by Windows Default![/red]'}\n"
        f"[bold]Catch-Up Missed Run:[/bold] {'[green]Enabled[/green]' if catchup_ok else '[red]Disabled (Skips if asleep/off at 8 AM)![/red]'}\n"
        f"[bold]Wake PC to Run:[/bold] {'[green]Enabled[/green]' if wake_ok else '[yellow]Disabled[/yellow]'}\n"
        f"[bold]Working Directory:[/bold] {workdir}"
    )

    console.print(Panel(body, title="⏰ Windows Daily Schedule Status", border_style="green" if not schedule_needs_repair(details) else "yellow"))

    if schedule_needs_repair(details):
        console.print("[bold yellow]⚠️ Warning:[/bold yellow] Your scheduled task has restrictive Windows defaults (battery block or no sleep catch-up), which commonly causes 8:00 AM skips on laptops.")
        console.print("Run [bold cyan]radar schedule --install[/bold cyan] to upgrade it!\n")

    if LOG_PATH.exists():
        try:
            lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-6:]
            if lines:
                console.print("[dim]Recent Scheduler Log (data/morning_scheduler.log):[/dim]")
                for line in lines:
                    console.print(f"  [dim]{line}[/dim]")
                console.print()
        except Exception:
            pass

    return True
