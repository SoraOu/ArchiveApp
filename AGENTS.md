# Instructions for AI coding assistants

1. Read `HANDOFF.md` fully before doing anything (status, decisions, conventions, next steps).
2. Read `graphify-out/GRAPH_REPORT.md` for the code map before searching raw files. Use
   `graphify query/explain/path` for specific questions.
3. All business rules go in `services.py` with tests. The UI never touches SQL.
4. Never commit or share `data\`, `backups\`, scans or `config.ini` (confidential).
5. Windows + Device Guard: use `python -m pip` and `python -m PyInstaller`.
6. Run `test_phase1.py`, `test_phase3.py` and the `dev/` GUI smoke tests after changes; say what you could not test.
