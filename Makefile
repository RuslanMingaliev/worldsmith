generate:
	python tooling/generate_module.py --target all

eval:
	python tooling/run_evals.py

regen:
	rm -rf generated/game
	python tooling/generate_module.py --target all
