extract:
	python tooling/extract_specs.py

generate:
	python tooling/generate_module.py --target all

eval:
	python tooling/run_evals.py

repair:
	python tooling/repair_module.py --target all

regen:
	rm -rf generated/game
	python tooling/generate_module.py --target all
