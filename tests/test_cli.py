from pathlib import Path

from print_color_preflight.cli import main


def test_inspect_cli_writes_json(rgb_pdf: Path, tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    result = main(["inspect", str(rgb_pdf), "--json", str(report)])
    assert result == 0
    assert '"untagged-rgb"' in report.read_text(encoding="utf-8")


def test_inspect_cli_can_fail_on_warning(rgb_pdf: Path) -> None:
    assert main(["inspect", str(rgb_pdf), "--fail-on", "warning"]) == 1


def test_profile_cli_reports_validation_error(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "bad.icc"
    path.write_bytes(b"bad")
    assert main(["profile", str(path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_profile_and_plan_commands(rgb_pdf: Path, cmyk_profile: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["profile", str(cmyk_profile), "--require-cmyk-output"]) == 0
    assert (
        main(
            [
                "plan",
                str(rgb_pdf),
                "--profile",
                str(cmyk_profile),
                "--intent",
                "relative-colorimetric",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"pdfx_certification"' in output


def test_doctor_reports_dependency(monkeypatch, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr("print_color_preflight.cli.find_ghostscript", lambda _: executable)
    monkeypatch.setattr(
        "print_color_preflight.cli.ghostscript_version", lambda _: "Ghostscript test"
    )
    assert main(["doctor", "--ghostscript", str(executable)]) == 0
    assert "Ghostscript test" in capsys.readouterr().out
