# System Model

## Overview

The system is a source-of-truth-driven generation pipeline for a retro shooter prototype.

The pipeline has seven major parts:

1. Reference Corpus
2. Knowledge Pack
3. Spec Pack
4. IR Contracts
5. Code Generator
6. Evaluator and Repair Loop
7. Reconciler / PostMortem / Release Editor Loop

## Components

### 1. Reference Corpus

Location:
- `reference/`

Responsibility:
- provide source material for research
- help identify stable mechanics and constraints
- serve as a comparison baseline

### 2. Knowledge Pack

Location:
- `knowledge/`

Responsibility:
- store sanitized mechanics findings extracted from private reference material
- provide public citations for specs without leaking source identifiers
- reject "remembered" genre knowledge when `reference/` is empty

### 3. Spec Pack

Location:
- `specs/`

Responsibility:
- define project goals
- define gameplay requirements
- define constraints and invariants
- define allowed generation strategy

This is the human-readable source of truth for generated game behavior and generation constraints.

### 4. IR Contracts

Location:
- `ir/`

Responsibility:
- compress specs into a small, generation-oriented representation
- pin module responsibilities, exported types/functions, dependencies, and behavioral contracts
- stabilize terminology across prompts
- reduce token waste
- make partial regeneration and Reconciler drift checks tractable

### 5. Code Generator

The generator emits a small Rust crate under `generated/game/`. Module-level structure is pinned in `ir/module_plan.yaml`. As of slice 1 of the FPS migration (specs/45), the rendering surface is split across three modules: **`presentation`** owns window-and-frame constants; **`renderer`** owns the HUD, the game-over border, and the debug-only 2D top-down draw path; **`raycaster`** owns the column-based first-person draw path. `main.rs` chooses between `renderer::draw` and `raycaster::draw` per frame based on the `--render-mode` flag. The default is `raycaster` (flipped from `topdown` in slice 5) — `cargo run` with no flag, every autopilot scenario, and the canonical PR-preview GIF dispatch to the raycaster pipeline. `--render-mode=topdown` is permanently retained as a debug-only alternate mode for development use (specs/45 § Implementation Status); the HUD and game-over border draw on top of either pipeline so they remain identical between modes.

Location:
- `tooling/`
- `generated/game/`

Target language: **Rust** (stable, safe subset)

Generation method: **LLM-based** (Claude)
- Uses knowledge, specs, and IR contracts as primary context
- Runs through CI in PR mode (partial regeneration) and release mode (full regeneration)
- Manual Claude Code generation remains available for exploration
- Prompts are refined from Reconciler/PostMortem findings

Module interfaces: **Contracted**
- `ir/module_plan.yaml` pins generated modules and dependencies
- `ir/contracts/*.yaml` pins module responsibilities, public surface, and key behavior
- Reconciler captures contract drift after generation instead of leaving it implicit

Responsibility:
- generate implementation for a requested module or slice
- follow the current source-of-truth pack
- avoid rewriting unrelated modules
- produce explicit, testable code

### 6. Evaluator

Location:
- `evals/`

Responsibility:
- verify build success
- verify smoke behavior
- verify structural invariants
- produce reports that guide repair

### 7. Reconciler / PostMortem / Release Editor

Location:
- `tooling/agents/`
- `.github/workflows/`

Responsibility:
- capture generated-code drift back into specs and IR contracts
- capture process drift back into agent prompts or ADR drafts
- compose release notes from the actual diff, PR bodies, and run artifacts
- keep PR-mode and release-mode regeneration distinct

## Data Flow

Reference -> Extractor -> knowledge/ -> Architect -> specs/ + ir/contracts/ -> Coder -> generated/ -> Evals -> Reconciler -> specs/ + ir/ -> PostMortem -> tooling/agents/

Release mode adds: generated/ + run artifacts -> Release Editor -> release notes.

## Architectural Invariants

- the public source-of-truth pack for generated game code is `knowledge/`, `specs/`, and `ir/contracts/`
- generated code remains disposable
- unrelated modules are not rewritten during partial regeneration
- evaluation always runs after generation
- PR mode and release mode answer different questions and must not be blurred
- Reconciler/PostMortem findings are folded back into source-of-truth or process docs instead of becoming folklore
