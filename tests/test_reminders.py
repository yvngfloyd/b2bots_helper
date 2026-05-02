from __future__ import annotations

import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.reminders import make_reminder_keyboard, reminder_image_path


class ReminderPresentationTests(unittest.TestCase):
    def test_second_reminder_has_continue_and_restart_buttons(self) -> None:
        keyboard = make_reminder_keyboard(reminder_count=1).as_markup()
        rows = keyboard.inline_keyboard

        self.assertEqual(rows[0][0].text, "Продолжить")
        self.assertEqual(rows[0][0].callback_data, "reminder:continue")
        self.assertEqual(rows[1][0].text, "Заполнить заново")
        self.assertEqual(rows[1][0].callback_data, "form:restart")

    def test_other_reminders_start_form_from_first_question(self) -> None:
        keyboard = make_reminder_keyboard(reminder_count=0).as_markup()
        button = keyboard.inline_keyboard[0][0]

        self.assertEqual(button.text, "Заполнить заявку")
        self.assertEqual(button.callback_data, "form:start")

    def test_reminder_images_rotate_in_order(self) -> None:
        self.assertTrue(str(reminder_image_path(0)).endswith("reminder_1.jpg"))
        self.assertTrue(str(reminder_image_path(1)).endswith("reminder_2.jpg"))
        self.assertTrue(str(reminder_image_path(2)).endswith("reminder_3.jpg"))
        self.assertTrue(str(reminder_image_path(3)).endswith("reminder_1.jpg"))


if __name__ == "__main__":
    unittest.main()
