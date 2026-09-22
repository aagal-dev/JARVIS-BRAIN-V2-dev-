**AGENTS.md – Project Overview for a Coding Agent**

---

## 1. High‑Level Architecture  

```
┌─────────────────────┐      ┌───────────────────────┐
│   User Input (CLI) │──►►│   JarvisBrain (core)   │
└─────────────────────┘      └───────┬─────┬─────────┘
                                   │     │
                        ┌──────────▼─┐ ┌─▼─────────────┐
                        │ Planner   │ │ Orchestrator │
                        └─────┬─────┘ └───────┬───────┘
          ┌───────────────────▼─────┐  ┌─────▼───────┐
          │ RuntimeStateManager      │  │   Components│
          └───────┬─────────────────┘  └─────┬───────┘
                  ▼                           ▼
        EpisodicMemoryService ↔ MemoryRetrieval (Qdrant + Voyage)
```

* **Entry point** – `main.py` → `JarvisBrain.run(user_request)`. 
* **Planner** creates a **plan** (direct response or multi‑step). 
* **Orchestrator** decides the next action (respond, execute, etc.) using the **available components** registry. 
* **RuntimeStateManager** holds the semantic workflow state (steps, status, results). 
* **Episodic Memory** (service + retrieval) stores/recalls prior conversations via Qdrant (vector store) and Voyage (embedding). 

---

## 2. Core Components  

| Component | Module | Role | Key Types |
|-----------|--------|------|------------|
| **JarvisBrain** | `core/agentic_loop.py` | Central orchestrator of the whole loop (input → retrieval → planning → execution → response). | `JarvisBrainResult`, `RuntimeState`, `OrchestratorResult`, `PlannerResult` |
| **Planner** | `agents/planner.py` | Generates a `PlannerResult` containing either `"direct"` (reply immediately) or `"planned"` (multi‑step objective + steps). | `PlannerState`, `PlannerResult`, `PlannerRelevantContext` |
| **Orchestrator** | `core/orchestrator.py` | LLM‑driven decision maker. Receives the **runtime state** + **available components**, returns an `OrchestratorResult` indicating next step (`respond` or `execute`) and optional actions. | `OrchestratorResult`, `ConversationAgentHandoff` |
| **Conversation Agent** | `agents/conversation_agent.py` | Final chat LLM that produces the user‑facing answer. Receives hand‑off state, runtime, and context. | `ConversationAgentState`, `ConversationAgentOutput` |
| **RuntimeStateManager** | `core/runtime_state_manager.py` | Tracks the semantic workflow: steps, current step, status, results. Provides `create`, `update`, `set_current_step`, `complete`. | `RuntimeState`, `RuntimeStep` |
| **EpisodicMemoryService** | `memory/episodic/service.py` | Consolidates a session’s chat history into **episodes**, persists them, and triggers indexing. | `EpisodicConsolidationResult` |
| **MemoryRetrieval** | `memory/retrieval.py` | Embeds queries (Voyage), runs hybrid search (Qdrant), returns top episodes as context. Also indexes new episodes. | `MemoryRetrievalResult`, `MemoryRetrievalResultItem` |
| **Component Registry** | `core/registry/available_components.py` | Simple static dictionary describing agents & subsystems that the orchestrator can invoke. | `AVAILABLE_COMPONENTS` |

---

## 3. Data Flow  

1. **User request** → `JarvisBrain.run`. 
2. **Memory retrieval** (if configured) → `MemoryRetrieval.retrieve` → returns episodic context. 
3. **Planner** builds `PlannerState` (user request + recent chat + retrieved context) → `run_planner` → `PlannerResult`. 
4. **RuntimeState** is created:
   * `direct` → only `user_request` stored.
   * `planned` → `objective` + list of `RuntimeStep` objects from the plan.
5. Loop (`while step < max_steps`):
   * Update `RuntimeStateManager` current step.
   * **Orchestrator** invoked with current runtime + component registry → `OrchestratorResult`.
   * If `next_step == "respond"` → build `ConversationAgentState` → `run_conversation_agent` → final response returned to CLI.
   * If `next_step == "execute"` → actions are logged (actual execution hooks are not yet implemented).
6. **Session end** (`quit` command) → `JarvisBrain.end_session` → `EpisodicMemoryService.consolidate` → episodes persisted and indexed.

---

## 4. Tech Stack  

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.13 (type‑annotated, pydantic models) |
| **LLM Integration** | `integrations.base_agent` (wrapper around Ollama) |
| **Vector Store** | Qdrant (`integrations.qdrant_client`) |
| **Embedding Service** | Voyage (`integrations.voyage_client`) |
| **Prompt Management** | Markdown files under `prompts/` (orchestrator‑v2.md, planner‑v2.md, etc.) |
| **Threaded Services** | Simple service manager (`threaded_services`) – currently only a `time_service`. |
| **Persistence** | Episodic episodes stored as JSON files in `memory/episodic/episodes/`. |
| **Testing** | Pytest suite (`tests/`). |
| **Package Management** | Poetry (see `pyproject.toml`). |

---

## 5. Component Interaction Diagram (textual)  

```
User ──► JarvisBrain
   │          │
   │          ▼
   │   MemoryRetrieval ←─ Voyage (embed) & Qdrant (search/index)
   │          │
   ▼          ▼
 Planner ──► PlannerResult
   │
   ▼
RuntimeStateManager ──► RuntimeState
   │
   ▼
 Orchestrator ──► OrchestratorResult
   │          │
   │          ├─► respond ──► ConversationAgent (LLM) ──► Output
   │          └─► execute ──► (future action handlers)
   ▼
 Loop repeats until “respond” or step limit reached
```

---

## 6. Extensibility Points  

* **Add new agents / actions** – Extend `AVAILABLE_COMPONENTS` and implement a concrete executor in the `execute` branch of the loop. 
* **Custom prompts** – Replace markdown files referenced in `configs.settings`. 
* **Alternative embedding / vector store** – Swap `VoyageClient` or `QdrantClient` implementations. 
* **Threaded services** – Register more services in `threaded_services/services/` and expose via `service_state_store`. 

---

## 7. Quick Reference for a New Coding Agent  

| What you need | Where to look |
|---------------|----------------|
| **Runtime step definition** | `schemas/system/runtime_state.py` (defines `RuntimeStep`) |
| **Planner input schema** | `schemas/agents/planner_v2.py` |
| **Orchestrator output schema** | `schemas/orchestrator/orchestrator_v2.py` |
| **Conversation hand‑off** | `schemas/orchestrator/orchestrator_v2.py` → `ConversationAgentHandoff` |
| **Episodic episode model** | `schemas/episodic_memory.py` (EpisodeRecord, ChatHistoryMessage) |
| **LLM invocation utility** | `integrations/base_agent.py` (wraps Ollama) |

Use these schemas to construct or parse messages when adding new capabilities.

---
