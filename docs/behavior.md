# Synchronization Behavior

> **Historical implementation:** `legacy/v1_2016/sync.py`  
> **Documentation date:** 2026  
> **Purpose:** Describe the observed synchronization behavior of the original implementation before modernization.

This document describes how the original synchronization algorithm behaves based on the implementation in `legacy/v1_2016/sync.py`.

It is a behavioral description of the existing implementation, not a specification of a redesigned system.

---

## 1. Overview

The system maintains two filesystem locations:

- **Local** — the primary working directory
- **Cloud / Server** — the backup or shared storage directory

The system periodically:

1. Scans both directories.
2. Loads the previous filesystem state from `filelist.yaml`.
3. Detects additions and deletions.
4. Stores timestamps and deletion state.
5. Compares the state of the two locations.
6. Reconciles differences.
7. Writes the resulting state back to both `filelist.yaml` files.
8. Repeats approximately once per second.

The synchronization model is therefore based on:

```text
Filesystem
    ↓
Snapshot
    ↓
Persistent state
    ↓
State comparison
    ↓
Reconciliation
    ↓
Filesystem changes
```

---

## 2. Persistent State

Each directory maintains a `filelist.yaml` file.

The YAML structure represents the filesystem as nested dictionaries.

A file is represented approximately as:

```yaml
example.txt:
  time: 2026-01-01 12:00:00
  isDelet: false
  dir: null
```

A directory is represented as:

```yaml
project:
  time: 2026-01-01 12:00:00
  isDelet: false
  dir:
    scene.hip:
      time: 2026-01-01 12:05:00
      isDelet: false
      dir: null
```

The state associated with each entry contains:

| Field | Meaning |
|---|---|
| `time` | Timestamp used when comparing states |
| `isDelet` | Whether the entry is considered deleted |
| `dir` | Nested state for a directory; `None` for a file |

The `filelist.yaml` file itself is excluded from filesystem scanning.

---

## 3. Filesystem Scanning

`makeList()` recursively scans a directory.

For each entry:

- Files receive their filesystem modification time.
- Directories receive their directory modification time.
- Directories are recursively scanned.
- `filelist.yaml` is ignored.

The result is an in-memory tree representing the current filesystem state.

---

## 4. State Update

Before synchronization, `writeList()` compares the current filesystem against the previous persisted state.

The comparison is performed by `updateList()`.

### 4.1 Existing entries

If an entry exists both:

```text
Current filesystem
        +
Previous state
```

the current filesystem information is used to update the stored state.

For directories, this comparison is performed recursively.

---

### 4.2 New entries

If an entry exists in the current filesystem but not in the previous state:

```text
Current:  file.txt
Previous: missing
```

the entry is added to the persisted state.

Its timestamp comes from the filesystem.

---

### 4.3 Missing entries

If an entry existed in the previous state but no longer exists in the current filesystem:

```text
Current:  missing
Previous: file.txt
```

the entry is **not immediately removed from the state**.

Instead:

```text
isDelet = True
time = datetime.now()
```

This creates a persistent deletion record.

This is effectively a tombstone-like mechanism.

The deletion timestamp allows a deletion to participate in the same timestamp comparison mechanism as file modifications.

---

## 5. Synchronization Rules

The `sync()` function compares the state of the Local and Cloud trees.

The general rule is:

> **When an entry exists on both sides, the state with the newer timestamp wins.**

This applies to both modifications and deletion states.

---

## 6. New Local File

### Initial state

```text
Local:
    new_file.txt

Cloud:
    missing
```

If the local state indicates that the file is not deleted:

```text
Local → Cloud
```

The file is copied to the Cloud location using `shutil.copy2()`.

Expected result:

```text
Local:
    new_file.txt

Cloud:
    new_file.txt
```

---

## 7. New Cloud File

The reverse operation also occurs.

```text
Local:
    missing

Cloud:
    new_file.txt
```

If the Cloud entry is not marked as deleted:

```text
Cloud → Local
```

The file is copied to the Local location.

---

## 8. Local Modification

If the same file exists on both sides and:

```text
Local timestamp > Cloud timestamp
```

the Local version is considered newer.

The Cloud file is removed and replaced with the Local file:

```text
Local
  ↓
Cloud
```

The synchronization therefore uses a **last-modified-time-wins** strategy.

---

## 9. Cloud Modification

If:

```text
Cloud timestamp > Local timestamp
```

the Cloud version is considered newer.

The Local file is removed and replaced with the Cloud file:

```text
Cloud
  ↓
Local
```

---

## 10. Local Deletion

A physical deletion is detected during the state update phase.

The missing local file becomes:

```text
isDelet = True
```

and receives a new timestamp:

```text
time = datetime.now()
```

If this deletion timestamp is newer than the Cloud state, the deletion propagates to the Cloud.

For a file:

```text
Local deletion
      ↓
Cloud file removed
```

For a directory:

```text
Local deletion
      ↓
Cloud directory removed recursively
```

---

## 11. Cloud Deletion

The same mechanism works in the opposite direction.

If the Cloud deletion state has a newer timestamp:

```text
Cloud deletion
      ↓
Local file/directory removed
```

This makes deletion a first-class synchronization event rather than simply treating a missing file as an absence of information.

---

## 12. Both Sides Modified

If the same file exists on both sides but their timestamps differ:

```text
Local timestamp > Cloud timestamp
```

Local wins.

If:

```text
Cloud timestamp > Local timestamp
```

Cloud wins.

There is no interactive conflict resolution.

There is also no merge of file contents.

The algorithm performs a replacement operation.

---

## 13. Both Sides Deleted

If both states contain the same entry and both are marked:

```text
isDelet = True
```

