# Graph Report - ArchiveApp  (2026-11-13)

## Corpus Check
- 50 files · ~42,858 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 18 file(s) not represented in the graph (top: .bak4c 5, .bak5 3, .bat 2)

## Summary
- 858 nodes · 2165 edges · 42 communities (27 shown, 15 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 370 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ff0a67fb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Archive
- .add_document
- TypeManager
- MainWindow
- DocumentDialog
- .move_field
- _rank
- Office Document Archive System: Project Plan
- ._log
- TagInput
- gui_smoke_phase3.py
- services.py
- Office Document Archive
- .add_document
- handoff_tool.py
- ArchiveError
- ModalWindow
- test_phase4d.py
- maintenance.py
- PendingWindow
- test_phase4b.py
- Storage
- Continuing the Archive project in a free Claude chat
- OcrDialog
- AGENTS.md
- CLAUDE.md
- dev/README.md
- HANDOFF - Office Document Archive
- test_phase4.py
- test_phase5.py
- activity_log.py
- test_phase3.py
- webserver.py
- .add_files
- BackupDialog
- create_app
- t_real_server
- .public_document
- RecycleBin
- .public_tags
- .remove_orphan_files

## God Nodes (most connected - your core abstractions)
1. `Archive` - 108 edges
2. `ArchiveError` - 59 edges
3. `MainWindow` - 52 edges
4. `DocumentDialog` - 40 edges
5. `key()` - 27 edges
6. `AutoSuggestEntry` - 26 edges
7. `norm()` - 25 edges
8. `ModalWindow` - 23 edges
9. `PendingWindow` - 21 edges
10. `TypeManager` - 20 edges

## Surprising Connections (you probably didn't know these)
- `4. Data Model` --references--> `key()`  [INFERRED]
  docs/ARCHIVE_SYSTEM_PLAN.md → services.py
- `10. The code graph (graphify)` --references--> `MainWindow`  [INFERRED]
  HANDOFF.md → ui/main_window.py
- `10. The code graph (graphify)` --references--> `DocumentDialog`  [INFERRED]
  HANDOFF.md → ui/add_dialog.py
- `4. Data Model` --references--> `tag_id()`  [INFERRED]
  docs/ARCHIVE_SYSTEM_PLAN.md → test_phase3.py
- `DocumentDialog` --uses--> `ArchiveError`  [INFERRED]
  ui/add_dialog.py → services.py

## Import Cycles
- None detected.

## Communities (42 total, 15 thin omitted)

### Community 0 - "Archive"
Cohesion: 0.16
Nodes (4): main(), Archive, t_reopen(), t_backup_status()

### Community 1 - ".add_document"
Cohesion: 0.10
Nodes (18): extract_text(), find_tesseract(), make_engine(), engine(), OcrUnavailable, _pymupdf(), fake_engine(), mkfile() (+10 more)

### Community 2 - "TypeManager"
Cohesion: 0.07
Nodes (5): CheckDialog, SettingsWindow, TagManager, FieldDialog, TypeManager

### Community 3 - "MainWindow"
Cohesion: 0.07
Nodes (3): open_with_default_app(), MainWindow, WebDialog

### Community 4 - "DocumentDialog"
Cohesion: 0.09
Nodes (3): DocumentDialog, FieldBuilderDialog, AutoSuggestEntry

### Community 6 - "_rank"
Cohesion: 0.14
Nodes (4): _rank(), t_seed(), t_suggest_types(), t_tags()

### Community 7 - "Office Document Archive System: Project Plan"
Cohesion: 0.08
Nodes (24): 10. Security and Compliance, 11. Backup and Continuity, 12. Office Readiness, 13. Open Decisions, 14. Next Step, 1. Overview, 2. Core Workflow, 3. Architecture (+16 more)

### Community 8 - "._log"
Cohesion: 0.13
Nodes (6): _clean_options(), DuplicateError, key(), norm(), _now(), validate_value()

### Community 9 - "TagInput"
Cohesion: 0.13
Nodes (3): ImportDialog, FlowFrame, TagInput

### Community 10 - "gui_smoke_phase3.py"
Cohesion: 0.17
Nodes (4): drive_builder(), drive_new_type(), mkpdf(), shot()

### Community 11 - "services.py"
Cohesion: 0.11
Nodes (8): _csv_safe(), format_value(), _parse_date(), suggest_from_list(), ask_new_type(), _center(), _make_modal(), NewTypeDialog

### Community 12 - "Office Document Archive"
Cohesion: 0.17
Nodes (11): Backup (do this weekly), Check the archive, Day to day, Files, If something goes wrong, Office Document Archive, Restore, Run (+3 more)

### Community 13 - ".add_document"
Cohesion: 0.20
Nodes (15): _like(), archive_files(), raises(), scan(), t_add_document(), t_atomic(), t_create_type(), t_duplicate_file() (+7 more)

### Community 14 - "handoff_tool.py"
Cohesion: 0.07
Nodes (33): apply(), main(), main(), prepare(), load(), patch(), 5. Architecture and conventions, app_dir() (+25 more)

### Community 16 - "ModalWindow"
Cohesion: 0.17
Nodes (5): ask_choice(), ask_text(), AskText, ChoiceDialog, ModalWindow

### Community 17 - "test_phase4d.py"
Cohesion: 0.09
Nodes (18): CountCalls, mkfile(), mkpdf(), mkpng(), raises(), t_export_csv(), t_export_errors(), t_export_filters() (+10 more)

### Community 19 - "PendingWindow"
Cohesion: 0.12
Nodes (3): PendingWindow, _size_text(), Preview

### Community 20 - "test_phase4b.py"
Cohesion: 0.08
Nodes (23): backup_root(), BackupError, check_destination(), list_snapshots(), restore_backup(), run_backup(), connect(), migrate() (+15 more)

### Community 22 - "Continuing the Archive project in a free Claude chat"
Cohesion: 0.22
Nodes (8): Continuing the Archive project in a free Claude chat, End of session (paste into the chat before you stop), First message (copy, then fill the <...>), Rules, Shortcut, Suggested order of work, What to attach, When something fails

### Community 27 - "HANDOFF - Office Document Archive"
Cohesion: 0.14
Nodes (13): 10. The code graph (graphify), 11. Keeping this handoff current (do this at every milestone), 12. Chat rules, 13. Milestone log, 1. What this is, 2. Status, 3. Environment (user's machine), 4. Decisions and why (the part the code graph cannot show) (+5 more)

### Community 28 - "test_phase4.py"
Cohesion: 0.14
Nodes (14): t_audit(), t_audit_names(), put(), raises(), t_audit(), t_import_basic(), t_import_duplicates(), t_import_failures_and_cancel() (+6 more)

### Community 29 - "test_phase5.py"
Cohesion: 0.20
Nodes (14): client(), mkfile(), mkpng(), raises(), setup_docs(), t_public_search(), t_read_only_archive(), t_route_document() (+6 more)

### Community 31 - "test_phase3.py"
Cohesion: 0.20
Nodes (13): InUseError, raises(), scan(), t_backup_and_restore(), t_delete_type(), t_merge_types(), t_rename_type(), t_setup() (+5 more)

### Community 32 - "webserver.py"
Cohesion: 0.15
Nodes (5): free_port(), t_autostart(), t_lan_addresses(), _check_port_free(), lan_addresses()

### Community 35 - "create_app"
Cohesion: 0.26
Nodes (9): create_app(), archive(), document(), document_file(), index(), page(), thumb(), _ext() (+1 more)

### Community 37 - "t_real_server"
Cohesion: 0.36
Nodes (3): t_real_server(), autostart(), WebServer

### Community 38 - ".public_document"
Cohesion: 0.25
Nodes (3): t_public_document(), t_public_file(), t_public_thumbnail()

## Knowledge Gaps
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Archive` connect `Archive` to `.add_document`, `.move_field`, `_rank`, `._log`, `services.py`, `.add_document`, `handoff_tool.py`, `ArchiveError`, `test_phase4d.py`, `maintenance.py`, `test_phase4b.py`, `OcrDialog`, `HANDOFF - Office Document Archive`, `test_phase4.py`, `test_phase5.py`, `test_phase3.py`, `.add_files`, `create_app`, `.public_document`, `.public_tags`, `.remove_orphan_files`?**
  _High betweenness centrality (0.213) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `Archive` (e.g. with `10. The code graph (graphify)` and `5. Architecture and conventions`) actually correct?**
  _`Archive` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `.add_document` be split into smaller, more focused modules?**
  _Cohesion score 0.09841269841269841 - nodes in this community are weakly interconnected._
- **Why does `ArchiveError` connect `ArchiveError` to `Archive`, `.add_document`, `TypeManager`, `MainWindow`, `DocumentDialog`, `.move_field`, `._log`, `TagInput`, `services.py`, `.add_document`, `ModalWindow`, `test_phase4d.py`, `maintenance.py`, `PendingWindow`, `test_phase4b.py`, `test_phase4.py`, `test_phase5.py`, `test_phase3.py`, `.add_files`, `RecycleBin`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `ArchiveError` (e.g. with `t_delete_restore_purge()` and `t_delete_type()`) actually correct?**
  _`ArchiveError` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `TypeManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07431693989071038 - nodes in this community are weakly interconnected._
- **Why does `MainWindow` connect `MainWindow` to `Archive`, `TypeManager`, `RecycleBin`, `gui_smoke_phase3.py`, `maintenance.py`, `PendingWindow`, `test_phase4b.py`, `OcrDialog`, `HANDOFF - Office Document Archive`, `activity_log.py`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._