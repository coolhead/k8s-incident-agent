SHELL := /bin/bash
PY ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python

KIND ?= kind
KUBECTL ?= kubectl
CLUSTER_NAME ?= incident-agent
NAMESPACE ?= demo

.DEFAULT_GOAL := help

help: ## Show targets
	@grep -E '^[a-zA-Z0-9_.-]+:.*##' Makefile | awk 'BEGIN{FS=":.*##"}{printf "  %-24s %s\n", $$1, $$2}'

venv: ## Create local venv
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@$(PIP) -q install -U pip wheel
	@echo "✅ Venv ready at $(VENV)"

deps: venv ## Install minimal deps (OSS)
	@$(PIP) -q install typer rich pyyaml kubernetes
	@echo "✅ Python deps installed."

cluster-create: ## Create kind cluster + switch context
	@set -e
	@$(KIND) create cluster --name $(CLUSTER_NAME)
	@$(KUBECTL) config use-context kind-$(CLUSTER_NAME)
	@$(KUBECTL) get nodes -o wide
	@echo "✅ Kind cluster '$(CLUSTER_NAME)' created."

cluster-delete: ## Delete kind cluster
	@$(KIND) delete cluster --name $(CLUSTER_NAME)
	@echo "🧨 Kind cluster '$(CLUSTER_NAME)' deleted."

ns: ## Create demo namespace
	@$(KUBECTL) get ns $(NAMESPACE) >/dev/null 2>&1 || $(KUBECTL) create ns $(NAMESPACE)
	@echo "✅ Namespace '$(NAMESPACE)' ready."

demo-app: ns ## Deploy baseline nginx app + service
	@$(KUBECTL) apply -f local/manifests/demo-app.yaml
	@$(KUBECTL) -n $(NAMESPACE) get pods,svc
	@echo "✅ Demo app deployed."

demo-clean: ## Remove baseline demo app
	@$(KUBECTL) -n $(NAMESPACE) delete deploy/web svc/web --ignore-not-found=true
	@echo "🧹 Demo app removed."

scenario-crashloop: ns ## Deploy crashloop scenario
	@$(KUBECTL) apply -f local/scenarios/crashloop/manifest.yaml
	@echo "✅ CrashLoop scenario deployed."
	@echo "Watch: kubectl -n $(NAMESPACE) get pods -w"

scenario-crashloop-clean: ## Remove crashloop scenario
	@$(KUBECTL) -n $(NAMESPACE) delete deploy/crashy --ignore-not-found=true
	@echo "🧹 CrashLoop scenario removed."

triage: ## Quick manual triage (pods/events) for demo namespace
	@$(KUBECTL) -n $(NAMESPACE) get pods -o wide
	@$(KUBECTL) -n $(NAMESPACE) get events --sort-by=.lastTimestamp | tail -n 30

agent-run: deps ## Run the triage agent
	@PYTHONPATH=local $(PYTHON) -m agent.main -n $(NAMESPACE)

reset: demo-clean scenario-crashloop-clean ## Remove demo resources (keeps cluster)
	@echo "✅ Namespace cleaned (cluster kept)."

nuke: reset cluster-delete ## Remove everything
	@echo "✅ Full cleanup complete."

agent-delete-crashy: deps ## Delete crashy pod (requires --approve in command below)
	@POD=$$(kubectl -n $(NAMESPACE) get pods -l app=crashy -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -z "$$POD" ]; then echo "No crashy pod found"; exit 1; fi; \
	echo "Found: $$POD"; \
	$(PYTHON) -m agent.remediate delete-pod patch-command -n $(NAMESPACE) -p $$POD

agent-delete-crashy-approve: deps ## Delete crashy pod (executes)
	@POD=$$(kubectl -n $(NAMESPACE) get pods -l app=crashy -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -z "$$POD" ]; then echo "No crashy pod found"; exit 1; fi; \
	echo "Deleting: $$POD"; \
	$(PYTHON) -m agent.remediate delete-pod patch-command -n $(NAMESPACE) -p $$POD --approve

agent-fix-crashy: deps ## Patch crashy deployment command (dry-run)
	@PYTHONPATH=local $(PYTHON) -m agent.remediate patch-command -n $(NAMESPACE) -d crashy

agent-fix-crashy-approve: deps ## Patch crashy deployment command (executes)
	@PYTHONPATH=local $(PYTHON) -m agent.remediate patch-command -n $(NAMESPACE) -d crashy --approve


local-agent-run: deps ## Run local triage agent
	@PYTHONPATH=local $(PYTHON) -m agent.main -n $(NAMESPACE)

local-agent-fix-crashy: deps ## Local: patch crashy command (dry-run)
	@PYTHONPATH=local $(PYTHON) -m agent.remediate patch-command -n $(NAMESPACE) -d crashy

local-agent-fix-crashy-approve: deps ## Local: patch crashy command (executes)
	@PYTHONPATH=local $(PYTHON) -m agent.remediate patch-command -n $(NAMESPACE) -d crashy --approve

llm-deps: deps ## Install llm agent deps
	@$(PIP) -q install -r llm_agent/requirements.txt
	@echo "✅ LLM deps installed."

llm-run: llm-deps ## Run LLM agent (read-only unless --approve)
	@$(PYTHON) -m llm_agent.agent.cli -n $(NAMESPACE)

llm-run-approve: llm-deps ## Run LLM agent with approval (executes writes)
	@$(PYTHON) -m llm_agent.agent.cli -n $(NAMESPACE) --approve
