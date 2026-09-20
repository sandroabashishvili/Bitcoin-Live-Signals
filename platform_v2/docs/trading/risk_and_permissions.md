# Risk and Permissions

Updated: 2026-09-12.

A signal selects direction; permissions decide whether an entry can open. Gate flags describe signal components and are not mandatory individual vetoes. Account protection remains independent of the score.

Both systems check actionable signals, usable execution quotes, capital/exposure, slots, duplicates, cooldown/proximity and entry quality/location. Futures also checks direction slots, liquidation buffer and SHORT market-plan alignment. Defaults include nine positions and a two-hour cooldown; consult each subsystem's settings and permission implementation before changing limits.

Spot independently evaluates opposing direction and historical entry quality. Spot's weak-open-position blocker and peer force-close are disabled. Futures no longer produces the old minus-rule peer force-close exits. Legacy fields/readers remain for historical data.

Futures SHORT outside-zone continuation override is disabled. Its separate late-extension quality override remains; a passed quality check does not bypass the required market-plan zone. No new mandatory Gate was introduced by the September 12 audit.

Runtime signal rows and denied-entry ledgers preserve decisions and reasons. In check maps, `true` means the named check passed (including `manual_block`, where true means no manual block). The first failed check supplies the main blocker; read the full map for multiple failures.

Historical replay must reproduce the same decision times, quote assumptions, permissions, portfolio state, fees and exit evidence before candidate results are comparable. Different archived replay tools model different versions; a tool's existence does not establish current-live parity. Preserve manifests, baseline differences and missing-candle limits in each report.
