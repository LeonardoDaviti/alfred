.PHONY: setup figures clean

# Stage the example patterns where the runtime expects them (./data/patterns).
setup:
	mkdir -p data/patterns
	cp patterns/expansion/*.json data/patterns/ 2>/dev/null || true
	@echo "patterns staged into ./data/patterns"

# Regenerate all thesis figures (no model needed).
figures:
	python thesis/figures/make_figures.py

clean:
	rm -rf data/patterns data/cache data/stats
