# Reconcile Log

## Purpose

Audit trail for constants captured by the Reconciler. Lives outside `25_game_tuning.md` because that file sits in `FROZEN_CONTEXT_FILES` and inlining provenance prose there would invalidate the cached prompt prefix on every regen. The Reconciler appends a `## <CONSTANT_NAME>` section here whenever it captures a new constant in `25_game_tuning.md`, and the spec row links back via `(see reconcile_log#<anchor>)`.

## BOT_KILL_MIN_RANGE

*(provenance unrecorded — predates log; backfill from PR/run history if needed)*

## KITE_MODE_LOS_GATE

*(provenance unrecorded — predates log; backfill from PR/run history if needed)*
