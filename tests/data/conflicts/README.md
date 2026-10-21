# Synthetic Conflict Engine fixtures

These are authored synthetic cases, with no customer data or production accuracy claim.
Import source-a.csv as FILE and source-b.xml as ONE_C; normalize with synthetic-material,
then match with synthetic-material. The XML uses the supported synthetic 1C export shape.

Expected automatic result: one mass VALUE_MISMATCH for DIFF (12.5 kg vs 12.4 kg),
one mass MISSING for MISS (empty CSV value vs 12 kg). EQ is equivalent after normalization.
INVALID and UNKNOWN are diagnostics, not false mismatches or absence. NEG-A/NEG-B
must not establish identity. Repeated DUP keys remain POSSIBLE_MATCH. Only after an
explicit authorized matching review confirms both DUP pairs can the engine expose
DUPLICATE: multiple records from one source claim the same confirmed identity.

This is a test oracle for these cases; it is not Forest Codex or a pilot dataset.
