# Original Design — 2016 Implementation

## Overview

The original implementation is a Python-based bidirectional filesystem synchronization tool developed approximately in 2016.

It was created to back up and synchronize production project files between a local working directory and an internal server.

The implementation is intentionally preserved in its original form in:

```text
legacy/v1_2016/sync.py
```

This document describes the architecture and behaviour of that implementation based on the original source code.

It does not describe the later modernized implementation.

---

## Design Goals

The original system was designed to:

- Maintain a copy of project files on an internal server
- Synchronize changes in both directions
- Detect newly created files and directories
- Detect modified files
- Detect deleted files and directories
- Propagate changes between the two locations
- Preserve information about deleted items between synchronization cycles
- Operate recursively across nested directory structures

The system uses filesystem modification timestamps as its primary mechanism for determining which side contains the most recent state.

---

# Architecture

At a high level, the system follows this process:

```text
Local Filesystem
       │
       ▼
Filesystem Scan
       │
       ▼
Directory State
       │
       ▼
Persistent YAML State
       │
       │
       ├──────────────────────┐
       │                      │
       ▼                      ▼
Local State             Server State
       │                      │
       └──────────┬───────────┘
                  ▼
          State Reconciliation
                  │
                  ▼
          Filesystem Operations
                  │
                  ▼
          Updated YAML State
```

The main architectural stages are:

1. Filesystem scanning
2. State representation
3. Persistent state storage
4. State reconciliation
5. Filesystem mutation
6. Repeated polling

---

# 1. Filesystem Scanning

## `makeList()`

```python
makeList(path)
```

`makeList()` recursively scans a directory and converts its filesystem structure into a nested Python dictionary.

For each filesystem entry, the implementation records:

- modification time
- deletion state
- child directory state

A file is represented approximately as:

```text
filename
├── time
├── isDelet
└── dir = None
```

A directory is represented as:

```text
directory
├── time
├── isDelet
└── dir
    └── child entries
```

The resulting structure is a recursive tree representation of the filesystem.

### Example

A filesystem such as:

```text
Project/
├── scene.hip
├── asset.obj
└── textures/
    └── bark.jpg
```

is represented conceptually as:

```text
{
    "scene.hip": {
        "time": ...,
        "isDelet": False,
        "dir": None
    },

    "asset.obj": {
        "time": ...,
        "isDelet": False,
        "dir": None
    },

    "textures": {
        "time": ...,
        "isDelet": False,
        "dir": {
            "bark.jpg": {
                "time": ...,
                "isDelet": False,
                "dir": None
            }
        }
    }
}
```

This establishes the core data model used throughout the system.

---

# 2. Persistent State

The filesystem tree is persisted to a YAML file named:

```text
filelist.yaml
```

The original implementation provides two functions for this:

```python
file_to_dict()
dict_to_file()
```

These functions provide a simple persistence layer between synchronization cycles.

The YAML file therefore acts as a stored representation of the filesystem state.

Conceptually:

```text
Filesystem
     │
     ▼
Python dictionary
     │
     ▼
filelist.yaml
```

and later:

```text
filelist.yaml
     │
     ▼
Python dictionary
```

The state is maintained independently for the local and server locations.

---

# 3. State Model

Each filesystem entry contains three pieces of information.

## Modification time

```python
'time'
```

The modification timestamp is used when comparing corresponding entries on the two sides.

## Deletion state

```python
'isDelet'
```

This records whether an entry has been detected as deleted.

A deleted entry is not immediately removed from the stored state.

Instead, the deletion is represented explicitly as a state.

## Child directory state

```python
'dir'
```

For files:

```text
dir = None
```

For directories:

```text
dir = nested dictionary
```

This produces a recursive tree structure.

---

# 4. Detecting State Changes

## `updateList()`

```python
updateList(currentDir, dirList)
```

`updateList()` compares the current filesystem scan against the previously stored state.

Conceptually:

