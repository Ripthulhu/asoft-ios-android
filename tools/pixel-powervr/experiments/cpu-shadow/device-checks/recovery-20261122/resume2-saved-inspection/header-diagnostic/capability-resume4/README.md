# Bounded synthetic count-semantics proof

This separately named revision preserves both failed native capability attempts. It records bounded `qemu-img dd --help` output, but no longer requires every implemented option to appear in help.

The only read is a newly written 2,048-byte synthetic input consisting of four distinct 512-byte blocks. The exact qualified native tool must make `bs=512 count=3 skip=2` produce exactly the third block, with a 512-byte output and unchanged input. This tests the upstream-style input-limit-before-skip behavior; it does not assume GNU dd count semantics. Every source, tooling, session, resource and own-child cleanup gate remains unchanged.

A failed proof leaves its own evidence intact and authorizes no image read. A genuine reviewed pass can bind the pending eight-header reader, whose fixed per-header count is `skip + 1` and whose output must still be exactly 512 bytes. The original inspector and filesystem acceptance predicates remain unchanged.

`source-status.json` identifies the exact source, command and independent release review. Actual result metadata must be captured and independently checked before `finalize_header_diagnostic.py` can produce a runnable header reader.
