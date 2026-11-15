# Library boundary

This codebase is yours: what it's for and how it's built are your call, and you'll keep building on it.

Read [local vision](docs/VISION.md) and [publishing contract v1](contracts/publishing.v1.md)
with their linked family direction and acceptance limits before changing behavior.
Reference upstream AHP/ACP and the owning API definitions; do not duplicate them
or treat this documentation packet as approval for new scope.

Read README.md and PROVENANCE.json before changes. Keep runtime and client ownership outside this library. Preserve histories and unknown outcomes; never replay effects to reconstruct state. Build a wheel, test it in an isolated consumer, and run the contract tests before claiming completion. Do not import sibling source trees. Public integration contracts belong with their owning API.

For documentation-only successors, verify references and prove runtime/test source
equality to the qualified revision. Preserve its sealed artifacts and evidence;
do not claim the successor documentation was included in the previously built package.

## Ecosystem maps

Keep this repository's README and product-page maps aligned with the
[Constellation map guide](https://github.com/microsoft/amplifier-constellation/blob/main/docs/ecosystem-maps.md)
and its canonical registry; start with this repository's
`docs/ecosystem-map.json`. When creating, renaming, splitting, retiring, or
changing a role, interface, parent, or dependency, inspect incoming and outgoing
relationships and update every affected parent/consumer map and link, including
the centralized product pages. Regenerate from source data and synchronize local
records/images rather than hand-editing generated images. Describe actual
boundaries and optional choices; a role highlight is not a compatibility claim.
Documentation work does not authorize deployment or resume paused product work.
