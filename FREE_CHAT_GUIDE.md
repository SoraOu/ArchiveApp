# Continuing the Archive project in a free Claude chat

A chat cannot see your folder, so you give it only what the task needs. Keep each chat small and focused.

## Shortcut
Run `compile_for_chat.bat` (in the ArchiveApp folder). Its menu is read from the task board in `HANDOFF.md`, so it always
offers the current tasks and their files, and the rules in the first message come from `HANDOFF.md` too. Paste the message
(already on your clipboard) into a new chat and attach `_for_chat\ALL_IN_ONE.txt`.
The sections below explain the same thing by hand.

## Rules
1. **One task per chat.** Start a new chat for each piece of work. Long chats use up your limit faster.
2. **Always attach `HANDOFF.md`.** Then attach only the files that task touches (table below).
3. **Never attach or paste** `data\`, scans, backups or `config.ini`. They are confidential.
4. **Ask for the right output format:** new modules as complete files; changes to existing files as
   "find this exact text, replace with this" blocks; tests together with the code.
5. **Always run the tests yourself** after applying a change. The chat cannot run your code, so paste any failure back as exact text.
6. **Finish every milestone the same way:** run `compile_for_chat.bat` and choose **M** (Record a milestone). It marks the task done,
   runs the tests and updates `HANDOFF.md` for you. Then run `graphify_menu.bat` option 7, `git add -A` and `git commit`.

## What to attach
| Task | Attach |
|---|---|
| Business logic (import, search, rules) | HANDOFF.md, services.py, the matching test file (and db.py for schema changes) |
| A window or dialog | HANDOFF.md, that one file from `ui\`; the chat will ask for others if needed |
| Backup / restore | HANDOFF.md, backup.py, restore.py |
| A bug | HANDOFF.md, the full error text, the file named in the error |
Tip: `graphify_menu.bat` option 5 ("explain") and option 6 ("path") show where something lives and what uses it,
so you know which file to attach.

## First message (copy, then fill the <...>)
```
I'm continuing a project mid-way. HANDOFF.md is attached: read it fully first.
I can only attach some files, so ask me for any other file you need instead of guessing its contents.
Attached: <list the files>.

Task: <one task, for example "Phase 4a: bulk import of a folder of existing scans">

Rules:
- Windows with Device Guard: commands use .venv\Scripts\python -m pip / -m PyInstaller.
- Business rules go in services.py with tests; the UI never touches SQL.
- In Archive, public methods commit; methods starting with _ never commit.
- Do not name methods or attributes on Tk widgets like Tk internals (_options, _name, _w, master...).
- Output: complete files for new modules; exact find/replace blocks for edits; tests first.
- Tell me exactly which commands to run, and say plainly what you could not test.
- Keep answers short. Ask at most one question at a time.
```

## When something fails
```
I applied your change and ran <command>. Result:
<paste the full error text>
The relevant file is attached. Fix it with the smallest change, as a find/replace block.
```

## End of session (paste into the chat before you stop)
```
List any new decisions (with the reason), new conventions and new tasks from today, each as one line in the HANDOFF.md format
(tasks: - [todo] id | title | files | what to do). Plain text. Then give me the exact handoff_tool.py --milestone command.
```
Paste those lines into the matching sections of `HANDOFF.md`, then run the milestone command.

## Suggested order of work
1. Run the Phase 2 and 3 tests and the app on your PC. Report problems first (one chat for fixes).
2. **Phase 4a bulk import**, in two chats: (a) service function and tests, (b) the import window.
3. Phase 4b watch folder, 4c OCR (install Tesseract first), 4d thumbnails.
4. Phase 5 browser view, again in small chats: server routes, then the pages, then network setup.
5. Phase 6 roles and packaging.
Collect your remaining document types and the meaning of "Source" before step 2 and put them in your first message.
