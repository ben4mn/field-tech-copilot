# Knowledge and safety policy

## Procedure cards

Knowledge enters the system as reviewable procedure cards. A card should cover one task or decision and include:

- Stable ID and descriptive title
- Topic tags and applicability (OS, vendor, product, version)
- Source title, URL or local reference, publication/version, and verification date
- Risk level, required privileges, prerequisites, side effects, and rollback/backup steps
- The procedure itself, expected outcomes, and branches

Do not copy material into a distributable bundle unless its license permits redistribution. A local technician may index lawfully obtained documentation without committing it to this repository; legal and contractual restrictions still apply.

## Source trust tiers

1. Operating-system or manufacturer primary documentation
2. Hardware/service documentation from the relevant vendor
3. Maintainer documentation for the exact software involved
4. Internally verified shop procedure with named reviewer and verification date

Forum posts, generated text, and unattributed command collections are leads, not verified procedure cards.

## Risk rules

Classify as `destructive` whenever an action can erase data, overwrite a disk or partition, reset/reinstall an OS, alter firmware, remove encryption access, invalidate credentials, or make a machine unbootable. Classify elevated shell changes, driver/registry changes, malware removal, and network-wide configuration as at least `caution`.

A destructive card and any derived recommendation must state:

- What can be lost or interrupted
- Preconditions and identity checks
- Backup or recovery expectation
- A rollback path, or an explicit statement that none exists
- The exact point at which the technician must confirm

## Runtime enforcement

- The model receives only the retrieved cards, each labeled with a stable ID.
- Returned citations are intersected with the retrieved IDs.
- Structured output validation rejects destructive steps without confirmation and rollback language.
- Duplicate-test fingerprints are compared against completed tests.
- Unstable-storage and encryption guards evaluate complaint, observations, and completed action results rather than only the latest prompt text.
- File-level copying from unstable original media is blocked; a completed and verified image or duplicate can be the source.
- Severe mechanical symptoms with irreplaceable data require power-off and professional-recovery escalation; less severe controlled imaging is a confirmed `caution` intervention with explicit source, destination, customer-risk, and rollback controls.
- BitLocker unlock or data access is accepted only as a confirmed `caution` intervention with authorization, matching key-ID prerequisites, and rollback.
- Recovery keys are rejected before persistence and must be entered privately by the customer in Windows.
- The current action is invalidated before new evidence or model work, and completion uses an atomic compare-and-swap write.
- The application never interprets model text as executable code.
- Model reasoning is advisory; the technician records what was actually done.

## Review and freshness

Cards should include a `verified_at` date and optional `review_after` date. The UI should mark stale material rather than silently treating it as current. Knowledge releases should be versioned, signed or checksummed, and tested against retrieval queries before installation on the offline laptop.
