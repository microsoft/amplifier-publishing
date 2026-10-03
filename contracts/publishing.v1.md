# Publishing contract — v1

Status: documentation consolidation for repository review, 2026-10-03.
Scope: existing `amplifier-publishing` 0.1.1 public behavior; no new runtime,
transport or schema obligations are proposed. Parent: [local vision](../docs/VISION.md).
Inherited approval belongs to the linked family direction, not to this document
merely because it exists. A changed promise requires an explicit consumer impact
and review; unqualified acceptance does not weaken the promise.

## Public surface and authority

[README API/records/storage](../README.md) owns the Publisher API and record
meanings. [Private service contract](../docs/PUBLISHING-TARGET.md) owns
`static-publishing-v1`, guarded RPC/import fields, limits and SSH receipt proof.
Reference those definitions rather than copying wire schemas here. `PROVENANCE.json`
is extraction evidence, not a claim that current files equal their original source.

[AHP](https://microsoft.github.io/agent-host-protocol/) and
[ACP](https://agentclientprotocol.com/) own their upstream wire semantics. This
library supplies optional publication mechanisms; host/agent/client integration
must negotiate its own capability and retain upstream meanings. It neither
imports native runtimes nor creates a second native history authority.

## Promises, falsifiers and executable checks

| Clause | Public promise and boundary | Falsifier | Existing acceptance checks |
| --- | --- | --- | --- |
| PUB1 | Capture/hash safe immutable static bytes; reviews bind the exact release. Build never compiles or deploys. Source and storage stay separate. | Later source edits change served bytes; review/deploy accepts altered snapshot bytes. | [Library tests](../tests/test_publishing_library.py): `test_actual_build_preview_review_deploy_update_rollback_stop_remove`, `test_immutable_digest_detects_tampering_before_and_during_serve`, `test_export_release_reads_only_owned_immutable_snapshot`. |
| PUB2 | Record intent before effects, fence revisions and preserve exact historical retry results. Unknown outcomes never replay automatically. | Changed payload adopts an older success; a crash silently redeploys. | [Library tests](../tests/test_publishing_library.py): `test_exact_retries_are_historical_and_changed_payload_is_rejected`, `test_stale_revision_and_rollback_requires_prior_deploy`, `test_real_process_crash_fences_unknown_without_replay`. |
| PUB3 | Guard every service operation/read with the selected persistent service identity; transport receipt proof covers the exact canonical admission. Legacy evidence remains unproven until exact original arguments are verified. | Service replacement receives a mutation after preflight; matching request ID alone proves different arguments. | [Remote tests](../tests/test_publishing_remote.py): `test_ssh_pins_discovery_and_service_swap_after_preflight_is_rejected`, `test_exact_rpc_proof_covers_review_note_and_survives_restart`, `test_legacy_receipt_requires_original_exact_retry_before_proof`, `test_interrupted_rpc_never_borrows_success_from_unproven_inner_receipt`. |
| PUB4 | Page scoped metadata before loading detail; exact selected reads preserve full evidence. Complete exports load only their selected session and retain insertion order. | A page or selected export decodes unrelated historical records, or drops exact receipt proof. | [Page tests](../tests/test_publishing_pages.py): `test_pages_are_indexed_scoped_and_keep_selected_evidence`, `test_large_cold_history_does_not_enter_selected_reads`, `test_large_service_receipt_history_stays_bounded_and_prefers_rpc`. |
| PUB5 | One process owns a Publisher store; local listener liveness is explicit. Stop/remove retain content/reviews/receipts; snapshot and restore never resume historical listeners or erase source. | Another service recovers a live store; closing the old owner unlinks a replacement endpoint; restore repeats publication. | [Library tests](../tests/test_publishing_library.py): `test_root_has_one_process_owner`, `test_consistent_backup_restores_audit_and_explicit_resume_only`; [remote tests](../tests/test_publishing_remote.py): `test_service_owner_exclusion_and_replaced_socket_are_preserved`. |
| PUB6 | Exposure/limits are truthful: private numeric binds, owner-only admin socket, loopback previews and bounded transfers; verified bytes and client reachability are distinct outcomes. | A remote loopback URL is claimed reachable, public bind is accepted, or malformed/lost replies become confirmed success. | [Remote tests](../tests/test_publishing_remote.py): `test_private_service_configuration_guards`, `test_remote_loopback_never_claims_client_reachability`, `test_actual_subprocess_output_overflow_is_bounded_and_unknown`, `test_url_verification_fetches_exact_bytes_over_actual_http`. |

## Consumer obligations

Authorize the prebuilt source and session scope before calls. Retain original
request payload/ID, target service UUID, canonical payload digest and immutable
release/session/site/manifest identities. Exact retry follows the documented
receipt rules; absent/mismatched proof stays unknown. Current site state is not
proof of an earlier operation. Legacy product import retains source bytes/hashes,
reference maps and unknown receipts; byte import creates neither historical
review nor service/deployment proof.

Keep workspace/artifact access and cleanup dependency maps alongside library
references. Missing source paths or site removal never authorize history/content
purge. Interactive consumers use `page`; complete exports are explicit requests.
Keep optional publication failures scoped to that capability.

Classify maintenance reads honestly: `receipt` and `inspect_lifetime` are passive;
other site/release/page reads may persist a dead listener's interruption and
advance its revision. Local listener counts do not cover queued/in-flight RPCs,
other processes or remote publication lifetime. Fence intake and hold the actual
owner; separately account for the managed service and preserve both Publisher
and sibling service stores during backup/restore.

## Family clause mapping

These links use reviewed family reference revision
`625af2f2832fafc8152f6078061d626f160362a4`; they are references, not copied standards.

- [CB1–7](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/component-boundaries.v1.md): standalone consumers, public ownership, scoped implementation and actual release/lifetime evidence apply to this library.
- [WS1, WS3, WS5](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/working-set.v1.md): preserve durable source/evidence, load selected detail, and charge work to scoped dependencies. Native catalog rules stay with their owners.
- [HP1, HP5–6](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/host-protocol.v1.md) and [AP1–3, AP6](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/agent-protocol.v1.md): the consumer retains negotiated host/agent semantics and native authority. Publishing is neither a substitute host nor execution adapter.
- [CS1, CS4, CS7, CS9](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/client-state.v1.md) and [CX3, CX6–7](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/client-experience.v1.md): consumers bind exact targets, retain/reconcile intent and present consistent progress/limits. UI and device acceptance stay client-owned.
- [CD1–6](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/client-development.v1.md): reference one semantic owner, declare consumer impact and distinguish source, package, peer and deployed evidence.
- [MA1–3, MA6–10](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/contracts/maintenance.v1.md): exact ownership/proof and retained passive recovery apply; whole-product archival/activation coverage is distribution-owned.

## Qualification and open acceptance

[PR3](https://github.com/microsoft/amplifier-publishing/pull/3) qualified source
`8117f1bb88073e93590ec49c3160bd51270af605`, merged as
`6f1bfa6fbf32ff334cff3adeeffdf58360595bd4` with the same source tree. 178 source
and 178 independently installed-wheel tests passed on macOS/Python 3.13.11,
zero skips. The sealed 0.1.1 wheel SHA256 is
`2542d40ff4ff92a232df1f64c2a984d4bbfc8ff0a4963f3a724ebe86dd7e8af1`.
[Installed qualification runner](../scripts/qualify-installed.sh) reproduces
package isolation and contract tests when runtime/package changes require it.
This documentation successor is not part of that sealed package.

Actual account-backed SSH/provider, Linux execution, remote supervisor/lifetime,
product legacy record import, complete product backup/restore, browser/device,
TLS/firewall and live adoption remain unqualified separately. Contract promises
remain desired behavior; fixture passes do not establish those external checks.
No new scope is proposed by this packet; future features need their own review.
