# 2026 Architecture

> **Target implementation:** 2026 modernization of `legacy/v1_2016/sync.py`  
> **Status:** Architecture design  
> **Purpose:** Define the structure and responsibilities of the modernized synchronization system before implementation.

This document describes the proposed architecture for the modernized version of the original bidirectional filesystem synchronization system.

The design intentionally preserves the core synchronization concept of the original implementation while separating responsibilities that were previously combined in a single procedural script.

---

# 1. Design Goals

The 2026 implementation should:

1. Preserve the core behavior of the original synchronization algorithm.
2. Separate filesystem operations from synchronization decisions.
3. Represent synchronization state with explicit data models.
4. Make reconciliation independently testable.
5. Make synchronization operations explicit before execution.
6. Remove hard-coded paths and configuration.
7. Support automated testing.
8. Provide a foundation for future features such as dry-run mode and alternative conflict policies.
9. Keep the implementation small enough to remain understandable and maintainable.

The goal is **not** to build a distributed storage platform.

The goal is to modernize the existing filesystem reconciliation system.

---

# 2. Architectural Principles

## 2.1 Separate decision-making from side effects

The synchronization engine should decide:

> What should happen?

before another component performs:

> How should the filesystem be changed?

For example:

```text
Local file newer
        ↓
Reconciler
        ↓
COPY_LOCAL_TO_REMOTE
        ↓
Filesystem adapter executes copy
```

The reconciliation layer should not directly call `os.remove()`, `shutil.copy2()`, or `os.mkdir()`.

---

## 2.2 Explicit state model

The original implementation represents entries using generic nested dictionaries:

```python
{
    "time": ...,
    "isDelet": False,
    "dir": ...
}
```

The modern implementation should use explicit domain models.

Conceptually:

```text
Entry
├── path
├── modified_time
├── deleted
└── type
```

Directories additionally contain child entries.

This makes the synchronization state easier to understand, validate, and test.

---

## 2.3 Deterministic reconciliation

Given the same two states and the same conflict policy, the reconciler should produce the same synchronization plan.

Conceptually:

```text
Local State
     +
Remote State
     +
Conflict Policy
     ↓
Deterministic Sync Plan
```

The reconciler should not depend on filesystem side effects while deciding what should happen.

---

# 3. High-Level Architecture

The system is divided into four main areas:

```text
                         ┌──────────────────┐
                         │       CLI        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Sync Engine     │
                         │  orchestration   │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
             ┌─────────────┐             ┌─────────────┐
             │   Scanner   │             │ State Store │
             └──────┬──────┘             └──────┬──────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
                         ┌──────────────────┐
                         │    Reconciler    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    Sync Plan     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Filesystem     │
                         │     Adapter      │
                         └────────┬─────────┘
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                      Local             Remote
                    filesystem        filesystem
```

---

# 4. Proposed Project Structure

The modernized repository should evolve toward:

```text
bidirectional-file-sync/
│
├── legacy/
│   └── v1_2016/
│       └── sync.py
│
├── src/
│   └── bidirectional_sync/
│       ├── __init__.py
│       ├── models.py
│       ├── scanner.py
│       ├── state_store.py
│       ├── reconciler.py
│       ├── filesystem.py
│       ├── sync_engine.py
│       └── cli.py
│
├── tests/
│   ├── test_models.py
│   ├── test_scanner.py
│   ├── test_reconciler.py
│   ├── test_sync_engine.py
│   └── test_deletions.py
│
├── docs/
│   ├── original-design.md
│   ├── behavior.md
│   └── architecture.md
│
├── examples/
│
├── README.md
├── PROJECT_STATUS.md
├── REQUIREMENTS.txt
└── .gitignore
```

The original implementation remains under `legacy/v1_2016/` and is not modified as part of the modernization.

---

# 5. Domain Model

## 5.1 Entry

The basic domain object represents an item in the synchronized filesystem.

Conceptually:

```text
Entry
├── path
├── modified_time
├── deleted
└── type
```

The type distinguishes at least:

```text
FILE
DIRECTORY
```

---

## 5.2 Directory

A directory contains child entries.

Conceptually:

