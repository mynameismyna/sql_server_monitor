import unittest

from predefined_queries import PREDEFINED_QUERIES
from query_safety import validate_read_only_query


class PredefinedQuerySafetyTests(unittest.TestCase):
    def test_all_executable_predefined_queries_are_read_only(self):
        executable_queries = {
            name: query
            for name, query in PREDEFINED_QUERIES.items()
            if not name.startswith("===")
        }

        self.assertEqual(120, len(executable_queries))
        for name, query in executable_queries.items():
            with self.subTest(name=name):
                allowed, reason = validate_read_only_query(query)
                self.assertTrue(allowed, reason)

    def test_advanced_catalog_helpers(self):
        from predefined_queries import (
            count_executable_queries,
            get_predefined_categories,
            get_query_description,
            search_predefined_queries,
        )

        self.assertEqual(120, count_executable_queries())
        categories = get_predefined_categories()
        self.assertGreaterEqual(len(categories), 20)
        self.assertIn("SUNUCU SAĞLIK ÖZETİ", categories)
        self.assertTrue(any("RPO" in name for name in search_predefined_queries("rpo")))
        self.assertIn("ring buffer", get_query_description("SQL Server Hataları (Son 24 Saat)").lower())


if __name__ == "__main__":
    unittest.main()
