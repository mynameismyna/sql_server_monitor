import re
from typing import Tuple


_BLOCKED_TOKENS = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|"
    r"EXEC|EXECUTE|GRANT|DENY|REVOKE|BACKUP|RESTORE|DBCC|KILL|"
    r"SHUTDOWN|BULK|OPENROWSET|OPENDATASOURCE|OPENQUERY|WAITFOR|"
    r"COMMIT|ROLLBACK|USE|INTO|SET|DECLARE|RECONFIGURE|CHECKPOINT|"
    r"WRITETEXT|UPDATETEXT|REVERT)\b",
    re.IGNORECASE,
)
_BLOCKED_TRANSACTION = re.compile(r"\b(?:BEGIN|SAVE)\s+(?:TRAN|TRANSACTION)\b", re.IGNORECASE)
_BLOCKED_SEQUENCE = re.compile(r"\bNEXT\s+VALUE\s+FOR\b", re.IGNORECASE)
_ALLOWED_START_TOKENS = {"SELECT", "WITH"}


def validate_read_only_query(query: str) -> Tuple[bool, str]:
    if not query or not query.strip():
        return False, "Sorgu boş olamaz."

    normalized = _strip_comments_literals_and_identifiers(query)
    statement = normalized.strip().lstrip(";").strip()
    statement_without_terminator = statement.rstrip(";").rstrip()
    if ";" in statement_without_terminator:
        return False, "Tek seferde yalnızca bir read-only SQL ifadesi çalıştırılabilir."

    first_token_match = re.search(r"\b[A-Z]+\b", normalized, re.IGNORECASE)
    if not first_token_match:
        return False, "Çalıştırılabilir bir SQL ifadesi bulunamadı."

    first_token = first_token_match.group(0).upper()
    if first_token not in _ALLOWED_START_TOKENS:
        return False, "Yalnızca read-only SELECT ve CTE sorgularına izin verilir."

    blocked_match = _BLOCKED_TOKENS.search(normalized)
    if blocked_match:
        return False, f"Read-only modda {blocked_match.group(0).upper()} ifadesine izin verilmez."

    if _BLOCKED_TRANSACTION.search(normalized):
        return False, "Read-only modda transaction komutlarına izin verilmez."

    if _BLOCKED_SEQUENCE.search(normalized):
        return False, "Read-only modda sequence değeri üretmeye izin verilmez."

    return True, ""


def _strip_comments_literals_and_identifiers(query: str) -> str:
    output = []
    index = 0
    length = len(query)

    while index < length:
        current = query[index]
        next_character = query[index + 1] if index + 1 < length else ""

        if current == "-" and next_character == "-":
            output.extend("  ")
            index += 2
            while index < length and query[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue

        if current == "/" and next_character == "*":
            output.extend("  ")
            index += 2
            depth = 1
            while index < length and depth:
                following = query[index + 1] if index + 1 < length else ""
                if query[index] == "/" and following == "*":
                    depth += 1
                    output.extend("  ")
                    index += 2
                elif query[index] == "*" and following == "/":
                    depth -= 1
                    output.extend("  ")
                    index += 2
                else:
                    output.append("\n" if query[index] == "\n" else " ")
                    index += 1
            continue

        if current == "'":
            output.append(" ")
            index += 1
            while index < length:
                if query[index] == "'":
                    if index + 1 < length and query[index + 1] == "'":
                        output.extend("  ")
                        index += 2
                        continue
                    output.append(" ")
                    index += 1
                    break
                output.append("\n" if query[index] == "\n" else " ")
                index += 1
            continue

        if current == '"':
            output.append(" ")
            index += 1
            while index < length:
                if query[index] == '"':
                    if index + 1 < length and query[index + 1] == '"':
                        output.extend("  ")
                        index += 2
                        continue
                    output.append(" ")
                    index += 1
                    break
                output.append("\n" if query[index] == "\n" else " ")
                index += 1
            continue

        if current == "[":
            output.append(" ")
            index += 1
            while index < length:
                if query[index] == "]":
                    if index + 1 < length and query[index + 1] == "]":
                        output.extend("  ")
                        index += 2
                        continue
                    output.append(" ")
                    index += 1
                    break
                output.append("\n" if query[index] == "\n" else " ")
                index += 1
            continue

        output.append(current)
        index += 1

    return "".join(output)