```text
Directory
├── metadata
└── children
    ├── File
    ├── File
    └── Directory
        └── children
```

This preserves the recursive tree model used by the original implementation.

---

## 5.3 Deletion State

Deletion remains an explicit state.

Instead of immediately forgetting a missing entry:

```text
Filesystem entry disappears
        ↓
deleted = True
        ↓
Deletion participates in reconciliation
        ↓
Both sides converge
        ↓
State can eventually be removed
```

The original `isDelet` field becomes the clearer:

```text
deleted
```

in the modern model.

---

# 6. Scanner

### Responsibility

`scanner.py` is responsible only for observing a filesystem.

It converts:

```text
Filesystem
    ↓
Snapshot
```

The scanner should:

- recursively enumerate files and directories
- collect modification timestamps
- identify file/directory type
- produce the domain model

The scanner should not:

- copy files
- delete files
- resolve conflicts
- modify synchronization state
- decide which side wins

Conceptually:

```python
snapshot = scanner.scan(root)
```

---

# 7. State Store

The state store is responsible for persistence of synchronization state.

Conceptually:

```python
state = state_store.load(root)
state_store.save(root, state)
```

The state storage mechanism should be separated from the synchronization logic.

The initial 2026 implementation should use a simple machine-readable format such as JSON rather than continuing the original YAML implementation.

The important abstraction is:

```text
Sync Engine
     ↓
State Store
     ↓
Persistent State
```

The engine should not depend directly on a specific serialization format.

---

# 8. Reconciler

The reconciler is the core decision-making component.

It receives:

```text
Local State
Remote State
Conflict Policy
```

and produces:

```text
Sync Plan
```

Conceptually:

```text
             Local State
                  │
                  ├──────────────┐
                  │              │
                  ▼              ▼
             ┌──────────────────────┐
             │      Reconciler      │
             └──────────┬───────────┘
                        │
                        ▼
                   Sync Plan
```

The reconciler should contain the synchronization rules previously embedded in `sync()`.

Examples include:

- local-only file → copy to remote
- remote-only file → copy to local
- local newer → local wins
- remote newer → remote wins
- newer deletion → propagate deletion
- both deleted → remove state
- directories → recursively reconcile children

---

# 9. Sync Plan

Synchronization operations should be represented explicitly.

Possible operations include:

```text
NO_OP

COPY_LOCAL_TO_REMOTE
COPY_REMOTE_TO_LOCAL

DELETE_LOCAL
DELETE_REMOTE

CREATE_LOCAL_DIRECTORY
CREATE_REMOTE_DIRECTORY
```

A plan might conceptually look like:

```text
A.txt  → COPY_LOCAL_TO_REMOTE
B.txt  → DELETE_REMOTE
C.txt  → COPY_REMOTE_TO_LOCAL
D/     → CREATE_LOCAL_DIRECTORY
```

This provides an important separation:

```text
Reconcile
    ↓
Plan
    ↓
Execute
```

rather than:

```text
Reconcile
    ↓
Immediately modify filesystem
```

---

# 10. Filesystem Adapter

The filesystem adapter performs actual filesystem mutations.

Responsibilities include:

- copy files
- remove files
- create directories
- remove directories
- check filesystem state where required

Conceptually:

```python
filesystem.copy(source, destination)
filesystem.delete(path)
filesystem.mkdir(path)
```

The reconciler should not know whether the underlying implementation uses:

```python
os
shutil
pathlib
```

or another filesystem abstraction.

This makes the reconciliation engine easier to test.

---

# 11. Synchronization Engine

`sync_engine.py` provides the high-level orchestration.

A synchronization cycle should conceptually follow:

```text
1. Scan Local
2. Scan Remote
3. Load persistent state
4. Update state from filesystem observations
5. Reconcile Local and Remote
6. Generate Sync Plan
7. Execute Sync Plan
8. Update state
9. Persist state
```

Conceptually:

```text
             ┌─────────────┐
             │    Scan     │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │ Load State  │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │ Reconcile   │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │  Sync Plan  │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │   Execute   │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │ Save State  │
             └─────────────┘
```

The engine is therefore primarily an orchestration layer rather than the location of every synchronization rule.

---

# 12. Conflict Resolution

