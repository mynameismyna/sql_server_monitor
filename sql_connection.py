from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Lock
from typing import Any, List, Optional, Tuple

import pyodbc

from query_safety import validate_read_only_query


MAX_RESULT_ROWS = 10000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryResult:
    columns: List[str]
    rows: List[Any]
    truncated: bool = False


class SQLConnection:
    def __init__(self):
        self.connection: Optional[pyodbc.Connection] = None
        self.server = ""
        self.database = ""
        self.auth_type = "Windows"
        self.username = ""
        self._query_lock = Lock()

    def connect(
        self,
        server: str,
        database: str,
        auth_type: str = "Windows",
        username: str = "",
        password: str = "",
    ) -> Tuple[bool, str]:
        if auth_type not in {"Windows", "SQL Server"}:
            return False, "Desteklenmeyen kimlik doğrulama türü."

        try:
            if self.connection:
                self.connection.close()
                self.connection = None

            connection_string = self._build_connection_string(
                server,
                database,
                auth_type,
                username,
                password,
            )
            self.connection = pyodbc.connect(
                connection_string,
                timeout=10,
                autocommit=False,
            )
            self.server = server
            self.database = database
            self.auth_type = auth_type
            self.username = username
            logger.info("SQL Server bağlantısı kuruldu")
            return True, "Bağlantı başarılı!"
        except pyodbc.Error as error:
            message = self._safe_connection_error(error, password)
            logger.error(message)
            return False, message
        except Exception as error:
            message = self._safe_connection_error(error, password)
            logger.error(message)
            return False, message

    def execute_query(self, query: str) -> Tuple[bool, Any, Optional[str]]:
        if not self.connection:
            return False, None, "Önce SQL Server'a bağlanmalısınız!"

        allowed, reason = validate_read_only_query(query)
        if not allowed:
            return False, None, reason

        if not self._query_lock.acquire(blocking=False):
            return False, None, "Başka bir sorgu çalışırken yeni sorgu başlatılamaz."

        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)

            while cursor.description is None:
                if not cursor.nextset():
                    self.connection.rollback()
                    return True, QueryResult([], []), None

            columns = [column[0] for column in cursor.description]
            rows = list(cursor.fetchmany(MAX_RESULT_ROWS + 1))
            truncated = len(rows) > MAX_RESULT_ROWS
            if truncated:
                rows = rows[:MAX_RESULT_ROWS]

            self.connection.rollback()
            return True, QueryResult(columns, rows, truncated), None
        except pyodbc.Error as error:
            self._rollback_quietly()
            message = f"SQL Hatası: {error}"
            logger.error(message)
            return False, None, message
        except Exception as error:
            self._rollback_quietly()
            message = f"Beklenmeyen hata: {error}"
            logger.error(message)
            return False, None, message
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    logger.debug("Cursor kapatılamadı", exc_info=True)
            self._query_lock.release()

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("SQL Server bağlantısı kapatıldı")

    def is_connected(self) -> bool:
        if not self.connection:
            return False

        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            return True
        except pyodbc.Error:
            return False
        except Exception:
            logger.debug("Bağlantı durumu doğrulanamadı", exc_info=True)
            return False
        finally:
            self._rollback_quietly()
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    logger.debug("Cursor kapatılamadı", exc_info=True)

    def get_databases(self) -> Tuple[bool, list, Optional[str]]:
        if not self.connection:
            return False, [], "Önce SQL Server'a bağlanmalısınız!"

        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sys.databases ORDER BY name")
            databases = [row[0] for row in cursor.fetchall()]
            return True, databases, None
        except pyodbc.Error as error:
            message = f"Veritabanları alınırken hata: {error}"
            logger.error(message)
            return False, [], message
        except Exception as error:
            message = f"Beklenmeyen hata: {error}"
            logger.error(message)
            return False, [], message
        finally:
            self._rollback_quietly()
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    logger.debug("Cursor kapatılamadı", exc_info=True)

    def change_database(self, database: str) -> Tuple[bool, str]:
        if not self.connection:
            return False, "Önce SQL Server'a bağlanmalısınız!"

        cursor = None
        try:
            escaped_database = database.replace("]", "]]")
            cursor = self.connection.cursor()
            cursor.execute(f"USE [{escaped_database}]")
            self.database = database
            logger.info("Aktif veritabanı değiştirildi")
            return True, f"Veritabanı değiştirildi: {database}"
        except pyodbc.Error as error:
            message = f"Veritabanı değiştirme hatası: {error}"
            logger.error(message)
            return False, message
        except Exception as error:
            message = f"Beklenmeyen hata: {error}"
            logger.error(message)
            return False, message
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    logger.debug("Cursor kapatılamadı", exc_info=True)

    @staticmethod
    def _build_connection_string(
        server: str,
        database: str,
        auth_type: str,
        username: str,
        password: str,
    ) -> str:
        options = [
            "DRIVER={ODBC Driver 17 for SQL Server}",
            f"SERVER={SQLConnection._odbc_value(server)}",
            f"DATABASE={SQLConnection._odbc_value(database)}",
            "Encrypt=yes",
            "TrustServerCertificate=no",
        ]

        if auth_type == "Windows":
            options.append("Trusted_Connection=yes")
        else:
            options.extend(
                [
                    f"UID={SQLConnection._odbc_value(username)}",
                    f"PWD={SQLConnection._odbc_value(password)}",
                ]
            )

        return ";".join(options) + ";"

    @staticmethod
    def _odbc_value(value: str) -> str:
        return "{" + str(value).replace("}", "}}") + "}"

    @staticmethod
    def _safe_connection_error(error: Exception, password: str) -> str:
        text = str(error)
        if password:
            text = text.replace(password, "[REDACTED]")
        return f"Bağlantı hatası: {text}"

    def _rollback_quietly(self) -> None:
        if not self.connection:
            return
        try:
            self.connection.rollback()
        except Exception:
            logger.debug("Rollback tamamlanamadı", exc_info=True)
