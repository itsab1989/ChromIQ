"""The command boxes, pasted into the real shells they are written for.

``test_argyll_command_boxes.py`` proves that a box shows the argument list the
button runs, reading the text with each shell's rules. This file checks those
rules against the shells themselves: each line the box would show is run, with
the ArgyllCMS tool replaced by a small Python program that records the
arguments it receives and the folder it runs in, and the record must equal the
argument list ChromIQ hands to ArgyllCMS.

On Windows that is Windows PowerShell 5.1 (``powershell``, the terminal
Windows opens by default) and PowerShell 7 (``pwsh``) when it is installed; on
macOS and Linux ``sh``, ``bash`` and ``zsh`` (the macOS default), each where
present. A shell that is not installed is skipped, never faked.

Written for 4.3.31, when the Windows CI showed that nothing had ever pasted
the PowerShell text into PowerShell.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import workflow.argyll_command_text as act
from tests.test_argyll_command_boxes import WINDOWS_ARGUMENTS

_ECHO = (
    "import json, os, sys\n"
    "with open(sys.argv[1], 'w', encoding='utf-8') as f:\n"
    "    json.dump({'cwd': os.getcwd(), 'args': sys.argv[2:]}, f)\n"
)

#: Texts every shell must hand over unchanged, beyond the Windows paths.
_TEXTS = [
    "/Users/Jürgen/ChromIQ/a folder with spaces/My Printer",
    "Tom & Jerry's 50%", "it's $HOME `date` $(date) !x *.ti3 ?",
    "=x", "a=b", "~", "~/x", "-s1.0", "two  spaces", "tab\tin it",
]

if os.name == "nt":
    _SHELLS = {"powershell": ["powershell"], "pwsh": ["pwsh"]}
else:
    _SHELLS = {"sh": ["sh"], "bash": ["bash"], "zsh": ["zsh"]}


def _shell(name: str) -> "list[str]":
    exe = shutil.which(_SHELLS[name][0])
    if exe is None:
        pytest.skip(f"{name} is not installed here")
    if name in ("powershell", "pwsh"):
        return [exe, "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File"]
    return [exe]


def _run_pasted(shell: "list[str]", work: Path, folder: Path,
                args: "list[str]") -> dict:
    """Run what the printcal box would show for *folder* and *args* (the
    change of folder, then the command) in *shell*; return what arrived."""
    echo = work / "echo_args.py"
    echo.write_text(_ECHO, encoding="utf-8")
    out = work / "arrived.json"
    if out.exists():
        out.unlink()
    line = act.command_line("TOOL", list(args))
    assert line.startswith("TOOL")
    program = " ".join(act.quote_arg(str(p))
                       for p in (sys.executable, echo, out))
    if act._windows():
        program = "& " + program
    script = act.change_folder_line(folder) + "\n" + program + line[4:] + "\n"
    suffix = ".ps1" if act._windows() else ".sh"
    path = work / ("pasted" + suffix)
    # A BOM, or Windows PowerShell 5.1 reads the file in the ANSI code page.
    path.write_text(script, encoding="utf-8-sig" if act._windows()
                    else "utf-8")
    try:
        done = subprocess.run(shell + [str(path)], capture_output=True,
                              timeout=180)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{shell[0]} did not finish within 180 s")
    assert out.exists(), (
        f"{shell[0]} did not run the pasted command:\n{script}\n"
        f"exit {done.returncode}\n"
        f"{done.stdout.decode('utf-8', 'replace')}\n"
        f"{done.stderr.decode('utf-8', 'replace')}")
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.mark.parametrize("shell_name", sorted(_SHELLS))
def test_every_argument_arrives_as_chromiq_passes_it(tmp_path, shell_name):
    shell = _shell(shell_name)
    folder = tmp_path / "a [b] folder, Jürgen's 100%"
    folder.mkdir()
    wrong = []
    for arg in WINDOWS_ARGUMENTS + _TEXTS:
        got = _run_pasted(shell, tmp_path, folder, ["-D", arg, "last"])
        if got["args"] != ["-D", arg, "last"]:
            wrong.append(f"{arg!r} arrived as {got['args']!r}")
        assert Path(got["cwd"]).resolve() == folder.resolve()
    assert not wrong, (f"{shell_name} received a different argument from "
                       "the box's text:\n" + "\n".join(wrong))


@pytest.mark.parametrize("shell_name", sorted(_SHELLS))
def test_a_whole_colprof_argument_list_arrives_unchanged(tmp_path,
                                                         shell_name):
    """One line with everything a real colprof call carries, side by side."""
    shell = _shell(shell_name)
    folder = tmp_path / "run1"
    folder.mkdir()
    args = ["-v", "-D", "Epson P900 \u2013 Hahnemühle's", "-qh", "-al",
            "-l250", "-s1.0", "-r0.50", "-S",
            str(tmp_path / "a folder with spaces" / "My Printer.icc"),
            str(tmp_path / "plain" / "Fresh")]
    assert _run_pasted(shell, tmp_path, folder, args)["args"] == args
