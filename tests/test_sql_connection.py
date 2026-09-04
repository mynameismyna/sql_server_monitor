import sys
import types
import unittest


class FakePyodbcError(Exception):
    pass


fake_pyodbc = types.ModuleType("pyodbc")
fake_pyodbc.Error = FakePyodbcError
fake_pyodbc.Connection = object
sys.modules["pyodbc"] = fake_pyodbc

from sql_connection import MAX_RESULT_ROWS, QueryResult, SQLConnection


class FakeCursor:
    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.description = [("value",)]
        self.executed_queries = []
        self.closed = False

    def execute(self, query):
        self.executed_queries.append(query)
        if self.error:
            raise self.error
        return self

    def fetchall(self):
        return self.rows

    def fetchmany(self, size):
        return self.rows[:size]

    def nextset(self):
        return False

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.test_cursor = cursor
        self.rollback_calls = 0
        self.commit_calls = 0
        self.closed = False

    def cursor(self):
        return self.test_cursor

    def rollback(self):
        self.rollback_calls += 1

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.closed = True


class SQLConnectionTests(unittest.TestCase):
    def test_executes_commented_select_and_rolls_back(self):
        cursor = FakeCursor(rows=[(1,), (2,)])
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        success, result, error = sql_connection.execute_query(
            "-- diagnostic query\nSELECT value FROM dbo.Sample"
        )

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(QueryResult(["value"], [(1,), (2,)]), result)
        self.assertEqual(1, connection.rollback_calls)
        self.assertEqual(0, connection.commit_calls)
        self.assertTrue(cursor.closed)

    def test_rejects_update_before_cursor_execution(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        success, result, error = sql_connection.execute_query(
            "UPDATE dbo.Sample SET Name = 'x'"
        )

        self.assertFalse(success)
        self.assertIsNone(result)
        self.assertIn("read-only", error.lower())
        self.assertEqual([], cursor.executed_queries)
        self.assertEqual(0, connection.commit_calls)

    def test_rolls_back_when_execution_fails(self):
        cursor = FakeCursor(error=FakePyodbcError("query failed"))
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        success, _, error = sql_connection.execute_query("SELECT 1")

        self.assertFalse(success)
        self.assertIn("SQL Hatası", error)
        self.assertEqual(1, connection.rollback_calls)
        self.assertTrue(cursor.closed)

    def test_limits_large_result_sets(self):
        rows = [(value,) for value in range(MAX_RESULT_ROWS + 1)]
        cursor = FakeCursor(rows=rows)
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        success, result, _ = sql_connection.execute_query("SELECT value FROM dbo.Sample")

        self.assertTrue(success)
        self.assertEqual(MAX_RESULT_ROWS, len(result.rows))
        self.assertTrue(result.truncated)

    def test_connection_uses_tls_and_does_not_retain_password(self):
        captured = {}
        connection = FakeConnection(FakeCursor())

        def connect(connection_string, **kwargs):
            captured["connection_string"] = connection_string
            captured["kwargs"] = kwargs
            return connection

        fake_pyodbc.connect = connect
        sql_connection = SQLConnection()

        success, _ = sql_connection.connect(
            "sql.example.local",
            "master",
            "SQL Server",
            "test_user",
            "temporary-password",
        )

        self.assertTrue(success)
        self.assertIn("Encrypt=yes", captured["connection_string"])
        self.assertIn("TrustServerCertificate=no", captured["connection_string"])
        self.assertFalse(captured["kwargs"]["autocommit"])
        self.assertFalse(hasattr(sql_connection, "password"))

    def test_connection_error_redacts_password(self):
        message = SQLConnection._safe_connection_error(
            RuntimeError("login failed for temporary-password"),
            "temporary-password",
        )

        self.assertNotIn("temporary-password", message)
        self.assertIn("[REDACTED]", message)

    def test_database_identifier_is_escaped(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        success, _ = sql_connection.change_database("db]name")

        self.assertTrue(success)
        self.assertEqual("USE [db]]name]", cursor.executed_queries[0])

    def test_connection_probe_rolls_back_and_closes_cursor(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        self.assertTrue(sql_connection.is_connected())
        self.assertEqual(1, connection.rollback_calls)
        self.assertTrue(cursor.closed)

    def test_database_listing_rolls_back_and_closes_cursor(self):
        cursor = FakeCursor(rows=[("master",), ("tempdb",)])
        connection = FakeConnection(cursor)
        sql_connection = SQLConnection()
        sql_connection.connection = connection

        success, databases, error = sql_connection.get_databases()

        self.assertTrue(success)
        self.assertEqual(["master", "tempdb"], databases)
        self.assertIsNone(error)
        self.assertEqual(1, connection.rollback_calls)
        self.assertTrue(cursor.closed)


if __name__ == "__main__":
    unittest.main()
