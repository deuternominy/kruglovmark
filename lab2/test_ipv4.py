"""Unit-тесты IPv4: границы октетов, поиск, файлы и консольное меню."""

import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Однозначный импорт при запуске из общего репозитория с main.py первой ЛР.
SPEC = importlib.util.spec_from_file_location(
    "lab2_ipv4_application", Path(__file__).with_name("main.py"))
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)


class ValidationTests(unittest.TestCase):
    def test_valid_addresses(self):
        for value in ["0.0.0.0", "255.255.255.255", "127.0.0.1",
                      "192.168.1.10", "1.2.3.4", "249.250.251.255"]:
            with self.subTest(value=value):
                self.assertTrue(app.is_valid_ipv4(value))

    def test_every_octet_value_in_every_position(self):
        # Проверяем переходы всех ветвей выражения, а не только примеры.
        for position in range(4):
            for value in range(256):
                octets = ["1"] * 4
                octets[position] = str(value)
                with self.subTest(position=position, value=value):
                    self.assertTrue(app.is_valid_ipv4(".".join(octets)))

    def test_out_of_range_octets(self):
        for position in range(4):
            for value in ["256", "299", "999", "1000", "-1", "+1"]:
                octets = ["1"] * 4
                octets[position] = value
                with self.subTest(address=octets):
                    self.assertFalse(app.is_valid_ipv4(".".join(octets)))

    def test_leading_zeroes(self):
        for value in ["01.2.3.4", "1.02.3.4", "1.2.003.4", "1.2.3.00"]:
            with self.subTest(value=value):
                self.assertFalse(app.is_valid_ipv4(value))

    def test_wrong_number_of_octets(self):
        for value in ["", "1", "1.2.3", "1.2.3.4.5", ".1.2.3.4", "1.2.3.4."]:
            with self.subTest(value=value):
                self.assertFalse(app.is_valid_ipv4(value))

    def test_full_string_and_ascii_digits(self):
        for value in [" 1.2.3.4", "1.2.3.4 ", "1.2.3.4\n", "1.2.3.4\r\n",
                      "x1.2.3.4", "1.2.3.4x", "１.２.３.４", "١.٢.٣.٤",
                      "1,2,3,4", "1a2b3c4", "1.2. 3.4"]:
            with self.subTest(value=value):
                self.assertFalse(app.is_valid_ipv4(value))


class SearchTests(unittest.TestCase):
    def test_order_positions_and_repeats(self):
        self.assertEqual(app.find_ipv4("IP 1.2.3.4; 8.8.8.8\n1.2.3.4"), [
            app.Match("1.2.3.4", 1, 4), app.Match("8.8.8.8", 1, 13),
            app.Match("1.2.3.4", 2, 1)])

    def test_punctuation_and_port(self):
        found = app.find_ipv4("(1.2.3.4), 8.8.8.8:53; адрес 127.0.0.1.")
        self.assertEqual([x.address for x in found], ["1.2.3.4", "8.8.8.8", "127.0.0.1"])

    def test_no_fragments_of_invalid_tokens(self):
        for value in ["256.1.2.3", "01.2.3.4", "1.2.3.456", "1.2.3.4.5",
                      "9991.2.3.4", "a1.2.3.4", "1.2.3.4я", "_1.2.3.4",
                      "１1.2.3.4", "1.2.3.4１", "1.2.3.4_", ".1.2.3.4"]:
            with self.subTest(value=value):
                self.assertEqual(app.find_ipv4(value), [])

    def test_empty_and_no_matches(self):
        for value in ["", "нет адресов", "256.300.1.1", "\n\n"]:
            self.assertEqual(app.find_ipv4(value), [])

    def test_windows_newlines_and_empty_lines(self):
        self.assertEqual(app.find_ipv4("\r\n  1.2.3.4\r\n\r\n8.8.8.8"), [
            app.Match("1.2.3.4", 2, 3), app.Match("8.8.8.8", 4, 1)])


class FileTests(unittest.TestCase):
    def test_real_sample_file(self):
        result = app.find_in_file(Path(__file__).with_name("sample.txt"))
        self.assertEqual([x.address for x in result], ["192.168.1.10", "192.168.1.1",
                         "8.8.8.8", "1.1.1.1", "127.0.0.1", "192.168.1.10"])
        self.assertEqual(result[0], app.Match("192.168.1.10", 2, 9))

    def test_empty_file(self):
        with patch.object(Path, "read_text", return_value="") as read:
            self.assertEqual(app.find_in_file("empty.txt"), [])
            read.assert_called_once_with(encoding="utf-8-sig")

    def test_io_error_propagates(self):
        with patch.object(Path, "read_text", side_effect=OSError("Нет доступа")):
            with self.assertRaises(OSError):
                app.find_in_file("closed.txt")


class MenuTests(unittest.TestCase):
    def menu(self, answers):
        with patch("builtins.input", side_effect=answers), patch("sys.stdout", new_callable=io.StringIO) as out:
            app.run()
            return out.getvalue()

    def test_check_both_results(self):
        text = self.menu(["1", "1.2.3.4", "1", "999.2.3.4", "0"])
        self.assertIn("Корректный IPv4-адрес.", text)
        self.assertIn("Некорректный IPv4-адрес.", text)

    def test_text_search_and_empty_result(self):
        text = self.menu(["2", "IP 8.8.8.8", "2", "без адресов", "0"])
        self.assertIn("8.8.8.8 | строка 1, столбец 4", text)
        self.assertIn("IPv4-адреса не найдены.", text)

    def test_real_file_from_menu(self):
        text = self.menu(["3", str(Path(__file__).with_name("sample.txt")), "0"])
        self.assertIn("Найдено адресов: 6", text)

    def test_bad_command_recovers(self):
        text = self.menu(["7", "1", "1.2.3.4", "0"])
        self.assertIn("неизвестная команда", text)
        self.assertIn("Корректный IPv4-адрес.", text)

    def test_file_error_recovers(self):
        with patch.object(app, "find_in_file", side_effect=OSError("Нет файла")):
            text = self.menu(["3", "missing.txt", "1", "1.2.3.4", "0"])
        self.assertIn("Ошибка чтения файла:", text)
        self.assertIn("Корректный IPv4-адрес.", text)

    def test_decoding_error_recovers(self):
        with patch.object(app, "find_in_file", side_effect=UnicodeError("Неверная кодировка")):
            text = self.menu(["3", "bad.txt", "0"])
        self.assertIn("Ошибка чтения файла:", text)

    def test_eof_and_keyboard_interrupt(self):
        for error in [EOFError(), KeyboardInterrupt()]:
            with self.subTest(error=type(error).__name__):
                self.assertIn("Работа завершена.", self.menu([error]))


if __name__ == "__main__":
    unittest.main()
