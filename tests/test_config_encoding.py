# SPDX-License-Identifier: MIT
"""A configuration saved by an editor or a shell that adds a byte order mark, or writes UTF-16, still loads."""

import pytest

from vyvid import cli, config

TEXT = '[framework]\nglue = "stop"\n\n[[domains]]\nname = "shared"\npath = "/somewhere"\n'


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le-bom", "utf-16-be-bom"])
def test_a_configuration_loads_in_each_encoding_a_windows_shell_writes(tmp_path, encoding):
    path = tmp_path / "config.toml"
    data = {"utf-16-le-bom": b"\xff\xfe" + TEXT.encode("utf-16-le"), "utf-16-be-bom": b"\xfe\xff" + TEXT.encode("utf-16-be")}.get(encoding)
    path.write_bytes(data if data is not None else TEXT.encode(encoding))
    loaded = config.load(path)
    assert loaded.glue == "stop" and list(loaded.domains) == ["shared"]


def test_a_vyvid_toml_and_a_manifest_load_with_a_byte_order_mark(tmp_path):
    path = tmp_path / "x.toml"
    path.write_bytes(b"\xef\xbb\xbf" + b'name = "x"\n')
    assert config.read_toml_text(path) == 'name = "x"\n'


@pytest.mark.parametrize("data", [b"\xff\xfe\x00", b'glue = "caf\xe9"\n', b"not = [toml"])
def test_a_file_that_cannot_be_read_is_a_problem_naming_it_and_no_traceback(tmp_path, capsys, monkeypatch, data):
    path = tmp_path / "config.toml"
    path.write_bytes(data)
    monkeypatch.setenv("VYVID_CONFIG", str(path))
    assert cli.main(["config"]) != 0
    said = capsys.readouterr().err
    assert str(path) in said and "Traceback" not in said


def test_a_command_rewrites_a_utf_16_configuration_as_utf_8_keeping_its_comment(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_bytes(("# mine\n" + TEXT).encode("utf-16"))
    monkeypatch.setenv("VYVID_CONFIG", str(path))
    assert cli.main(["domain", "remove", "shared"]) == 0
    written = path.read_bytes()
    assert written[:2] not in (b"\xff\xfe", b"\xfe\xff") and b"# mine" in written and b"shared" not in written
