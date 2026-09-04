import unittest

from query_safety import validate_read_only_query


class QuerySafetyTests(unittest.TestCase):
    def test_accepts_select_with_leading_comments(self):
        allowed, reason = validate_read_only_query(
            "-- UPDATE is mentioned only in documentation\nSELECT 1"
        )

        self.assertTrue(allowed)
        self.assertEqual("", reason)

    def test_accepts_common_table_expression(self):
        allowed, _ = validate_read_only_query(
            ";WITH values_cte AS (SELECT 1 AS value) SELECT value FROM values_cte;"
        )

        self.assertTrue(allowed)

    def test_ignores_keywords_in_literals_and_identifiers(self):
        allowed, _ = validate_read_only_query(
            "SELECT 'DELETE' AS [update], [drop], transaction_id FROM [transaction]"
        )

        self.assertTrue(allowed)

    def test_rejects_data_modification(self):
        for query in (
            "UPDATE dbo.Sample SET Name = 'x'",
            "DELETE FROM dbo.Sample",
            "INSERT INTO dbo.Sample(Name) VALUES ('x')",
            "MERGE dbo.Sample AS target USING dbo.Source AS source ON 1 = 0 WHEN NOT MATCHED THEN INSERT DEFAULT VALUES;",
        ):
            with self.subTest(query=query):
                allowed, _ = validate_read_only_query(query)
                self.assertFalse(allowed)

    def test_rejects_select_into_and_second_statement(self):
        for query in (
            "SELECT * INTO dbo.Copy FROM dbo.Source",
            "SELECT 1; DROP TABLE dbo.Sample",
            "SELECT 1; SELECT 2",
            "SELECT 1\nCHECKPOINT",
            "SELECT NEXT VALUE FOR dbo.SampleSequence",
            "WITH values_cte AS (SELECT 1 AS value) DELETE FROM values_cte",
        ):
            with self.subTest(query=query):
                allowed, _ = validate_read_only_query(query)
                self.assertFalse(allowed)

    def test_rejects_server_side_commands(self):
        for query in (
            "EXEC sys.sp_configure 'show advanced options', 1",
            "DBCC FREEPROCCACHE",
            "KILL 51",
            "BACKUP DATABASE Sample TO DISK = 'sample.bak'",
            "SELECT * FROM OPENROWSET(BULK 'sample.txt', SINGLE_CLOB) AS source",
            "SELECT 1; SAVE TRANSACTION checkpoint_name",
        ):
            with self.subTest(query=query):
                allowed, _ = validate_read_only_query(query)
                self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
