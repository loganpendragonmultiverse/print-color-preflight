from pathlib import Path

from print_color_preflight.report import write_html_report, write_json_report


def test_reports_escape_untrusted_content(tmp_path: Path) -> None:
    data = {
        "findings": [
            {"severity": "warning", "code": "<code>", "message": "<script>x</script>", "page": 1}
        ]
    }
    html_path = tmp_path / "report.html"
    json_path = tmp_path / "report.json"
    write_html_report(data, html_path, "<Title>")
    write_json_report(data, json_path)
    rendered = html_path.read_text(encoding="utf-8")
    assert "<script>x</script>" not in rendered
    assert "&lt;script&gt;x&lt;/script&gt;" in rendered
    assert json_path.read_text(encoding="utf-8").endswith("\n")
