# Generation uses the phase runner (Claude or Codex) and tooling/agents/ prompts.
# See tooling/README.md for local execution and GitHub Actions provider setup.

eval:
	python tooling/run_evals.py

validate:
	python tooling/validate_specs.py --verbose

test-tooling:
	python -m unittest discover -s tooling/tests -v