the entry is removed from the synchronization state.

This allows the deletion tombstone to eventually disappear once both sides agree that the object no longer exists.

---

## 14. Directories

Directories are handled recursively.

When both sides contain a directory and neither side is marked deleted:

```text
Local directory
        ↕
Cloud directory
```

`sync()` recursively compares their child entries.

For example:

```text
project/
├── scene.hip
├── textures/
│   ├── diffuse.png
│   └── normal.png
└── cache/
```

The synchronization algorithm recursively enters:

```text
project/
    ↓
textures/
    ↓
individual files
```

This means synchronization operates on the filesystem tree rather than only on top-level files.

---

## 15. Directory Deletion

If a directory is marked deleted and its deletion timestamp is newer than the corresponding directory on the other side, the other directory is recursively removed.

Conceptually:

```text
Local:
    project/  [deleted, newer]

Cloud:
    project/  [existing, older]

Result:

Cloud/project/
    ↓
removed recursively
```

The implementation uses `shutil.rmtree()` for directory removal.

---

## 16. New Directories

When a directory exists on one side but not the other, the synchronization code creates the missing directory with `os.mkdir()`.

Its contents are handled through the recursive state model and subsequent synchronization passes.

This is different from file synchronization, where `copy2()` immediately copies the file itself.

---

## 17. Polling Model

The original implementation does not use filesystem events.

The main loop continuously polls both directories:

```text
while True:
    scan Local
    scan Cloud

    update Local state
    update Cloud state

    synchronize

    persist state

    sleep
```

The loop sleeps for approximately one second between iterations.

Therefore synchronization is **polling-based**, rather than event-driven.

---

## 18. Conflict Resolution Model

The conflict resolution rule can be summarized as:

```text
                 Compare timestamps
                        │
             ┌──────────┴──────────┐
             │                     │
        Local newer           Cloud newer
             │                     │
             ▼                     ▼
        Local wins             Cloud wins
```

The timestamp comparison applies to:

- file modifications
- directory state
- deletion events

A deletion can therefore beat a modification if the deletion timestamp is newer.

---

## 19. State Machine

At a conceptual level, an individual entry can move through states such as:

```text
             ┌───────────────┐
             │    Existing   │
             └───────┬───────┘
                     │
              filesystem delete
                     │
                     ▼
             ┌───────────────┐
             │    Deleted    │
             │  tombstone    │
             └───────┬───────┘
                     │
              both sides agree
                     │
                     ▼
                 Removed
```

An existing entry can also be updated when its filesystem timestamp changes.

The synchronization process then compares the resulting states between Local and Cloud.

---

## 20. Important Implementation Characteristics

The original system has several notable design characteristics.

### Persistent state

The synchronization state survives between executions through YAML files.

### Recursive tree representation

Filesystem hierarchy is represented as nested dictionaries.

### Explicit deletion state

Deleted objects remain represented in state temporarily instead of disappearing immediately.

### Bidirectional reconciliation

Changes can propagate in either direction.

### Timestamp-based conflict resolution

The newer state wins when both sides disagree.

### Continuous polling

The system repeatedly scans both locations rather than responding to filesystem events.

---

# 21. Known Limitations

The following are characteristics or limitations of the original implementation and should not be interpreted as requirements for the modernized version.

## Timestamp-based conflict detection

The system relies heavily on filesystem modification timestamps.

This can be affected by:

- filesystem timestamp resolution
- clock differences between machines or storage systems
- copied files retaining timestamps
- changes that occur within the same timestamp resolution

The implementation does not provide a stronger versioning or content-hash mechanism.

---

## No content-based merge

When both sides contain different versions of a file, the system does not attempt to merge them.

The newer timestamp wins.

Therefore a newer version can overwrite an older version without preserving both versions.

---

## No transactional synchronization

The synchronization process performs filesystem operations such as:

```text
remove
copy
mkdir
rmtree
```

without an explicit transaction or rollback mechanism.

If the process fails during synchronization, the two locations may temporarily become inconsistent.

---

## No filesystem locking

The original implementation does not implement a locking protocol.

It assumes that the synchronization process can safely inspect and modify both locations.

---

## No explicit network protocol

Although one location is described as a Cloud/server location, the implementation itself operates through filesystem paths.

It does not implement:

- a network synchronization protocol
- a server process
- authentication
- network conflict negotiation
- distributed locking

The system should therefore be understood as a **filesystem reconciliation tool**, rather than a general distributed synchronization system.

---

## Polling overhead

The main loop repeatedly scans both directory trees approximately every second.

For large directory trees this can become expensive because the system repeatedly performs filesystem enumeration and metadata queries.

---

## Hard-coded configuration

The original implementation stores the Local and Cloud paths directly in the Python source.

Configuration is therefore not separated from the synchronization logic.

---

## Limited error handling

The original implementation does not provide comprehensive handling for conditions such as:

- missing directories
- permission errors
- files disappearing during a scan
- failed copy operations
- failed deletion operations
- partially completed synchronization

---

# 22. Summary of Original Behavior

The original implementation can be summarized as:

```text
Filesystem changes
        ↓
Recursive filesystem scan
        ↓
Compare against persistent YAML state
        ↓
Detect additions / deletions
        ↓
Record deletion state
        ↓
Compare Local and Cloud
        ↓
Newer timestamp wins
        ↓
Copy / delete / create directories
        ↓
Persist updated state
        ↓
Repeat
```

The core design is therefore a:

> **Polling-based, timestamp-driven, bidirectional filesystem state reconciliation system with persistent deletion state.**

This description reflects the behavior of the original implementation and is intended to serve as the behavioral baseline for the subsequent modernization and refactoring work.