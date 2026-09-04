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

        self.assertEqual(71, len(executable_queries))
        for name, query in executable_queries.items():
            with self.subTest(name=name):
                allowed, reason = validate_read_only_query(query)
                self.assertTrue(allowed, reason)


if __name__ == "__main__":
    unittest.main()
