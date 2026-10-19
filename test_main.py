
from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4
import unittest

from main import (Author, Genre, Reader, Book, LibraryError, Library, NotFoundError,
                  JsonStorage, XmlStorage, ConsoleApp, demo_library)


@contextmanager
def test_folder():
    folder = Path(__file__).parent / ("test_data_" + uuid4().hex)
    folder.mkdir()
    try:
        yield folder
    finally:
        for file in folder.iterdir():
            file.unlink()
        folder.rmdir()


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.library = demo_library()

    def test_crud(self):
        for kind, item, changes in [
            ("authors", Author(3, "Лев Толстой"), {"name": "Л. Н. Толстой"}),
            ("genres", Genre(3, "Поэзия"), {"name": "Лирика"}),
            ("readers", Reader(3, "Пётр", "p@example.org"), {"name": "Пётр Иванов"}),
            ("books", Book(3, "Новая книга", 1, 1, 2), {"title": "Другое название"}),
        ]:
            self.library.add(kind, item)
            self.library.update(kind, 3, **changes)
            updated = self.library.repo(kind).get(3)
            for key, value in changes.items():
                self.assertEqual(getattr(updated, key), value)
            self.library.delete(kind, 3)
            with self.assertRaises(NotFoundError):
                self.library.repo(kind).get(3)

    def test_duplicate_and_invalid_values(self):
        with self.assertRaises(LibraryError):
            self.library.add("books", Book(1, "Дубликат", 1, 1, 2))
        for value in (-1, True, 1.5):
            with self.assertRaises(LibraryError):
                Book(3, "Книга", 1, 1, value)
        with self.assertRaises(LibraryError):
            self.library.add("books", Book(3, "Книга", 99, 1, 1))
        self.assertEqual(len(self.library.repo("books").all()), 2)

    def test_issue_return_and_shortage(self):
        self.library.issue(1, 2, 1)
        self.library.issue(2, 2, 1)
        self.assertEqual(self.library.available(2), 0)
        with self.assertRaises(LibraryError):
            self.library.issue(3, 2, 1)
        self.library.return_book(1)
        self.assertEqual(self.library.available(2), 1)
        with self.assertRaises(LibraryError):
            self.library.return_book(1)

    def test_references_and_rollback(self):
        self.library.issue(1, 1, 1)
        before = self.library.to_dict()
        for kind, item_id in [("books", 1), ("authors", 1), ("readers", 1)]:
            with self.assertRaises(LibraryError):
                self.library.delete(kind, item_id)
        with self.assertRaises(LibraryError):
            self.library.update("books", 1, copies=0)
        self.assertEqual(self.library.to_dict(), before)

    def test_json_xml_roundtrip(self):
        self.library.issue(1, 1, 1)
        self.library.issue(2, 2, 1)
        self.library.return_book(1)
        with test_folder() as folder:
            for storage, ext in [(JsonStorage(), "json"), (XmlStorage(), "xml")]:
                file = Path(folder) / ("library." + ext)
                storage.save(self.library, file)
                restored = storage.load(file)
                self.assertEqual(restored.to_dict(), self.library.to_dict())
                self.assertEqual(restored.available(2), 1)

    def test_corrupt_files_and_schema(self):
        import xml.etree.ElementTree as ET
        with test_folder() as folder:
            file = Path(folder) / "bad.txt"
            for storage in [JsonStorage(), XmlStorage()]:
                file.write_text("{broken", encoding="utf-8")
                with self.assertRaises((ValueError, ET.ParseError)):
                    storage.load(file)
                with self.assertRaises(OSError):
                    storage.load(Path(folder) / "missing")
        data = self.library.to_dict()
        data["books"][0]["author_id"] = 99
        with self.assertRaises(LibraryError):
            Library.from_dict(data)
        with self.assertRaises(LibraryError):
            Library.from_dict({})


if __name__ == "__main__":
    unittest.main()
