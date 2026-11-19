r"""build.py - builds the program into release\OfficeArchive and checks it.

Run from the ArchiveApp folder:   .venv\Scripts\python build.py

- Builds with PyInstaller (--onedir, no console window) using this Python, so Device Guard is happy.
- Output goes to release\OfficeArchive. It never touches the folder you actually run the program from,
  and never touches any data folder.
- Copies profile.json and README.md next to the .exe, then runs the .exe with --selftest.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "OfficeArchive"
OUT = HERE / "release"
APP = OUT / NAME
HIDDEN = ["webserver", "waitress", "flask", "jinja2", "markupsafe", "werkzeug", "openpyxl",
          "pytesseract", "selftest", "winstartup", "thumbs"]


def main():
    if subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True).returncode != 0:
        raise SystemExit("PyInstaller is not installed for this Python. Run: .venv\\Scripts\\python -m pip install pyinstaller")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
           "--name", NAME, "--distpath", str(OUT), "--workpath", str(HERE / "build"),
           "--specpath", str(HERE / "build"), "--paths", str(HERE),
           "--collect-submodules", "waitress"]
    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]
    cmd.append(str(HERE / "app.py"))
    print("Building... (this takes a few minutes)")
    if subprocess.run(cmd, cwd=str(HERE)).returncode != 0:
        raise SystemExit("The build failed. Read the messages above and tell me the last lines.")

    for extra in ("profile.json", "README.md"):
        if (HERE / extra).is_file():
            shutil.copy2(HERE / extra, APP / extra)
        else:
            print(f"Note: {extra} not found next to build.py, so it was not copied.")
    (APP / "config.ini.example").write_text(
        "; Copy this file to config.ini (same folder as OfficeArchive.exe) to keep your data somewhere else.\n"
        "[paths]\ndata_dir = C:\\OfficeArchiveData\n", encoding="utf-8")

    exe = APP / f"{NAME}.exe"
    result = APP / "selftest_result.txt"
    result.unlink(missing_ok=True)
    print("\nRunning the self-test of the built program...")
    try:
        subprocess.run([str(exe), "--selftest"], timeout=300)
    except subprocess.TimeoutExpired:
        raise SystemExit("The self-test did not finish in 5 minutes.")
    if not result.is_file():
        raise SystemExit("The built program did not write selftest_result.txt, so it could not start. "
                         "Run it by hand and read app.log in its data folder.")
    text = result.read_text(encoding="utf-8")
    print(text)
    print(f"Built: {APP}")
    sys.exit(0 if "SELF-TEST PASSED" in text else 1)


if __name__ == "__main__":
    main()
