"""
Ежедневный запуск парсера. Сам парсер не трогаем.

- Если за сегодня данные уже есть в tobaza.csv, ничего не делает.
- Пишет лог в parser_log.txt.
- Если после запуска за сегодня данных нет (нет интернета, сайт упал),
  завершается с ошибкой, и планировщик повторит попытку.
"""
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

PARSER = HERE / "ff.py" 
CSV = HERE / "tobaza.csv"
LOG = HERE / "parser_log.txt"

today = date.today().isoformat()


def already_collected():
    if not CSV.exists():
        return False
    with open(CSV, encoding="utf-8-sig") as f:
        return any(line.rstrip().endswith(";" + today) for line in f)


def main():
    if already_collected():
        return 0 

    python = Path(sys.executable)
    console_python = python.with_name("python.exe")
    if console_python.exists():
        python = console_python

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    with open(LOG, "a", encoding="utf-8") as log:
        log.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
        log.flush()
        result = subprocess.run(
            [str(python), str(PARSER)],
            cwd=str(HERE),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=no_window,
        )
        ok = already_collected()
        log.write(f"Код завершения: {result.returncode}, данные за сегодня есть: {ok}\n")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
