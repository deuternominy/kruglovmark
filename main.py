
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
import json
from pathlib import Path
import xml.etree.ElementTree as ET


class LibraryError(Exception):
    """Нарушение правил работы библиотеки."""


class NotFoundError(LibraryError):
    """Запись с заданным номером отсутствует."""


def positive(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise LibraryError("Идентификатор должен быть целым положительным числом.")


def nonempty(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LibraryError("Текстовое поле не должно быть пустым.")


@dataclass(frozen=True)
class Author:
    id: int
    name: str

    def __post_init__(self) -> None:
        positive(self.id)
        nonempty(self.name)


@dataclass(frozen=True)
class Genre:
    id: int
    name: str

    def __post_init__(self) -> None:
        positive(self.id)
        nonempty(self.name)


@dataclass(frozen=True)
class Reader:
    id: int
    name: str
    email: str

    def __post_init__(self) -> None:
        positive(self.id)
        nonempty(self.name)
        nonempty(self.email)
        if "@" not in self.email:
            raise LibraryError("В адресе электронной почты отсутствует @.")


@dataclass(frozen=True)
class Book:
    id: int
    title: str
    author_id: int
    genre_id: int
    copies: int

    def __post_init__(self) -> None:
        for value in (self.id, self.author_id, self.genre_id):
            positive(value)
        nonempty(self.title)
        if type(self.copies) is not int or self.copies < 0:
            raise LibraryError("Количество экземпляров должно быть целым и неотрицательным.")


@dataclass(frozen=True)
class Loan:
    id: int
    book_id: int
    reader_id: int
    issued_on: str
    returned_on: str = ""

    def __post_init__(self) -> None:
        for value in (self.id, self.book_id, self.reader_id):
            positive(value)
        issued = date.fromisoformat(self.issued_on)
        if self.returned_on and date.fromisoformat(self.returned_on) < issued:
            raise LibraryError("Возврат не может предшествовать выдаче.")


class Repository:
    """Общие операции CRUD с защитой от повторных идентификаторов."""

    def __init__(self, entity_type: type) -> None:
        self.entity_type = entity_type
        self._items: dict = {}

    def all(self) -> list:
        return [self._items[key] for key in sorted(self._items)]

    def get(self, item_id: int) -> Author | Genre | Reader | Book | Loan:
        if item_id not in self._items:
            raise NotFoundError(f"Запись с ID {item_id} не найдена.")
        return self._items[item_id]

    def add(self, item: Author | Genre | Reader | Book | Loan) -> None:
        if type(item) is not self.entity_type:
            raise LibraryError("Неверный тип объекта.")
        if item.id in self._items:
            raise LibraryError(f"Запись с ID {item.id} уже существует.")
        self._items[item.id] = item

    def update(self, item_id: int, **changes: object) -> None:
        if "id" in changes:
            raise LibraryError("Изменение идентификатора запрещено.")
        self._items[item_id] = replace(self.get(item_id), **changes)

    def delete(self, item_id: int) -> None:
        self.get(item_id)
        del self._items[item_id]


class Library:
    """Проверяет ссылки между записями и управляет выдачей книг."""

    TYPES = {"authors": Author, "genres": Genre, "readers": Reader,
             "books": Book, "loans": Loan}

    def __init__(self) -> None:
        self.repositories = {key: Repository(cls) for key, cls in self.TYPES.items()}

    def repo(self, kind: str) -> Repository:
        if kind not in self.repositories:
            raise LibraryError("Неизвестный раздел библиотеки.")
        return self.repositories[kind]

    def validate(self) -> None:
        for book in self.repo("books").all():
            self.repo("authors").get(book.author_id)
            self.repo("genres").get(book.genre_id)
            active = sum(x.book_id == book.id and not x.returned_on
                         for x in self.repo("loans").all())
            if active > book.copies:
                raise LibraryError("Количество экземпляров меньше числа выданных книг.")
        for loan in self.repo("loans").all():
            self.repo("books").get(loan.book_id)
            self.repo("readers").get(loan.reader_id)

    def add(self, kind: str, item: Author | Genre | Reader | Book) -> None:
        if kind == "loans":
            raise LibraryError("Для выдачи книги используйте команду выдачи.")
        self.repo(kind).add(item)
        try:
            self.validate()
        except LibraryError:
            self.repo(kind).delete(item.id)
            raise

    def update(self, kind: str, item_id: int, **changes: object) -> None:
        if kind == "loans":
            raise LibraryError("Для возврата книги используйте команду возврата.")
        old = self.repo(kind).get(item_id)
        self.repo(kind).update(item_id, **changes)
        try:
            self.validate()
        except LibraryError:
            self.repo(kind)._items[item_id] = old
            raise

    def delete(self, kind: str, item_id: int) -> None:
        if kind == "loans":
            raise LibraryError("История выдачи сохраняется.")
        old = self.repo(kind).get(item_id)
        self.repo(kind).delete(item_id)
        try:
            self.validate()
        except LibraryError:
            self.repo(kind)._items[item_id] = old
            raise LibraryError("Нельзя удалить запись, на которую есть ссылки.")

    def available(self, book_id: int) -> int:
        book = self.repo("books").get(book_id)
        return book.copies - sum(x.book_id == book_id and not x.returned_on
                                 for x in self.repo("loans").all())

    def issue(self, loan_id: int, book_id: int, reader_id: int) -> Loan:
        self.repo("readers").get(reader_id)
        if self.available(book_id) <= 0:
            raise LibraryError("Нет свободных экземпляров книги.")
        loan = Loan(loan_id, book_id, reader_id, date.today().isoformat())
        self.repo("loans").add(loan)
        return loan

    def return_book(self, loan_id: int) -> None:
        loan = self.repo("loans").get(loan_id)
        if loan.returned_on:
            raise LibraryError("Книга по этой выдаче уже возвращена.")
        self.repo("loans").update(loan_id, returned_on=date.today().isoformat())

    def to_dict(self) -> dict:
        return {key: [asdict(item) for item in repo.all()]
                for key, repo in self.repositories.items()}

    @classmethod
    def from_dict(cls, data: dict) -> Library:
        if not isinstance(data, dict) or set(data) != set(cls.TYPES):
            raise LibraryError("Ожидались разделы authors, genres, readers, books, loans.")
        result = cls()
        # Сначала создаются все объекты, затем проверяются их взаимные ссылки.
        for kind, entity in cls.TYPES.items():
            if not isinstance(data[kind], list):
                raise LibraryError("Раздел должен содержать список записей.")
            for row in data[kind]:
                result.repo(kind).add(entity(**row))
        result.validate()
        return result


class JsonStorage:
    """Хранение полного состояния библиотеки в JSON."""

    def save(self, library: Library, path: str | Path) -> None:
        Path(path).write_text(json.dumps(library.to_dict(), ensure_ascii=False,
                                        indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> Library:
        return Library.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


class XmlStorage:
    """Тот же интерфейс хранения для XML (полиморфизм)."""

    INTEGER_FIELDS = {"id", "author_id", "genre_id", "copies", "book_id", "reader_id"}

    def save(self, library: Library, path: str | Path) -> None:
        root = ET.Element("library")
        for kind, rows in library.to_dict().items():
            group = ET.SubElement(root, kind)
            for row in rows:
                item = ET.SubElement(group, "item")
                for key, value in row.items():
                    ET.SubElement(item, key).text = str(value)
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def load(self, path: str | Path) -> Library:
        root = ET.parse(path).getroot()
        if root.tag != "library":
            raise LibraryError("Ожидался корневой элемент library.")
        data = {}
        for group in root:
            if group.tag in data:
                raise LibraryError("Повторный раздел XML.")
            rows = []
            for item in group:
                if item.tag != "item" or len({x.tag for x in item}) != len(item):
                    raise LibraryError("Некорректная запись XML.")
                rows.append({x.tag: int(x.text or "") if x.tag in self.INTEGER_FIELDS
                             else x.text or "" for x in item})
            data[group.tag] = rows
        return Library.from_dict(data)


def demo_library() -> Library:
    library = Library()
    for kind, item in [("authors", Author(1, "Александр Пушкин")),
                       ("authors", Author(2, "Михаил Булгаков")),
                       ("genres", Genre(1, "Роман")),
                       ("readers", Reader(1, "Иван Петров", "ivan@example.org")),
                       ("books", Book(1, "Евгений Онегин", 1, 1, 3)),
                       ("books", Book(2, "Мастер и Маргарита", 2, 1, 2))]:
        library.add(kind, item)
    return library


class ConsoleApp:
    """Команды пользователя и граница обработки исключений."""

    MENU = ("\n1 Список  2 Поиск  3 Добавить  4 Изменить  5 Удалить\n"
            "6 Выдать книгу  7 Вернуть книгу  8 Сохранить  9 Загрузить  0 Выход")

    def __init__(self) -> None:
        self.library = demo_library()

    def record(self, kind: str, item_id: int) -> object:
        if kind == "authors":
            return Author(item_id, input("Имя автора: "))
        if kind == "genres":
            return Genre(item_id, input("Название жанра: "))
        if kind == "readers":
            return Reader(item_id, input("ФИО: "), input("Email: "))
        if kind == "books":
            return Book(item_id, input("Название: "), int(input("ID автора: ")),
                        int(input("ID жанра: ")), int(input("Экземпляров: ")))
        raise LibraryError("Редактировать можно authors, genres, readers, books.")

    def execute(self, command: str) -> None:
        if command in {"1", "2", "3", "4", "5"}:
            kind = input("Раздел (authors/genres/readers/books/loans): ").strip()
            repo = self.library.repo(kind)
            if command == "1":
                for item in repo.all():
                    print(item)
                if not repo.all():
                    print("Список пуст.")
                return
            item_id = int(input("ID: "))
            if command == "2":
                print(repo.get(item_id))
            elif command == "3":
                self.library.add(kind, self.record(kind, item_id))
            elif command == "4":
                data = asdict(self.record(kind, item_id))
                data.pop("id")
                self.library.update(kind, item_id, **data)
            else:
                self.library.delete(kind, item_id)
        elif command == "6":
            print(self.library.issue(int(input("ID выдачи: ")),
                                     int(input("ID книги: ")),
                                     int(input("ID читателя: "))))
        elif command == "7":
            self.library.return_book(int(input("ID выдачи: ")))
        elif command in {"8", "9"}:
            fmt = input("Формат (json/xml): ").strip().lower()
            if fmt not in {"json", "xml"}:
                raise LibraryError("Неизвестный формат.")
            storage = JsonStorage() if fmt == "json" else XmlStorage()
            path = input("Путь к файлу: ").strip()
            if command == "8":
                storage.save(self.library, path)
            else:
                # Замена только после успешного разбора и проверки всего файла.
                self.library = storage.load(path)
        else:
            raise LibraryError("Неизвестная команда.")
        print("Операция выполнена.")

    def run(self) -> None:
        print("Библиотека. Начальные данные загружены из демонстрационного набора.")
        while True:
            try:
                print(self.MENU)
                command = input("Команда: ").strip()
                if command == "0":
                    return
                self.execute(command)
            except (LibraryError, ValueError, TypeError, KeyError,
                    OSError, ET.ParseError) as error:
                print(f"Ошибка: {error}")
            except (EOFError, KeyboardInterrupt):
                print("\nРабота завершена.")
                return


if __name__ == "__main__":
    ConsoleApp().run()
