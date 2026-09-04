import json
import os
import tempfile
import unittest
from pathlib import Path

from config_manager import CONFIG_FILE, ConfigManager


class ConfigManagerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.original_directory = os.getcwd()
        self.temp_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temp_directory.name)

    def tearDown(self):
        os.chdir(self.original_directory)
        self.temp_directory.cleanup()

    def test_save_connection_does_not_persist_password_field(self):
        saved = ConfigManager.save_connection(
            "sql.example.local",
            "master",
            "SQL Server",
            "test_user",
        )

        self.assertTrue(saved)
        config = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
        self.assertNotIn("password", config)
        self.assertEqual("test_user", config["username"])

    def test_load_connection_removes_legacy_password_field(self):
        config_path = Path("connection_config.json")
        config_path.write_text(
            json.dumps(
                {
                    "server": "sql.example.local",
                    "database": "master",
                    "auth_type": "SQL Server",
                    "username": "test_user",
                    "password": "legacy-placeholder",
                }
            ),
            encoding="utf-8",
        )

        loaded = ConfigManager.load_connection()
        persisted = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertNotIn("password", loaded)
        self.assertNotIn("password", persisted)


if __name__ == "__main__":
    unittest.main()
