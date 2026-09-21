import unittest

from predefined_queries import PREDEFINED_QUERIES, search_predefined_queries
from query_guides import (
    QUERY_GUIDES,
    SITUATION_PLAYBOOKS,
    format_guide_html,
    format_situation_html,
    get_query_guide,
    get_situation_playbooks,
)


class QueryGuideTests(unittest.TestCase):
    def test_every_executable_query_has_guide(self):
        executable = [name for name in PREDEFINED_QUERIES if not name.startswith("===")]
        self.assertEqual(120, len(executable))
        self.assertEqual(len(executable), len(QUERY_GUIDES))
        for name in executable:
            with self.subTest(name=name):
                guide = get_query_guide(name)
                self.assertTrue(guide["summary"])
                self.assertTrue(guide["when"])
                self.assertTrue(guide["helps_with"])

    def test_related_queries_exist(self):
        for name, guide in QUERY_GUIDES.items():
            for related in (guide.get("before") or []) + (guide.get("after") or []):
                with self.subTest(name=name, related=related):
                    self.assertIn(related, QUERY_GUIDES)

    def test_situation_playbooks_reference_known_queries(self):
        self.assertGreaterEqual(len(get_situation_playbooks()), 10)
        for situation in SITUATION_PLAYBOOKS:
            self.assertTrue(situation["title"])
            self.assertTrue(situation["symptoms"])
            self.assertTrue(situation["steps"])
            for step in situation["steps"]:
                with self.subTest(situation=situation["id"], query=step["query"]):
                    self.assertIn(step["query"], QUERY_GUIDES)
                    self.assertTrue(step.get("note"))

    def test_guide_html_contains_sections_and_links(self):
        html = format_guide_html("Bekleyen İşlemler (Blocking)")
        self.assertIn("Ne zaman kullanılmalı", html)
        self.assertIn("Hangi durumlara fayda eder", html)
        self.assertIn("query:Bloke", html)

    def test_situation_html_lists_steps(self):
        situation = SITUATION_PLAYBOOKS[0]
        html = format_situation_html(situation)
        self.assertIn("Önerilen sıra", html)
        self.assertIn("Adım 1", html)

    def test_search_finds_by_symptom_text(self):
        matches = search_predefined_queries("timeout")
        self.assertIn("Bekleyen İşlemler (Blocking)", matches)


if __name__ == "__main__":
    unittest.main()
