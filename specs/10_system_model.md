# System Model

## Overview

The system is a small spec-driven generation pipeline for a retro shooter prototype.

The pipeline has five major parts:

1. Reference Corpus
2. Spec Pack
3. IR Builder
4. Code Generator
5. Evaluator and Repair Loop

## Components

### 1. Reference Corpus

Location:
- `reference/`

Responsibility:
- provide source material for research
- help identify stable mechanics and constraints
- serve as a comparison baseline

### 2. Spec Pack

Location:
- `specs/`

Responsibility:
- define project goals
- define gameplay requirements
- define constraints and invariants
- define allowed generation strategy

This is the human-readable source of truth.

### 3. IR Builder

Location:
- `ir/`

Responsibility:
- compress specs into a small, generation-oriented representation
- stabilize terminology across prompts
- reduce token waste
- make incremental generation easier

### 4. Code Generator

Location:
- `tooling/`
- `generated/game/`

Target language: **Rust** (stable, safe subset)

Generation method: **LLM-based** (Claude)
- Uses specs and IR as primary context
- Human-guided interactive generation in Claude Code session
- Prompts refined iteratively based on results

Module interfaces: **Implicit**
- Specs describe module responsibilities, not exact signatures
- LLM infers necessary types, functions, and contracts
- Rust compiler catches incompatibilities during build
- Can evolve to explicit contracts if integration problems emerge

Responsibility:
- generate implementation for a requested module or slice
- follow the current specs and IR
- avoid rewriting unrelated modules
- produce explicit, testable code

### 5. Evaluator

Location:
- `evals/`

Responsibility:
- verify build success
- verify smoke behavior
- verify structural invariants
- produce reports that guide repair

## Data Flow

Reference -> Specs -> IR -> Generation -> Evals -> Repair

## Architectural Invariants

- specs remain the primary source of truth
- generated code remains disposable
- unrelated modules are not rewritten during local generation
- evaluation always runs after generation
- repair is preferred over broad rewrite
