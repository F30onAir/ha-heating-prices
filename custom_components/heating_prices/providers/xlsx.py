"""Minimal XLSX reader built on the standard library.

Only what the EU Weekly Oil Bulletin workbooks need: shared strings, inline
strings and numbers, read row by row so the large history file stays cheap.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
import io
import posixpath
import re
from xml.etree import ElementTree as ET
import zipfile

from . import ParseError

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_CELL_REF = re.compile(r"^([A-Z]+)\d+$")
_EXCEL_EPOCH = date(1899, 12, 30)

CellValue = str | float


def column_index(letters: str) -> int:
    """Return the zero-based column index for column letters ("A" -> 0)."""
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def excel_date(serial: float) -> date:
    """Convert an Excel date serial number to a date."""
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        data = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    return [
        "".join(node.text or "" for node in item.iter(f"{_NS}t"))
        for item in root.iter(f"{_NS}si")
    ]


def _sheet_path(archive: zipfile.ZipFile, sheet: str | None) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheets = list(workbook.iter(f"{_NS}sheet"))
    if not sheets:
        raise ParseError("Workbook has no sheets")
    chosen = sheets[0]
    if sheet is not None:
        matches = [node for node in sheets if node.get("name") == sheet]
        if not matches:
            raise ParseError(f"Sheet {sheet!r} not found")
        chosen = matches[0]
    rel_id = chosen.get(_REL_ID)
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in rels:
        if rel.get("Id") == rel_id:
            target = rel.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join("xl", target))
    raise ParseError(f"No relationship for sheet {chosen.get('name')!r}")


def _cell_value(cell: ET.Element, strings: list[str]) -> CellValue | None:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{_NS}t"))
    value = cell.find(f"{_NS}v")
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        return strings[int(value.text)]
    if cell_type in ("str", "e"):
        return value.text
    if cell_type == "b":
        return float(value.text == "1")
    try:
        return float(value.text)
    except ValueError:
        return value.text


def iter_rows(
    content: bytes, sheet: str | None = None
) -> Iterator[dict[int, CellValue]]:
    """Yield each row of a sheet as {column index: value}, skipping empty cells."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as err:
        raise ParseError("Not an XLSX file") from err
    with archive:
        strings = _shared_strings(archive)
        with archive.open(_sheet_path(archive, sheet)) as handle:
            for _event, element in ET.iterparse(handle, events=("end",)):
                if element.tag != f"{_NS}row":
                    continue
                row: dict[int, CellValue] = {}
                for position, cell in enumerate(element.iter(f"{_NS}c")):
                    match = _CELL_REF.match(cell.get("r", ""))
                    index = column_index(match.group(1)) if match else position
                    value = _cell_value(cell, strings)
                    if value is not None and value != "":
                        row[index] = value
                yield row
                element.clear()
