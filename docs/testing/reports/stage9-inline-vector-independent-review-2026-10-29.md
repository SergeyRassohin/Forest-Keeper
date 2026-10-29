# Stage 9: independent physical-vector migration review

The reviewed migration has no blocking security or product-intent finding. The independent populated migration test passed: **1 passed, 0 skipped, 7.93 seconds**, exit 0, with one `StarletteDeprecationWarning`. This approves the reviewed physical rewrite and its regression coverage; Stage 9 acceptance and merge remain blocked by the outstanding gates.

The test ran in a fresh owned schema with the test provider and made no real model calls. It created three human API fixture Decisions and explicitly synthetic storage-edge vectors. Upgrade and downgrade preserved every logical table digest, binary vector payload, index definition, constraint and trigger. Signed zero, subnormal and maximum finite float32 values remained byte-identical. UPDATE and DELETE still failed through the immutable guard. An injected exception after DDL rolled back the revision, storage policy and rows; repeated upgrade to head succeeded.

The migration combines TYPE and STORAGE in one ALTER, uses the float4-array round trip to force rewriting, and runs ANALYZE afterward. It does not update business rows, disable triggers, activate a version, change a model, relax authorization or alter recommendation thresholds. The health revision changes to `0009_inline_vectors`.

The tested base was `ed240cd62cc7cbc3d5953c55effbb948fd7d8835`, with uncommitted candidate files. Their exact hashes, the private test-log hash and execution details are in the [companion JSON](stage9-inline-vector-independent-review-2026-10-29.json). Candidate hashes remained unchanged after execution. This is not exact-final-HEAD CI evidence.

The reviewer also inspected the parent's separate TEMP-table diagnostics, without executing them independently. Those diagnostics check the actual pinned model/version and 10,000 distinct vectors, preserve original rows, compare 30,000 per-row distances with zero differences, and exercise the actual DDL round trip. Their 30-second diagnostic statement bound does not alter the API's 1.5-second budget. The earlier failed diagnostic attempts remain historical evidence.

Deployment needs coordinated maintenance: ALTER TYPE takes ACCESS EXCLUSIVE and rewrites the heap and indexes. Budget transient old/new heap, index, TOAST and WAL space, including replication/archive requirements. The observed TEMP relation totals increased from 72,802,304 to 97,607,680 bytes for 10,000 rows. These tests do not establish endpoint NFR performance or semantic quality.

Required next gates include final committed-source checks and CI, fresh actual-model regression and loaded endpoint measurements, human-approved Gold Reference and quality acceptance, and production hardware/profile and signed-delivery dependencies. No merge or stage acceptance was performed. Reports contain safe metadata only; raw logs, credentials, prompts and vector payloads remain private.
