"""
Создаёт в Планировщике заданий Windows задачу, которая запускает run_parser.py:
  - каждый день в 12:00;
  - и при входе в Windows (если в 12:00 компьютер был выключен).
Двойного сбора не будет: run_parser.py пропускает запуск, если данные за сегодня уже есть.

Запуск (ОБЯЗАТЕЛЬНО из активированного venv, чтобы задача использовала правильный Python):
    python setup_schedule.py          # создать задачу
    python setup_schedule.py remove   # удалить задачу
"""
import subprocess
import sys
from pathlib import Path

TASK_NAME = "PriceParserKZ"
TIME = "12:00"  
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_parser.py"

python = Path(sys.executable)
pythonw = python.with_name("pythonw.exe")   
exe = pythonw if pythonw.exists() else python


def run_powershell(script):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result


def create():
    script = f"""
$ErrorActionPreference = 'Stop'
$action = New-ScheduledTaskAction -Execute '{exe}' -Argument '"{RUNNER}"' -WorkingDirectory '{HERE}'
$t1 = New-ScheduledTaskTrigger -Daily -At {TIME}
$t2 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger @($t1, $t2) -Settings $settings -Force | Out-Null
"""
    r = run_powershell(script)
    if r.returncode == 0:
        print(f"Готово. Задача '{TASK_NAME}' создана: каждый день в {TIME} и при входе в Windows.")
        print(f"Python для запуска: {exe}")
        print("Лог работы: parser_log.txt (появится после первого запуска).")
    else:
        print("Не получилось создать задачу:")
        print(r.stderr or r.stdout)


def remove():
    script = f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false"
    r = run_powershell(script)
    if r.returncode == 0:
        print(f"Задача '{TASK_NAME}' удалена.")
    else:
        print("Не получилось удалить (возможно, задачи нет):")
        print(r.stderr or r.stdout)


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Этот скрипт работает только в Windows.")
        sys.exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove()
    else:
        create()