```text
Current Filesystem
        │
        │ compare
        ▼
Previous State
        │
        ▼
Updated State
```

It handles three important cases.

---

## 4.1 Existing entries

If an entry exists in both the current filesystem and the previous state, its state is updated.

For directories, the comparison continues recursively.

---

## 4.2 New entries

If an entry exists in the current filesystem but not in the previous state, it is added to the state.

Conceptually:

```text
Current - Previous
        ↓
     New entry
```

---

## 4.3 Deleted entries

If an entry exists in the previous state but no longer exists in the current filesystem, it is marked as deleted.

The implementation does this by setting:

```python
isDelet = True
```

and updating its timestamp:

```python
time = datetime.now()
```

The entry remains in the state representation.

This allows a deletion to be propagated to the other side during synchronization.

---

# 5. Deletion as State

The deletion mechanism is an important part of the original design.

Instead of immediately removing a missing file from the stored state:

```text
File disappears
       │
       ▼
isDelet = True
       │
       ▼
Deletion remains represented
       │
       ▼
Sync propagates deletion
```

This means that deletion is treated as a state transition rather than simply the absence of an entry.

The stored state therefore distinguishes between:

```text
Entry never existed
```

and:

```text
Entry existed and was deleted
```

---

# 6. Bidirectional Synchronization

## `sync()`

```python
sync(localList, cloudList, subDir='')
```

`sync()` is the core synchronization function.

It compares the stored state of the local and server locations and applies filesystem operations according to the differences.

The synchronization is bidirectional:

```text
Local  ↔  Server
```

Neither side is treated as permanently authoritative.

---

# 7. Conflict Resolution

When the same entry exists on both sides, the implementation compares their stored timestamps.

The basic rule is:

```text
Local timestamp > Server timestamp
        ↓
Local state wins
```

and:

```text
Server timestamp > Local timestamp
        ↓
Server state wins
```

This applies to modifications and deletion states.

The synchronization strategy can therefore be described as:

> **Timestamp-based last-state-wins reconciliation**

---

# 8. File Synchronization

For files existing on both sides, the timestamps determine which copy is propagated.

### Local is newer

```text
Local file
    │
    ▼
Copy
    │
    ▼
Server file
```

### Server is newer

```text
Server file
    │
    ▼
Copy
    │
    ▼
Local file
```

The implementation uses:

```python
copy2()
```

for file copying.

---

# 9. Deletion Synchronization

Deletion is handled using the same timestamp comparison mechanism.

For example:

```text
Local:
    file exists
    timestamp = 10:00

Server:
    file marked deleted
    timestamp = 11:00
```

The server state is newer.

Therefore:

```text
Server deletion
       ↓
Delete local file
```

Conversely, if the local deletion state is newer, the server copy is deleted.

This allows deletions to propagate in either direction.

---

# 10. Directory Synchronization

Directories are handled recursively.

When corresponding entries on both sides represent directories, `sync()` calls itself on their child dictionaries.

Conceptually:

```text
Root
 │
 ├── Folder A
 │      │
 │      └── sync()
 │
 └── Folder B
        │
        └── sync()
```

This allows the same synchronization logic to operate at arbitrary directory depths.

---

# 11. Creating Missing Entries

If an entry exists on one side but not the other, the implementation creates the missing entry.

For files:

```text
copy2()
```

is used.

For directories:

```text
os.mkdir()
```

is used before recursively handling their contents in subsequent processing.

The system therefore handles both:

```text
Local → Server
```

and:

```text
Server → Local
```

creation.

---

# 12. Removing Fully Deleted Entries

If an entry is marked as deleted on both sides:

```text
Local:  isDelet = True
Server: isDelet = True
```

the entry is removed from both state dictionaries.

This represents the final removal of the deletion record after both sides have reached the same state.

Conceptually:

```text
Deleted on one side
        ↓
Deletion propagated
        ↓
Deleted on both sides
        ↓
Remove state entry
```

---

