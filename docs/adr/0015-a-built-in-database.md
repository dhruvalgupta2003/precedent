---
title: "ADR0015: A built-in database, so trying Precedent needs no Docker"
status: accepted
date: 2026-11-13
---

## Context
Every path into Precedent started with "install Docker and run FalkorDB". For people arriving from the launch post
that is the biggest drop-off: the 2-minute demo was really "install Docker Desktop first". FalkorDBLite runs FalkorDB
inside the Python process, from one file, with prebuilt packages for macOS and for Linux with glibc 2.38+ (Ubuntu
24.04+). It has no Windows package, and on older Linux it would compile Redis from source.

## Decision
1. Precedent picks its database by one rule (`adapters.falkor.connect`): the server at `FALKORDB_URL` when it is set;
   otherwise the built-in database, in `$PRECEDENT_DB` or `~/.local/share/precedent/precedent.db`, when FalkorDBLite is
   installed; otherwise a server on `localhost:6380`, as before.
2. FalkorDBLite is the optional extra `precedent[embedded]`, never a hard dependency, so the plain install can't break
   on Windows or older Linux. The docs' install line includes the extra. Windows skips it and uses a server.
3. The built-in database bundles an older FalkorDB (module 4.22) than the server we test on (6.0.4). CI runs the graph
   tests on both, and the eval suites give the same scores on both.

## Alternatives
- **A hard dependency** — rejected: a failed compile on Windows or older Linux would break installing Precedent at all.
- **Auto-detect a running server first** — rejected: data would silently live in two places depending on whether
  Docker happened to be running. One explicit rule is easier to reason about.

## Consequences
`uv tool install` is the whole setup on macOS and current Linux. Teams and CI that share decisions still set
`FALKORDB_URL` to a server. Running the built-in database surfaced one query that relied on how FalkorDB 6 reads
`NOT … IN`; it now uses parentheses and reads the same on both versions.

The built-in server starts and stops with each process, and the Claude Code hook is a new process on every edit. At
first each hook call took ~5.5 s: after `SHUTDOWN` closed the socket, the Redis client retried with back-off. The
built-in client now never retries (a dropped local socket means the server stopped), and the CLI loads the AI library
only when AI is used. A hook call now takes about 1 s, of which the database is ~0.2 s.
