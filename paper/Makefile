PAPER = main
TEX_DIR = tex

.PHONY: all clean view watch

all: $(TEX_DIR)/$(PAPER).pdf

$(TEX_DIR)/$(PAPER).pdf: $(TEX_DIR)/$(PAPER).tex $(TEX_DIR)/refs.bib $(wildcard $(TEX_DIR)/sections/*.tex)
	cd $(TEX_DIR) && pdflatex -interaction=nonstopmode $(PAPER).tex
	cd $(TEX_DIR) && bibtex $(PAPER) || true
	cd $(TEX_DIR) && pdflatex -interaction=nonstopmode $(PAPER).tex
	cd $(TEX_DIR) && pdflatex -interaction=nonstopmode $(PAPER).tex

view: all
	xdg-open $(TEX_DIR)/$(PAPER).pdf

clean:
	cd $(TEX_DIR) && rm -f *.aux *.bbl *.blg *.log *.out *.toc $(PAPER).pdf
	cd $(TEX_DIR)/sections && rm -f *.aux

wordcount:
	@cd $(TEX_DIR) && for f in sections/*.tex; do echo "$$f: $$(detex $$f 2>/dev/null | wc -w) words"; done