The original implementation uses modification timestamps:

```text
newer timestamp wins
```

The first modern implementation should preserve this behavior.

The conflict policy should nevertheless be isolated from the reconciler's general structure.

Conceptually:

```text
ConflictResolver
        │
        ├── local newer
        ├── remote newer
        └── equal / unresolved
```

This allows future policies to be introduced without rewriting the entire synchronization engine.

Potential future policies could include:

```text
Timestamp-based
Content-hash-based
Manual conflict resolution
```

These are future extension points, not requirements for the initial implementation.

---

# 13. Deletion Handling

Deletion is treated as state rather than simply absence.

The intended flow is:

```text
File exists
    ↓
File disappears
    ↓
Scanner detects absence
    ↓
State marks entry as deleted
    ↓
Reconciler compares deletion timestamp
    ↓
Deletion propagates if it is newer
    ↓
Both sides converge
    ↓
Tombstone can be removed
```

This preserves one of the most important design concepts from the original implementation.

---

# 14. Polling

The original implementation uses a continuous polling loop.

The modern implementation may retain this behavior for compatibility, but the polling interval should be configurable.

Instead of:

```python
time.sleep(1)
```

the application should conceptually support:

```text
sync watch --interval 1
```

or equivalent configuration.

The polling mechanism should remain outside the core reconciliation algorithm.

This means the same synchronization engine can potentially be used for:

```text
one-shot synchronization
continuous polling
future event-driven execution
```

without changing the reconciliation logic.

---

# 15. CLI

The command-line interface should provide a small entry point to the application.

The initial interface should remain intentionally simple.

Potential commands:

```text
sync
watch
```

Potential options:

```text
--local
--remote
--interval
--dry-run
```

Not all options need to be implemented in the first version.

The CLI should translate user configuration into the application layer rather than containing synchronization logic itself.

---

# 16. Testing Strategy

Testing is a major improvement over the original implementation.

The behavioral scenarios documented in `docs/behavior.md` should become automated tests.

Core scenarios include:

```text
test_new_local_file
test_new_remote_file

test_local_modification
test_remote_modification

test_local_deletion
test_remote_deletion

test_both_deleted

test_local_newer_wins
test_remote_newer_wins

test_new_directory
test_nested_directory_sync
```

The most important unit-test target is the reconciler.

For example:

```text
Given:
    Local A.txt = newer
    Remote A.txt = older

When:
    reconcile()

Then:
    plan contains COPY_LOCAL_TO_REMOTE
```

This allows synchronization behavior to be tested without actually copying files.

---

# 17. Test Layers

Testing should be divided into layers.

## Unit tests

Test:

- domain models
- state transitions
- conflict resolution
- reconciliation

These should require minimal or no real filesystem access.

## Filesystem tests

Test:

- scanning
- file copying
- deletion
- directory creation/removal

These operate on temporary directories.

## Integration tests

Test the complete flow:

```text
filesystem
    ↓
scanner
    ↓
state
    ↓
reconciler
    ↓
plan
    ↓
filesystem
```

Integration tests should verify that the complete system converges as expected.

---

# 18. Dry-Run Support

Because reconciliation produces an explicit `SyncPlan`, a dry-run mode becomes straightforward.

Conceptually:

```text
scan
  ↓
reconcile
  ↓
plan
  ↓
print plan
  ↓
do not execute
```

Example:

```text
$ sync --dry-run

COPY_LOCAL_TO_REMOTE    project/scene.hip
DELETE_REMOTE           project/cache.tmp
COPY_REMOTE_TO_LOCAL    textures/new.png
```

Dry-run is a natural consequence of the architecture rather than a special case inside the synchronization algorithm.

---

# 19. Error Handling

The modern implementation should make filesystem failures explicit.

Potential failures include:

- source file disappeared during synchronization
- destination cannot be written
- permission denied
- directory creation failed
- copy failed
- deletion failed

The initial implementation should provide clear errors and avoid silently treating failed filesystem operations as successful synchronization.

Full transactional rollback is outside the initial scope.

---

# 20. Configuration

The original implementation contains hard-coded paths:

```python
localDir = r'...'
cloudDir = r'...'
```

The modern implementation should move these into runtime configuration.

