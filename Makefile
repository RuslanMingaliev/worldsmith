# Generation is manual: human + Claude Code session, driven by the agent prompts
# in tooling/agents/. There is no `make generate` button — see CLAUDE.md and
# specs/00_project_goal.md § Generation Model for the workflow.

eval:
	python tooling/run_evals.py

validate:
	python tooling/validate_specs.py --verbose
