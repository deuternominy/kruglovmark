"""Запуск проекта из Visual Studio."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import ConsoleApp

if __name__ == "__main__":
    ConsoleApp().run()
