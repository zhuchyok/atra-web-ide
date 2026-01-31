# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD  ?= sphinx-build
SOURCEDIR    = .
BUILDDIR     = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the -M flag
# (see $(SPHINXBUILD) -M help for a list of all available targets).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Custom targets
clean:
	rm -rf $(BUILDDIR)/*

html:
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo "HTML документация создана в $(BUILDDIR)/html/"

pdf:
	@$(SPHINXBUILD) -M latexpdf "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo "PDF документация создана в $(BUILDDIR)/latex/"

serve:
	@echo "Запуск локального сервера документации..."
	@cd $(BUILDDIR)/html && python -m http.server 8080
	@echo "Документация доступна по адресу: http://localhost:8080"

install:
	@echo "Установка зависимостей для документации..."
	@pip install sphinx sphinx-autodoc-typehints sphinx-rtd-theme

all: clean html
	@echo "Документация готова!"
