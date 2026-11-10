# Instructions for AI coding assistants

1. Read `HANDOFF.md` fully (status, decisions, conventions, task board). Then `graphify-out/GRAPH_REPORT.md` for the code map.
2. Work on the task marked `[next]` in HANDOFF.md section 8, unless the user says otherwise.
3. All business rules go in `services.py` with tests. The UI never touches SQL.
4. Never commit or share `data\`, `backups\`, scans or `config.ini` (confidential).
5. Windows + Device Guard: use `python -m pip` and `python -m PyInstaller`.
6. Run `test_phase1.py`, `test_phase3.py`, any newer `test_*.py` and the `dev/` GUI smoke tests after changes. Say what you could not test.
7. **Keep HANDOFF.md current.** When a task is finished and its tests pass, run:
   `.venv\Scripts\python tools\handoff_tool.py --milestone <id> --note "what was done, what is untested"`
   If you cannot run commands, give the user that exact command with the id and note filled in.
   Edit by hand, keeping the formats: new decisions (section 4), conventions (5), schema (6), and new tasks in section 8,
   one line each: `- [todo] id | title | files | what to do`. Never renumber ids. See HANDOFF.md section 11.
