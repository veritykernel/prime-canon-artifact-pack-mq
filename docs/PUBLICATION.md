# Rendered publication

Use `scripts/publish_rendered_subject.sh <subject-slug>` for the configured
stage destination. The target directory must already exist. The guard accepts
only this verified publisher or its no-effect dry run.

The publisher checks the current view, render execution receipt, and drift
receipt against the expected subject and output path. The execution receipt
must bind the exact current view, active node bytes, and render policy bytes.
Historical receipts without that binding fail closed until a reviewed successor
render. Drift and export checks recompute the binding without rewriting it.
The publisher reads the rendered source once, verifies the SHA-256 recorded by
the execution receipt, and publishes those same bytes with an atomic
replacement under the fixed stage root. It rejects linked path components and
leaves the existing target untouched if verification fails.

Before publication, every stage directory component must be owned by root or
the invoking user and must not be group or world writable. Root-owned sticky
intermediate directories are allowed; the final stage directory is not. A
group-writable `/Users/Shared/nuum-work/stage` is rejected. Its owner must
qualify a protected destination or an
approved permission change, including the other consumers, before a fresh
signed render and publication. The publisher does not change that directory.
