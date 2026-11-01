"""Build small XLSX files for tests."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape
import zipfile


def _column(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def build_xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    """Create a workbook; strings go to the shared strings table."""
    strings: list[str] = []

    def sheet_xml(rows: list[list[object]]) -> str:
        body = []
        for row_number, row in enumerate(rows, start=1):
            cells = []
            for col, value in enumerate(row):
                ref = f"{_column(col)}{row_number}"
                if value is None:
                    continue
                if isinstance(value, str):
                    if value not in strings:
                        strings.append(value)
                    cells.append(
                        f'<c r="{ref}" t="s"><v>{strings.index(value)}</v></c>'
                    )
                else:
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            body.append(f'<row r="{row_number}">{"".join(cells)}</row>')
        return (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(body)}</sheetData></worksheet>"
        )

    sheet_bodies = [sheet_xml(rows) for rows in sheets.values()]
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, name in enumerate(sheets, start=1)
        )
        + "</sheets></workbook>"
    )
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Relationships>"
    )
    shared = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join(f"<si><t>{escape(text)}</t></si>" for text in strings)
        + "</sst>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/sharedStrings.xml", shared)
        for i, body in enumerate(sheet_bodies, start=1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", body)
    return buffer.getvalue()
