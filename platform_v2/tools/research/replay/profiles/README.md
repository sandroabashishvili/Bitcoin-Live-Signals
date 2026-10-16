# Historical replay specifications and decisions

The JSON files here were grouped from the replay package root on 2026-10-15.
Their contents are unchanged. Versioned approval/promotion fields describe the
original historical experiment, not current deployment authorization.

`shadow_candidate_set_v2.json` remains the default of `forward_shadow_replay`;
its sibling promotion-record reference remains valid in this directory.
Use `platform_v2/tools/research/replay/profiles/<filename>.json` when explicitly
passing a spec. Python replay module paths did not change.
