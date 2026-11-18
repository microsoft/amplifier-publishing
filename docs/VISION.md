# Publishing vision

`amplifier-publishing` lets an independent consumer capture prebuilt static output,
review its exact immutable bytes, and manage publication with durable outcomes.
A release and its evidence survive the original workspace, viewing client and
listener process. Recovery preserves uncertainty instead of repeating effects.

This is a local application of the approved [Amplifier Unified family vision](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/docs/architecture/VISION.md)
and [repository ownership map](https://github.com/microsoft/amplifier-unified/blob/625af2f2832fafc8152f6078061d626f160362a4/docs/architecture/repositories.md).
It consolidates inherited direction and existing public behavior for repository
review; it does not ratify new scope or establish deployment acceptance.

Desired outcomes:

- Reviewed release identity refers to the captured bytes even after source edits.
- Lost replies can be inspected through exact request and target evidence;
  unknown outcomes remain unknown and do not cause automatic publication.
- Selected metadata browsing performs bounded work without loading unrelated history.
- Consumers can install and qualify the library without Unified or a native agent.
- Stopping/removing publication preserves source, releases, reviews and receipts.

This repository owns immutable snapshots, local listener lifecycle, private
service identity, bounded import/export and the explicit transport receipt
contract. The consumer owns build execution, source authorization, authenticated
session scope, workspace/artifact references, reviewed legacy product migration,
cleanup policy and UI. The library can enforce an explicitly supplied prospective
body policy and finish proven detached cleanup; it never infers expiry for legacy
content or activates an application cleanup policy. The service supervisor owns its actual process lifetime;
the distribution owns composition, package activation and deployment acceptance.

Project compilation, arbitrary server execution, account provisioning, SSH key
changes, tunnels, DNS, reverse proxies, TLS, public hosting and native history
mutation are outside this API. AHP/ACP remain authoritative upstream protocols;
this optional library is not an AHP host or ACP agent. Its local mechanism must
not redefine either protocol or bypass the execution owner's native composition.

[Publishing contract v1](../contracts/publishing.v1.md) connects these outcomes to
existing APIs, falsifiers, executable checks and consumer obligations. Gaps in
acceptance remain visible there; passing fixtures never narrows the vision.
