# Bidirectional File Sync

A Python-based bidirectional file synchronization tool originally developed around 2016 for backing up production project files to an internal server.

The original implementation was written to solve a practical production workflow problem: maintaining a local working directory and an internal server copy while preserving changes and deletions on both sides.

## Origin

This repository contains the original implementation developed approximately 10 years ago, followed by a later modernization and refactoring of the system.

The original implementation is intentionally preserved as part of the project history.

## Core Idea

The original tool maintains a filesystem representation for both locations and compares their state using stored metadata.

The synchronization process can:

- Recursively scan directory structures
- Track file modification timestamps
- Track deleted files and directories
- Compare local and server states
- Propagate additions and deletions
- Synchronize files in both directions
- Resolve changes using modification timestamps

## Original Architecture

The original implementation represents a directory tree as nested Python dictionaries.

Each filesystem entry stores information including:

- modification time
- deletion state
- child directory data

The synchronization process consists broadly of:

```text
Filesystem
    ↓
Directory Snapshot
    ↓
State Representation
    ↓
State Comparison
    ↓
Reconciliation
    ↓
Filesystem Operations
```

## Project History

### Original implementation — ~2016

The first version was created as an internal production tool for project backup and synchronization.

It was designed around the constraints and workflow of the production environment in which it was used.

The original code is preserved in:

```text
legacy/v1_2016/
```

### Modernized implementation — 2026

The project is being revisited with the goal of:

- improving code structure
- improving reliability
- adding tests
- improving error handling
- making the tool reproducible outside its original environment
- documenting the synchronization model

The modern implementation will remain conceptually connected to the original system while being developed as a separate implementation.

## Limitations of the Original Version

The original implementation was designed for a specific internal production environment and should not be considered production-ready software in its current form.

Known limitations include:

- Python 2 / older Python-era conventions
- limited error handling
- no automated test suite
- filesystem operations are performed directly
- timestamp-based conflict resolution
- no dry-run mode
- no robust recovery mechanism
- hard-coded paths in the original script

These limitations are intentionally retained in the historical version.

## Why Preserve the Original?

The purpose of keeping the original implementation is not to present it as modern Python code.

It documents the original system design and provides a baseline for comparing the original implementation with the later refactored version.

## Status

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the current development status.

## Requirements

See [REQUIREMENTS.txt](REQUIREMENTS.txt).