# 13. Synchronization Loop

The original program runs continuously:

```python
while True:
```

Each iteration performs the following operations:

```text
1. Scan local filesystem
2. Update local state
3. Scan server filesystem
4. Update server state
5. Load both states
6. Reconcile local and server
7. Persist updated states
8. Wait
9. Repeat
```

The loop uses:

```python
time.sleep(1)
```

so synchronization is polling-based.

Conceptually:

```text
             ┌───────────────┐
             │   Wait 1 sec  │
             └───────┬───────┘
                     │
                     ▼
              Scan filesystems
                     │
                     ▼
              Update state
                     │
                     ▼
               Reconcile
                     │
                     ▼
            Apply filesystem changes
                     │
                     ▼
             Persist state
                     │
                     └───────────────►
```

---

# 14. Function Responsibilities

| Function | Responsibility |
|---|---|
| `makeList()` | Recursively scan filesystem and build state tree |
| `file_to_dict()` | Load persisted YAML state |
| `dict_to_file()` | Persist state to YAML |
| `dict_to_txt()` | Debug/export dictionary representation |
| `dict_to_set()` | Convert dictionary keys to sets for comparison |
| `updateList()` | Compare current filesystem against previous state |
| `showList()` | Print state tree for inspection |
| `writeList()` | Scan filesystem and update persisted state |
| `sync()` | Reconcile local and server states |
| `__main__` loop | Continuously poll and synchronize |

---

# 15. Data Flow

The complete data flow can be summarized as:

```text
                 LOCAL
                   │
                   ▼
             makeList()
                   │
                   ▼
             Current State
                   │
                   ▼
             updateList()
                   │
                   ▼
             filelist.yaml
                   │
                   │
                   │
                   │
                   ▼
              sync() ◄───────────────┐
                   │                  │
                   │                  │
                   ▼                  │
            Filesystem Actions        │
                   │                  │
                   ▼                  │
                 LOCAL                │
                                      │
                 SERVER               │
                   │                  │
                   ▼                  │
             makeList()               │
                   │                  │
                   ▼                  │
             updateList()             │
                   │                  │
                   ▼                  │
             filelist.yaml ───────────┘
```

---

# 16. Architectural Characteristics

The original implementation can be characterized as a:

**Polling-based, timestamp-driven, bidirectional filesystem state reconciliation system.**

Its main design characteristics are:

- Recursive filesystem representation
- Persistent state stored in YAML
- Explicit deletion state
- Bidirectional synchronization
- Timestamp-based conflict resolution
- Recursive reconciliation
- Continuous polling

---

# 17. What the Original Design Does Not Provide

The original implementation was created for an internal production workflow and does not attempt to provide the features expected from a general-purpose synchronization product.

The original design does not include:

- File content hashing
- Partial file synchronization
- Network protocol handling
- Concurrent synchronization control
- File locking
- Transactional operations
- Automatic rollback
- Crash recovery
- Explicit conflict history
- Dry-run mode
- Automated tests
- Structured logging
- Configuration management
- Retry handling
- Integrity verification

These are limitations of the original implementation rather than missing documentation.

---

# 18. Design Summary

The original implementation is built around a simple but coherent model:

```text
Filesystem
    ↓
Snapshot
    ↓
Persistent State
    ↓
State Comparison
    ↓
Reconciliation
    ↓
Filesystem Mutation
    ↓
Updated State
```

The central idea is that synchronization is performed by comparing **representations of filesystem state**, rather than simply copying files from one location to another.

This allows the system to reason about:

- additions
- modifications
- deletions
- directory structures
- changes occurring on either side

The implementation is therefore more accurately described as a **filesystem state reconciliation tool** than a simple backup script.

---

## Historical Note

This document was written in 2026 to document the architecture of the original implementation.

It should not be interpreted as documentation that existed when the original tool was developed.

The source of truth for the historical implementation remains:

```text
legacy/v1_2016/sync.py
```