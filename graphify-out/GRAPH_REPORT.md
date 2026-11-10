# Graph Report - ArchiveApp  (2026-11-10)

## Corpus Check
- 36 files · ~30,343 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: .bat 2, .gz 2, (none) 1)

## Summary
- 658 nodes · 1707 edges · 31 communities (22 shown, 9 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 252 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5cfa794e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Archive
- test_phase1.py
- TypeManager
- MainWindow
- DocumentDialog
- backup.py
- _rank
- Office Document Archive System: Project Plan
- key
- TagInput
- test_phase4b.py
- services.py
- Office Document Archive
- test_phase3.py
- handoff_tool.py
- ArchiveError
- ModalWindow
- gui_smoke_phase3.py
- maintenance.py
- main_window.py
- os
- services.py
- Continuing the Archive project in a free Claude chat
- DuplicateFileError
- AGENTS.md
- CLAUDE.md
- dev/README.md
- RecycleBin
- test_phase4.py
- NewTypeDialog
- .remove_orphan_files

## God Nodes (most connected - your core abstractions)
1. `Archive` - 83 edges
2. `MainWindow` - 54 edges
3. `ArchiveError` - 48 edges
4. `DocumentDialog` - 41 edges
5. `key()` - 27 edges
6. `AutoSuggestEntry` - 26 edges
7. `norm()` - 25 edges
8. `PendingWindow` - 22 edges
9. `ModalWindow` - 21 edges
10. `TypeManager` - 21 edges

## Surprising Connections (you probably didn't know these)
- `10. The code graph (graphify)` --references--> `DocumentDialog`  [INFERRED]
  HANDOFF.md → ui/add_dialog.py
- `10. The code graph (graphify)` --references--> `MainWindow`  [INFERRED]
  HANDOFF.md → ui/main_window.py
- `4. Data Model` --references--> `key()`  [INFERRED]
  docs/ARCHIVE_SYSTEM_PLAN.md → services.py
- `4. Data Model` --references--> `tag_id()`  [INFERRED]
  docs/ARCHIVE_SYSTEM_PLAN.md → test_phase3.py
- `5. Architecture and conventions` --references--> `Archive`  [INFERRED]
  HANDOFF.md → services.py

## Import Cycles
- None detected.

## Communities (31 total, 9 thin omitted)

### Community 0 - "Archive"
Cohesion: 0.10
Nodes (5): Archive, t_reopen(), t_seed(), t_backup_status(), t_field_management()

### Community 1 - "test_phase1.py"
Cohesion: 0.25
Nodes (13): archive_files(), raises(), scan(), t_add_document(), t_atomic(), t_create_type(), t_duplicate_file(), t_field_rules() (+5 more)

### Community 2 - "TypeManager"
Cohesion: 0.08
Nodes (5): CheckDialog, SettingsWindow, TagManager, FieldDialog, TypeManager

### Community 3 - "MainWindow"
Cohesion: 0.06
Nodes (5): ActivityLog, MainWindow, PendingWindow, _size_text(), Preview

### Community 4 - "DocumentDialog"
Cohesion: 0.08
Nodes (3): DocumentDialog, FieldBuilderDialog, AutoSuggestEntry

### Community 5 - "backup.py"
Cohesion: 0.11
Nodes (11): backup_root(), BackupError, check_destination(), list_snapshots(), restore_backup(), run_backup(), connect(), migrate() (+3 more)

### Community 6 - "_rank"
Cohesion: 0.15
Nodes (3): _rank(), t_suggest_types(), t_tags()

### Community 7 - "Office Document Archive System: Project Plan"
Cohesion: 0.08
Nodes (23): 10. Security and Compliance, 11. Backup and Continuity, 12. Office Readiness, 13. Open Decisions, 14. Next Step, 1. Overview, 2. Core Workflow, 3. Architecture (+15 more)

### Community 8 - "key"
Cohesion: 0.22
Nodes (5): _clean_options(), DuplicateError, key(), norm(), validate_value()

### Community 9 - "TagInput"
Cohesion: 0.13
Nodes (3): ImportDialog, FlowFrame, TagInput

### Community 10 - "test_phase4b.py"
Cohesion: 0.23
Nodes (13): pump(), shot(), names(), put(), raises(), t_changed_file_rehashed(), t_dismiss_and_restore(), t_filed_disappears() (+5 more)

### Community 11 - "services.py"
Cohesion: 0.16
Nodes (6): format_value(), _parse_date(), suggest_from_list(), open_with_default_app(), ask_new_type(), _center()

### Community 12 - "Office Document Archive"
Cohesion: 0.17
Nodes (11): Backup (do this weekly), Check the archive, Day to day, Files, If something goes wrong, Office Document Archive, Restore, Run (+3 more)

### Community 13 - "test_phase3.py"
Cohesion: 0.17
Nodes (14): 4. Data Model, InUseError, _like(), raises(), scan(), t_delete_type(), t_merge_types(), t_rename_type() (+6 more)

### Community 14 - "handoff_tool.py"
Cohesion: 0.16
Nodes (23): ask(), build_bundle(), check_file(), copy_to_clipboard(), edit_error_text(), interactive(), interactive_milestone(), main() (+15 more)

### Community 15 - "ArchiveError"
Cohesion: 0.12
Nodes (4): ArchiveError, _now(), t_delete_restore_purge(), t_search()

### Community 16 - "ModalWindow"
Cohesion: 0.15
Nodes (5): ask_choice(), ask_text(), AskText, ChoiceDialog, ModalWindow

### Community 17 - "gui_smoke_phase3.py"
Cohesion: 0.16
Nodes (4): drive_builder(), drive_new_type(), mkpdf(), shot()

### Community 18 - "maintenance.py"
Cohesion: 0.21
Nodes (3): BackupDialog, _mb(), start_backup()

### Community 21 - "services.py"
Cohesion: 0.08
Nodes (16): 10. The code graph (graphify), 11. Keeping this handoff current (do this at every milestone), 12. Chat rules, 13. Milestone log, 1. What this is, 2. Status, 3. Environment (user's machine), 4. Decisions and why (the part the code graph cannot show) (+8 more)

### Community 22 - "Continuing the Archive project in a free Claude chat"
Cohesion: 0.22
Nodes (8): Continuing the Archive project in a free Claude chat, End of session (paste into the chat before you stop), First message (copy, then fill the <...>), Rules, Shortcut, Suggested order of work, What to attach, When something fails

### Community 28 - "test_phase4.py"
Cohesion: 0.18
Nodes (10): t_audit(), t_audit_names(), put(), raises(), t_audit(), t_import_basic(), t_import_duplicates(), t_import_failures_and_cancel() (+2 more)

## Knowledge Gaps
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Archive` connect `Archive` to `test_phase1.py`, `backup.py`, `_rank`, `key`, `test_phase4b.py`, `services.py`, `test_phase3.py`, `ArchiveError`, `main_window.py`, `services.py`, `DuplicateFileError`, `test_phase4.py`, `.remove_orphan_files`?**
  _High betweenness centrality (0.164) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Archive` (e.g. with `10. The code graph (graphify)` and `5. Architecture and conventions`) actually correct?**
  _`Archive` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Archive` be split into smaller, more focused modules?**
  _Cohesion score 0.1021021021021021 - nodes in this community are weakly interconnected._
- **Why does `ArchiveError` connect `ArchiveError` to `Archive`, `test_phase1.py`, `TypeManager`, `MainWindow`, `DocumentDialog`, `key`, `TagInput`, `test_phase4b.py`, `services.py`, `test_phase3.py`, `ModalWindow`, `DuplicateFileError`, `RecycleBin`, `test_phase4.py`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `MainWindow` (e.g. with `10. The code graph (graphify)` and `ActivityLog`) actually correct?**
  _`MainWindow` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `TypeManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07627118644067797 - nodes in this community are weakly interconnected._
- **Why does `MainWindow` connect `MainWindow` to `TypeManager`, `DocumentDialog`, `backup.py`, `TagInput`, `gui_smoke_phase3.py`, `main_window.py`, `services.py`, `RecycleBin`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._