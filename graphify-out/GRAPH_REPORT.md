# Graph Report - ArchiveApp  (2026-11-10)

## Corpus Check
- 41 files · ~34,027 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: .bak4c 4, .bat 2, .gz 2)

## Summary
- 717 nodes · 1850 edges · 31 communities (21 shown, 10 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 288 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ea534462`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Archive
- .add_document
- TypeManager
- MainWindow
- DocumentDialog
- validate_value
- .similar_tag_map
- Office Document Archive System: Project Plan
- ArchiveError
- TagInput
- test_phase4b.py
- services.py
- Office Document Archive
- test_phase1.py
- handoff_tool.py
- ._log
- ModalWindow
- gui_smoke_phase3.py
- maintenance.py
- tkinter
- ocr.py
- services.py
- Continuing the Archive project in a free Claude chat
- OcrDialog
- AGENTS.md
- CLAUDE.md
- dev/README.md
- RecycleBin
- NewTypeDialog
- activity_log.py

## God Nodes (most connected - your core abstractions)
1. `Archive` - 91 edges
2. `ArchiveError` - 51 edges
3. `MainWindow` - 47 edges
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

## Communities (31 total, 10 thin omitted)

### Community 0 - "Archive"
Cohesion: 0.14
Nodes (5): Archive, t_reopen(), t_backup_status(), t_folder_missing_and_off(), t_not_set()

### Community 1 - ".add_document"
Cohesion: 0.21
Nodes (10): fake_engine(), mkfile(), ocr_rows(), raises(), t_cancel(), t_deleted_and_purge(), t_empty_and_failed(), t_pending_and_run() (+2 more)

### Community 2 - "TypeManager"
Cohesion: 0.07
Nodes (5): CheckDialog, SettingsWindow, TagManager, FieldDialog, TypeManager

### Community 3 - "MainWindow"
Cohesion: 0.06
Nodes (5): open_with_default_app(), MainWindow, PendingWindow, _size_text(), Preview

### Community 4 - "DocumentDialog"
Cohesion: 0.09
Nodes (3): DocumentDialog, FieldBuilderDialog, AutoSuggestEntry

### Community 5 - "validate_value"
Cohesion: 0.12
Nodes (3): _parse_date(), validate_value(), t_field_management()

### Community 7 - "Office Document Archive System: Project Plan"
Cohesion: 0.08
Nodes (24): 10. Security and Compliance, 11. Backup and Continuity, 12. Office Readiness, 13. Open Decisions, 14. Next Step, 1. Overview, 2. Core Workflow, 3. Architecture (+16 more)

### Community 8 - "ArchiveError"
Cohesion: 0.18
Nodes (7): ArchiveError, _clean_options(), DuplicateError, InUseError, key(), norm(), t_field_rules()

### Community 9 - "TagInput"
Cohesion: 0.13
Nodes (3): ImportDialog, FlowFrame, TagInput

### Community 10 - "test_phase4b.py"
Cohesion: 0.29
Nodes (11): pump(), shot(), names(), put(), raises(), t_changed_file_rehashed(), t_dismiss_and_restore(), t_filed_disappears() (+3 more)

### Community 11 - "services.py"
Cohesion: 0.17
Nodes (3): format_value(), suggest_from_list(), _center()

### Community 12 - "Office Document Archive"
Cohesion: 0.17
Nodes (11): Backup (do this weekly), Check the archive, Day to day, Files, If something goes wrong, Office Document Archive, Restore, Run (+3 more)

### Community 13 - "test_phase1.py"
Cohesion: 0.05
Nodes (44): DuplicateFileError, _like(), _rank(), archive_files(), raises(), scan(), t_add_document(), t_atomic() (+36 more)

### Community 14 - "handoff_tool.py"
Cohesion: 0.08
Nodes (34): apply(), main(), main(), prepare(), backup_root(), BackupError, check_destination(), list_snapshots() (+26 more)

### Community 16 - "ModalWindow"
Cohesion: 0.17
Nodes (5): ask_choice(), ask_text(), AskText, ChoiceDialog, ModalWindow

### Community 17 - "gui_smoke_phase3.py"
Cohesion: 0.15
Nodes (4): drive_builder(), drive_new_type(), mkpdf(), shot()

### Community 18 - "maintenance.py"
Cohesion: 0.15
Nodes (3): BackupDialog, _mb(), start_backup()

### Community 20 - "ocr.py"
Cohesion: 0.17
Nodes (7): extract_text(), find_tesseract(), make_engine(), engine(), OcrUnavailable, _pymupdf(), t_extract_text()

### Community 21 - "services.py"
Cohesion: 0.05
Nodes (22): connect(), migrate(), schema_version(), 10. The code graph (graphify), 11. Keeping this handoff current (do this at every milestone), 12. Chat rules, 13. Milestone log, 1. What this is (+14 more)

### Community 22 - "Continuing the Archive project in a free Claude chat"
Cohesion: 0.22
Nodes (8): Continuing the Archive project in a free Claude chat, End of session (paste into the chat before you stop), First message (copy, then fill the <...>), Rules, Shortcut, Suggested order of work, What to attach, When something fails

### Community 29 - "NewTypeDialog"
Cohesion: 0.24
Nodes (3): ask_new_type(), _make_modal(), NewTypeDialog

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Archive` connect `Archive` to `.add_document`, `validate_value`, `.similar_tag_map`, `ArchiveError`, `test_phase4b.py`, `services.py`, `test_phase1.py`, `._log`, `maintenance.py`, `tkinter`, `services.py`, `OcrDialog`, `._refresh_search_text`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Archive` (e.g. with `10. The code graph (graphify)` and `5. Architecture and conventions`) actually correct?**
  _`Archive` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Archive` be split into smaller, more focused modules?**
  _Cohesion score 0.1402116402116402 - nodes in this community are weakly interconnected._
- **Why does `ArchiveError` connect `ArchiveError` to `Archive`, `.add_document`, `TypeManager`, `MainWindow`, `DocumentDialog`, `validate_value`, `TagInput`, `test_phase4b.py`, `services.py`, `test_phase1.py`, `._log`, `ModalWindow`, `RecycleBin`, `._refresh_search_text`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `ArchiveError` (e.g. with `t_delete_restore_purge()` and `t_delete_type()`) actually correct?**
  _`ArchiveError` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Should `TypeManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07431693989071038 - nodes in this community are weakly interconnected._
- **Why does `MainWindow` connect `MainWindow` to `TypeManager`, `services.py`, `gui_smoke_phase3.py`, `tkinter`, `services.py`, `OcrDialog`, `RecycleBin`, `activity_log.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._