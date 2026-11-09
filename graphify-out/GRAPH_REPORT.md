# Graph Report - ArchiveApp  (2026-11-06)

## Corpus Check
- 34 files · ~26,699 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: .gz 2, (none) 1, .ini 1)

## Summary
- 616 nodes · 1608 edges · 21 communities (17 shown, 4 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 258 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1f9a61ad`
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
- main_window.py
- Office Document Archive
- test_phase3.py
- PendingWindow
- .update_document
- services.py
- AGENTS.md
- CLAUDE.md
- dev/README.md
- test_phase4.py

## God Nodes (most connected - your core abstractions)
1. `Archive` - 84 edges
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
- `8. Next steps (suggested order)` --references--> `Archive`  [INFERRED]
  HANDOFF.md → services.py
- `4. Data Model` --references--> `tag_id()`  [INFERRED]
  docs/ARCHIVE_SYSTEM_PLAN.md → test_phase3.py

## Import Cycles
- None detected.

## Communities (21 total, 4 thin omitted)

### Community 0 - "Archive"
Cohesion: 0.10
Nodes (4): Archive, _now(), t_check_integrity(), t_field_management()

### Community 1 - "test_phase1.py"
Cohesion: 0.16
Nodes (17): DuplicateFileError, _like(), archive_files(), raises(), scan(), t_add_document(), t_atomic(), t_create_type() (+9 more)

### Community 2 - "TypeManager"
Cohesion: 0.06
Nodes (9): ActivityLog, AskText, ChoiceDialog, ModalWindow, CheckDialog, SettingsWindow, TagManager, FieldDialog (+1 more)

### Community 4 - "DocumentDialog"
Cohesion: 0.08
Nodes (3): DocumentDialog, FieldBuilderDialog, AutoSuggestEntry

### Community 5 - "backup.py"
Cohesion: 0.08
Nodes (13): backup_root(), BackupError, check_destination(), list_snapshots(), restore_backup(), run_backup(), connect(), migrate() (+5 more)

### Community 6 - "_rank"
Cohesion: 0.13
Nodes (5): _rank(), t_seed(), t_suggest_types(), t_tags(), t_similar_tags()

### Community 7 - "Office Document Archive System: Project Plan"
Cohesion: 0.08
Nodes (23): 10. Security and Compliance, 11. Backup and Continuity, 12. Office Readiness, 13. Open Decisions, 14. Next Step, 1. Overview, 2. Core Workflow, 3. Architecture (+15 more)

### Community 8 - "key"
Cohesion: 0.23
Nodes (5): _clean_options(), DuplicateError, key(), norm(), t_tag_rename()

### Community 9 - "TagInput"
Cohesion: 0.13
Nodes (3): ImportDialog, FlowFrame, TagInput

### Community 10 - "test_phase4b.py"
Cohesion: 0.08
Nodes (18): pump(), shot(), sha256_file(), t_audit(), t_audit_names(), t_backup_status(), t_audit(), names() (+10 more)

### Community 11 - "main_window.py"
Cohesion: 0.05
Nodes (17): main(), drive_builder(), drive_new_type(), mkpdf(), shot(), format_value(), suggest_from_list(), app_dir() (+9 more)

### Community 12 - "Office Document Archive"
Cohesion: 0.17
Nodes (11): Backup (do this weekly), Check the archive, Day to day, Files, If something goes wrong, Office Document Archive, Restore, Run (+3 more)

### Community 13 - "test_phase3.py"
Cohesion: 0.21
Nodes (11): 4. Data Model, InUseError, raises(), scan(), t_delete_type(), t_merge_types(), t_rename_type(), t_setup() (+3 more)

### Community 14 - "PendingWindow"
Cohesion: 0.12
Nodes (3): PendingWindow, _size_text(), Preview

### Community 15 - ".update_document"
Cohesion: 0.25
Nodes (3): _parse_date(), validate_value(), t_search()

### Community 21 - "services.py"
Cohesion: 0.09
Nodes (12): 10. The code graph (graphify), 1. What this is, 2. Status, 3. Environment (user's machine), 5. Architecture and conventions, 6. Data model (schema version 1), 7. Starter types (`profile.json`, 6 of ~20), 8. Next steps (suggested order) (+4 more)

### Community 28 - "test_phase4.py"
Cohesion: 0.26
Nodes (9): 4. Decisions and why (the part the code graph cannot show), ArchiveError, put(), raises(), t_import_basic(), t_import_duplicates(), t_import_failures_and_cancel(), t_import_required_type() (+1 more)

## Knowledge Gaps
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Archive` connect `Archive` to `test_phase1.py`, `backup.py`, `_rank`, `key`, `test_phase4b.py`, `main_window.py`, `test_phase3.py`, `.update_document`, `services.py`, `test_phase4.py`?**
  _High betweenness centrality (0.177) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Archive` (e.g. with `10. The code graph (graphify)` and `5. Architecture and conventions`) actually correct?**
  _`Archive` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Archive` be split into smaller, more focused modules?**
  _Cohesion score 0.09634146341463415 - nodes in this community are weakly interconnected._
- **Why does `ArchiveError` connect `test_phase4.py` to `Archive`, `test_phase1.py`, `TypeManager`, `MainWindow`, `DocumentDialog`, `key`, `TagInput`, `test_phase4b.py`, `main_window.py`, `test_phase3.py`, `PendingWindow`, `.update_document`?**
  _High betweenness centrality (0.167) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `MainWindow` (e.g. with `10. The code graph (graphify)` and `ActivityLog`) actually correct?**
  _`MainWindow` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `TypeManager` be split into smaller, more focused modules?**
  _Cohesion score 0.05789473684210526 - nodes in this community are weakly interconnected._
- **Why does `MainWindow` connect `MainWindow` to `TypeManager`, `DocumentDialog`, `backup.py`, `TagInput`, `main_window.py`, `PendingWindow`, `services.py`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._