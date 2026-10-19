"""ЛР 2. Проверка и поиск IPv4 с помощью регулярных выражений."""

from dataclasses import dataclass
from pathlib import Path
import re


# Один октет: 0–255; ведущие нули в многозначных октетах запрещены.
OCTET = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
IPV4 = rf"(?:{OCTET}\.){{3}}{OCTET}"
CHECK_PATTERN = re.compile(IPV4)
# Не выделяем часть слова, длинного числа или цепочки из пяти октетов.
# Точка в конце предложения допустима, если после неё нет цифры.
SEARCH_PATTERN = re.compile(rf"(?<![\w.]){IPV4}(?!\w|\.[0-9])")


@dataclass(frozen=True)
class Match:
    """Найденный адрес; строка и столбец нумеруются с единицы."""

    address: str
    line: int
    column: int


def is_valid_ipv4(value: str) -> bool:
    """Проверить всю строку без удаления пробелов и перевода строки."""
    return CHECK_PATTERN.fullmatch(value) is not None


def find_ipv4(text: str) -> list[Match]:
    """Найти адреса по порядку, сохраняя повторные вхождения."""
    result = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in SEARCH_PATTERN.finditer(line):
            result.append(Match(match.group(), line_number, match.start() + 1))
    return result


def find_in_file(path: str | Path) -> list[Match]:
    """Прочитать UTF-8/UTF-8 BOM файл; ошибки обрабатывает вызывающий код."""
    return find_ipv4(Path(path).read_text(encoding="utf-8-sig"))


def show_matches(matches: list[Match]) -> None:
    if not matches:
        print("IPv4-адреса не найдены.")
        return
    print(f"Найдено адресов: {len(matches)}")
    for match in matches:
        print(f"{match.address} | строка {match.line}, столбец {match.column}")


def run() -> None:
    """Консольное меню с обработкой файловых ошибок и прерывания ввода."""
    print("ЛР 2. Проверка и поиск IPv4-адресов")
    while True:
        try:
            print("\n1 Проверить адрес\n2 Найти в тексте\n3 Найти в файле\n0 Выход")
            command = input("Команда: ").strip()
            if command == "0":
                return
            if command == "1":
                value = input("IPv4: ")
                print("Корректный IPv4-адрес." if is_valid_ipv4(value)
                      else "Некорректный IPv4-адрес.")
            elif command == "2":
                show_matches(find_ipv4(input("Текст: ")))
            elif command == "3":
                show_matches(find_in_file(input("Путь к файлу: ").strip()))
            else:
                print("Ошибка: неизвестная команда.")
        except (OSError, UnicodeError) as error:
            print(f"Ошибка чтения файла: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nРабота завершена.")
            return


if __name__ == "__main__":
    run()
