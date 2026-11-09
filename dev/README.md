# dev/ - headless GUI tests

These drive the real Tkinter windows (add/edit, managers, backup, check, reminder) without a screen and
save screenshots to a temp folder. They run on **Linux** (the Windows machine does not need them).

Setup (Debian/Ubuntu):
```
apt-get install -y python3-tk xvfb
pip install pillow pymupdf
```
Run from the project folder:
```
xvfb-run -a -s "-screen 0 1400x900x24" python3 dev/gui_smoke_phase2.py
xvfb-run -a -s "-screen 0 1400x900x24" python3 dev/gui_smoke_phase3.py
```
Every line should print PASS and the last line `ERRORS: none`.

Look at the screenshots after any UI change. They caught layout and Tk-collision bugs that unit tests cannot.