For example:

```text
--local <path>
--remote <path>
```

or a configuration file.

The synchronization engine itself should receive paths as input rather than owning global path variables.

---

# 21. Dependency Direction

The architecture should follow a clear dependency direction.

```text
CLI
 ↓
Sync Engine
 ↓
Reconciler
 ↓
Domain Models
```

Infrastructure components such as filesystem access and state persistence should be injected into or used by the application layer rather than embedded throughout the reconciliation logic.

The key principle is:

> **Synchronization decisions should remain independent of filesystem implementation details.**

---

# 22. What Is Intentionally Not Included

The first modern implementation should **not** attempt to become a full enterprise synchronization product.

The following are explicitly outside the initial scope:

- distributed networking protocol
- multi-user synchronization
- authentication
- encryption
- cloud API integration
- database-backed distributed state
- file-content merging
- version history
- conflict UI
- filesystem event watchers
- multi-machine coordination
- transactional rollback

These may be future directions, but adding them now would obscure the core modernization exercise.

---

# 23. 2016 → 2026 Mapping

| 2016 implementation | 2026 architecture |
|---|---|
| `makeList()` | `Scanner` |
| `file_to_dict()` | `StateStore.load()` |
| `dict_to_file()` | `StateStore.save()` |
| nested dictionaries | Domain models |
| `updateList()` | State update / observation logic |
| `sync()` | `Reconciler` |
| direct `os.remove()` | Filesystem adapter |
| direct `copy2()` | Filesystem adapter |
| hard-coded paths | CLI/configuration |
| `while True` loop | Watch/runner layer |
| implicit operations | `SyncPlan` |
| timestamp comparison inside `sync()` | Conflict policy |
| manual verification | Automated tests |

The goal is not to reproduce the old function names.

The goal is to preserve the important behavior while giving each responsibility an explicit location.

---

# 24. Target Data Flow

The intended 2026 data flow is:

```text
             LOCAL FILESYSTEM
                    │
                    ▼
                Scanner
                    │
                    ▼
              Local Snapshot
                    │
                    │
                    ├───────────────┐
                    │               │
                    ▼               ▼
             State Store       Reconciler
                    ▲               ▲
                    │               │
                    │               │
              Remote State          │
                    ▲               │
                    │               │
                Scanner             │
                    ▲               │
                    │               │
            REMOTE FILESYSTEM ──────┘

                         ↓

                     Sync Plan
                         ↓
                 Filesystem Adapter
                    ↙          ↘
                 Local       Remote
```

The important boundary is:

```text
Observe → Decide → Execute
```

rather than mixing all three operations together.

---

# 25. Migration Strategy

The modernization should happen incrementally.

### Phase 1 — Preserve

Keep the original implementation unchanged:

```text
legacy/v1_2016/sync.py
```

### Phase 2 — Document

Document:

- original architecture
- observed behavior
- known limitations

### Phase 3 — Model

Implement explicit domain models.

### Phase 4 — Extract reconciliation

Move synchronization decisions into a dedicated reconciler.

### Phase 5 — Add filesystem abstraction

Separate filesystem side effects from reconciliation.

### Phase 6 — Add persistence

Introduce the new state storage implementation.

### Phase 7 — Add tests

Convert behavioral scenarios into automated tests.

### Phase 8 — Add CLI / watch mode

Provide a usable application interface.

### Phase 9 — Compare behavior

Use the documented 2016 behavior as the baseline and identify intentional differences.

---

# 26. Definition of Success

The modernization is successful when:

1. The original 2016 implementation remains preserved.
2. The important synchronization behavior is explicitly documented.
3. The new implementation has clear separation of responsibilities.
4. Reconciliation can be tested independently of filesystem operations.
5. Synchronization behavior is covered by automated tests.
6. Paths and runtime configuration are no longer hard-coded.
7. The system can produce an explicit synchronization plan.
8. The new implementation can perform the same core bidirectional synchronization workflow.
9. Any intentional behavioral differences from the 2016 version are documented.

The objective is therefore not simply:

> "Rewrite an old Python script."

It is:

> **Preserve a historical synchronization algorithm, extract its behavior, and redesign it as a testable modern software system.**