# Promotion authorization

`ready: true` in a promotion packet records machine gate results. It does not
authorize a canon write. The promotion command now verifies every replay
manifest input hash and requires a signed, short-lived human approval over the
exact packet, summary, manifest, corpus, and ordered target list before writing.

The approval is a JSON object with exactly these fields:

```json
{
  "kind": "PRIME_CANON_PROMOTION_APPROVAL_V1",
  "subject_slug": "subject-0001",
  "corpus_id": "pc.corpus.subject-0001",
  "corpus_sha256": "<sha256 of corpus index bytes>",
  "packet_sha256": "<sha256 of promotion-readiness-packet.yaml bytes>",
  "summary_sha256": "<sha256 of promotion-readiness-summary.yaml bytes>",
  "manifest_sha256": "<sha256 of promotion-readiness-replay.yaml bytes>",
  "target_refs": ["<exact ordered packet target refs>"],
  "issued_at": "<UTC ISO 8601 timestamp>",
  "expires_at": "<UTC ISO 8601 timestamp within 30 days>",
  "reviewer_principal": "human:reviewer"
}
```

The reviewer must inspect the underlying evidence and exact frozen inputs,
then sign the JSON bytes with an SSH key admitted by the external allowed
signers file, using namespace `prime-canon-promotion-v1`. The allowed signers
file must be outside the repository, root-owned, and not group or world
writable. Repository contributors cannot establish reviewer authority by
editing a checked-in identity or receipt. The operator supplies the external
approval, its SSH signature, and the allowed signers path via
`PRIME_CANON_APPROVAL`, `PRIME_CANON_APPROVAL_SIGNATURE`, and
`PRIME_CANON_ALLOWED_SIGNERS` respectively. An absent signer configuration
causes a fail-closed result. No signer or approval is supplied in this pack.

For an approved new subject, run `python scripts/promote_nodes_and_current_state.py
. <subject-slug>` with those environment variables set. The command rejects
existing node, receipt, or current-view outputs, so an uncertain or previous
promotion must be reconciled before retrying. Historic receipts remain
unchanged. Compiler-generated admissibility from contributor labels now
fails the independent-source-verification burden; an
independent reviewer must assess real source material before new readiness can
pass.
