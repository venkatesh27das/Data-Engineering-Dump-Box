# CODEX.md — Knowledge Graph Builder POC

## 1. Purpose

Build a local-first POC application called **Knowledge Graph Builder**.

The application allows a user to:

1. Define a knowledge objective.
2. Upload structured schema files and/or unstructured documents.
3. Run an autonomous Knowledge Asset Construction Agent.
4. Generate graph-ready knowledge assets.
5. Review the generated assets and their quality/evidence.
6. Approve and publish selected assets to Neo4j Aura.
7. Explore the resulting graph visually.

This is a **POC**, not a production enterprise platform. Keep the implementation clean, modular, believable, and easy to demonstrate.

The POC must prove:

- structured-only processing
- unstructured-only processing
- hybrid structured + unstructured processing
- dynamic agent planning
- autonomous tool selection
- reactive retry / re-planning
- graph-ready asset generation
- provenance and confidence tracking
- human review for low-confidence assets
- Neo4j publication
- graph exploration

Do not over-engineer enterprise-scale capabilities such as multi-tenancy, distributed queues, Kubernetes, CDC, complex IAM, or high availability.

---

# 2. Visual Source of Truth

The folder:

```text
application_screenshot/
```

contains the approved application screenshots.

**Codex must inspect this folder before building any frontend screen.**

Treat these screenshots as the source of truth for:

- layout
- navigation
- information hierarchy
- spacing
- card proportions
- table density
- button placement
- graph explorer layout
- typography hierarchy
- border radius
- visual tone
- navigation behavior

Do not redesign the application unless a UI detail is technically impossible.

The application has only three primary navigation items:

```text
Build
Graph Assets
Graph Explorer
```

Do not add Dashboard, Sources, Jobs, Admin, Monitoring, Governance, or other primary navigation tabs.

Settings and connection indicators live in the top header.

---

# 3. POC Scope

## 3.1 Structured data input

For the POC, do **not** connect directly to enterprise databases.

Users upload schema-oriented files such as:

```text
.sql
.json
.csv
```

Supported structured input examples:

- CREATE TABLE DDL
- exported database schema
- table and column metadata CSV
- schema JSON
- optional small sample CSV files

The structured-data path should extract:

- tables
- columns
- data types
- primary keys when present
- foreign keys when present
- inferred keys when possible
- table descriptions
- candidate business entities
- candidate relationships
- semantic concepts
- schema-to-enterprise-concept mappings

Do not require actual table data for the basic POC.

---

## 3.2 Unstructured data input

Users can upload:

```text
.pdf
.docx
.png
.jpg
.jpeg
```

The unstructured path should create usable text and document structure, then derive graph-ready knowledge.

Expected outputs include:

- document metadata
- sections/pages
- chunks/evidence spans
- entities
- relationships
- concepts
- facts/claims
- events where relevant
- source references
- confidence values

Scanned PDFs or images may use OCR.

---

## 3.3 Hybrid mode

Hybrid mode combines the structured and unstructured paths.

Example:

```text
supplier_schema.sql
contracts.pdf
product_catalog.docx
```

The agent should be able to identify that:

- a supplier from the schema
- a supplier mentioned in a contract
- an alias in a product document

may represent the same canonical entity.

Hybrid mode should therefore invoke cross-source entity resolution.

---

# 4. Core Product Concept

The main agent is the:

```text
Knowledge Asset Construction Agent
```

Its job is not to directly create random Neo4j nodes.

Its canonical output is a typed:

```text
KnowledgeAssetPackage
```

Neo4j is a downstream graph publication target.

Architecture:

```text
Sources
   ↓
Knowledge Asset Construction Agent
   ↓
KnowledgeAssetPackage
   ↓
Review / Validate
   ↓
Graph Publisher
   ↓
Neo4j Aura
   ↓
Graph Explorer
```

This separation is mandatory.

---

# 5. Recommended Technology Stack

## Frontend

Use:

```text
React
TypeScript
Vite
Tailwind CSS
Cytoscape.js
```

Use a lightweight component approach.

Do not introduce a heavy UI framework unless clearly needed.

Prefer:

- semantic HTML
- reusable React components
- Tailwind utility styling
- Lucide icons or equivalent lightweight open-source icon library

---

## Backend

Use:

```text
Python 3.12+
FastAPI
Pydantic
Deep Agents
LangGraph
LangChain model/tool integrations only where needed
Neo4j Python driver
SQLite
```

The backend runs locally on the developer Mac.

---

## Local model runtime

Use:

```text
LM Studio
```

Default base URL:

```text
http://localhost:1234/v1
```

LM Studio must be integrated through an abstraction.

Do not scatter direct LM Studio calls across the codebase.

Implement:

```python
class ModelProvider:
    async def chat(...)
    async def structured_generate(...)
    async def embed(...)
    async def health_check(...)
```

Then implement:

```text
LMStudioProvider
```

All model names must be configurable.

---

## Graph database

Use:

```text
Neo4j Aura
```

Neo4j is an external online dependency.

Credentials must be supplied through environment variables.

Use the official Python package:

```text
neo4j
```

Do not use the deprecated `neo4j-driver` package.

---

## Graph visualization

Use:

```text
Cytoscape.js
```

Do not iframe Neo4j Browser as the primary visualization.

The Graph Explorer should visually match the screenshot while retrieving graph data from the backend.

---

# 6. Agent Framework Decision

Use:

```text
Deep Agents
+
LangGraph runtime
```

Reasoning model:

- Deep Agents provides the high-level autonomous agent harness.
- LangGraph provides durable state, tool orchestration, loops, interrupts, persistence, and reactive execution.

Do not implement the application as a fixed linear pipeline.

Incorrect:

```text
parse
→ entity extraction
→ relationship extraction
→ graph creation
```

Desired behavior:

```text
understand objective
→ inspect sources
→ determine modalities
→ create plan
→ select tools/subagents
→ execute
→ evaluate result
→ react/re-plan if needed
→ converge
→ create asset package
```

The agent must be free to skip irrelevant steps.

Example:

- schema-only project should not invoke OCR
- PDF-only project should not run SQL schema analysis
- low-quality scanned PDF may trigger OCR after parsing quality fails
- ambiguous entity resolution should trigger additional evidence analysis

---

# 7. Agent Architecture

Implement one supervisor and a small number of specialist subagents.

Do not create dozens of agents.

Initial architecture:

```text
Knowledge Asset Supervisor
        │
        ├── Source Analyst
        ├── Knowledge Engineer
        ├── Graph Modeller
        └── Quality Reviewer
```

---

## 7.1 Knowledge Asset Supervisor

Responsibilities:

- understand project objective
- inspect available sources
- classify source modality
- decide which graph asset levels are required
- formulate tasks
- delegate to specialist agents/tools
- track execution state
- inspect results
- trigger re-planning
- determine whether human review is required
- assemble final KnowledgeAssetPackage

The supervisor must not perform every operation itself.

Use specialist agents and deterministic tools.

---

## 7.2 Source Analyst

Responsibilities:

Structured:

- parse DDL
- inspect schema JSON/CSV
- discover tables and attributes
- extract explicit PK/FK
- infer candidate relationships
- identify likely business objects

Unstructured:

- identify file type
- parse file
- detect document structure
- detect low parsing quality
- decide whether OCR is needed
- return normalized document representation

Output should be typed.

Example:

```python
class SourceAnalysisResult(BaseModel):
    source_id: str
    modality: Literal["structured", "unstructured"]
    source_type: str
    summary: str
    detected_assets: list[str]
    recommended_tools: list[str]
    warnings: list[str]
```

---

## 7.3 Knowledge Engineer

Responsibilities:

- identify business concepts
- extract entities
- extract relationships
- extract facts/claims
- extract events
- extract aliases
- map synonyms
- propose taxonomy/ontology concepts where appropriate
- generate semantic mappings
- preserve evidence references

The Knowledge Engineer must return structured data.

Do not rely on free-form prose as the source of truth.

---

## 7.4 Graph Modeller

Responsibilities:

- convert semantic assets into graph-ready schema
- define node labels
- define relationship types
- identify node properties
- identify edge properties
- determine constraints
- prepare graph publication manifest

Graph Modeller should not directly publish by default.

It creates a graph model inside the KnowledgeAssetPackage.

---

## 7.5 Quality Reviewer

Responsibilities:

Evaluate:

- entity confidence
- relationship confidence
- fact confidence
- source/evidence coverage
- semantic consistency
- duplicates
- possible contradictions
- orphan nodes
- missing provenance
- graph schema validity
- unresolved aliases

Return:

```text
PASS
REVIEW_REQUIRED
REPLAN_REQUIRED
FAIL
```

The supervisor decides the next step.

---

# 8. Reactive Execution Pattern

At least one genuine reactive loop must exist in the implementation.

Example 1:

```text
parse document
→ parsing confidence poor
→ reviewer flags issue
→ supervisor selects OCR
→ source reprocessed
→ extraction continues
```

Example 2:

```text
entity resolution
→ duplicate ambiguity remains
→ reviewer flags entities
→ supervisor requests more evidence
→ Knowledge Engineer analyzes documents
→ resolver retries
```

Example 3:

```text
relationship has no evidence
→ validation fails
→ agent re-runs evidence-focused relation extraction
```

Record these as observable agent events.

Do not expose hidden chain-of-thought.

The UI may show:

```text
Analyzing sources
Discovering concepts
Extracting entities
Resolving entities
3 ambiguous entities detected
Re-running entity resolution with additional evidence
Validating assets
Completed
```

---

# 9. Tool Architecture

Keep deterministic operations as tools.

Suggested structure:

```text
backend/app/tools/

structured/
    parse_ddl.py
    parse_schema_json.py
    parse_schema_csv.py
    infer_keys.py
    infer_schema_relationships.py

documents/
    parse_pdf.py
    parse_docx.py
    parse_image.py
    run_ocr.py
    chunk_document.py

knowledge/
    extract_entities.py
    extract_relationships.py
    extract_facts.py
    extract_events.py
    discover_concepts.py
    resolve_entities.py
    map_semantics.py

graph/
    build_graph_schema.py
    validate_graph_schema.py
    generate_cypher.py
    publish_neo4j.py
    query_neo4j.py

quality/
    score_assets.py
    validate_evidence.py
    detect_duplicates.py
    detect_conflicts.py
    validate_package.py
```

Tools should have narrow responsibilities and typed inputs/outputs.

Do not create one giant `process_everything()` tool.

---

# 10. Graph Asset Levels

Support these graph-ready asset categories.

## L0 — Source and Evidence Assets

Examples:

- source
- file
- page
- section
- chunk
- schema
- table
- column
- evidence span
- provenance metadata

---

## L1 — Metadata Assets

Examples:

- data asset
- document
- table
- column
- schema relationship
- owner if supplied
- tags if supplied

---

## L2 — Entity Assets

Examples:

- Supplier
- Product
- Contract
- Customer
- Organization
- Person
- Policy
- DataProduct

Each entity should include:

```text
canonical ID
name
type
aliases
attributes
source references
confidence
```

---

## L3 — Relationship Assets

Each relationship should include:

```text
source entity ID
target entity ID
relationship type
properties
confidence
evidence
source references
```

---

## L4 — Semantic Assets

Examples:

- concepts
- glossary terms
- synonyms
- semantic mappings
- taxonomy candidates
- ontology classes
- concept hierarchy

---

## L5 — Contextual Knowledge Assets

Examples:

- facts
- claims
- events
- temporal assertions
- business rules
- evidence-linked statements

---

# 11. Canonical Pydantic Models

Implement Pydantic domain models under:

```text
backend/app/domain/
```

At minimum:

```python
SourceAsset
EvidenceReference
Entity
Relationship
Concept
Fact
Event
SemanticMapping
GraphNodeDefinition
GraphRelationshipDefinition
GraphSchema
QualityIssue
QualityReport
KnowledgeAssetPackage
```

Recommended fields:

```python
class EvidenceReference(BaseModel):
    source_id: str
    source_name: str
    page: int | None = None
    section: str | None = None
    chunk_id: str | None = None
    excerpt: str | None = None
```

```python
class Entity(BaseModel):
    id: str
    canonical_name: str
    entity_type: str
    aliases: list[str] = []
    attributes: dict = {}
    evidence: list[EvidenceReference] = []
    confidence: float
    review_status: str = "pending"
```

```python
class Relationship(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    properties: dict = {}
    evidence: list[EvidenceReference] = []
    confidence: float
    review_status: str = "pending"
```

```python
class QualityReport(BaseModel):
    overall_score: float
    evidence_coverage: float
    average_confidence: float
    consistency: float
    completeness: float
    issues: list[QualityIssue]
```

```python
class KnowledgeAssetPackage(BaseModel):
    package_id: str
    project_id: str
    sources: list[SourceAsset]
    entities: list[Entity]
    relationships: list[Relationship]
    concepts: list[Concept]
    facts: list[Fact]
    events: list[Event]
    semantic_mappings: list[SemanticMapping]
    graph_schema: GraphSchema
    quality_report: QualityReport
```

Avoid `Any` unless absolutely required.

---

# 12. Structured Output Strategy

All LLM outputs that become application state must be schema-constrained.

Use structured JSON generation wherever possible.

Never parse important business objects from arbitrary prose if a schema can be used.

Examples:

```text
EntityExtractionResponse
RelationshipExtractionResponse
ConceptDiscoveryResponse
EntityResolutionResponse
GraphModelResponse
QualityReviewResponse
```

Validate every response with Pydantic.

When validation fails:

1. retry with corrective instruction
2. if retry fails, emit a controlled tool error
3. let supervisor decide whether to re-plan or stop

---

# 13. Model Configuration

Create:

```text
backend/config/models.yaml
```

Example:

```yaml
lmstudio:
  base_url: "http://localhost:1234/v1"

models:
  orchestrator:
    name: "${LMSTUDIO_ORCHESTRATOR_MODEL}"
    temperature: 0.2

  knowledge:
    name: "${LMSTUDIO_KNOWLEDGE_MODEL}"
    temperature: 0.1

  embedding:
    name: "${LMSTUDIO_EMBEDDING_MODEL}"
```

Do not hardcode a specific model name.

Allow the same model to be configured for orchestrator and knowledge extraction.

---

# 14. Backend Project Structure

Use this target structure:

```text
knowledge-graph-builder/
│
├── application_screenshot/
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── build/
│   │   │   ├── assets/
│   │   │   └── graph/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── types/
│   │   └── styles/
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── domain/
│   │   ├── providers/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── storage/
│   │   ├── tools/
│   │   ├── orchestration/
│   │   └── main.py
│   ├── config/
│   ├── tests/
│   └── pyproject.toml
│
├── data/
│   ├── uploads/
│   ├── processed/
│   └── artifacts/
│
├── .env.example
├── CODEX.md
└── README.md
```

---

# 15. Persistence Strategy

Use SQLite for POC application state.

Persist:

```text
projects
sources
runs
agent_events
asset_packages
review_decisions
neo4j_publish_history
```

Large generated package JSON may be stored as files under:

```text
data/artifacts/
```

with metadata in SQLite.

Uploaded files go under:

```text
data/uploads/<project_id>/
```

Do not store uploaded binary content in SQLite.

---

# 16. Core API Design

Use FastAPI.

Base path:

```text
/api/v1
```

Implement at minimum:

## Health

```http
GET /health
```

Return:

```json
{
  "api": "ok",
  "lmstudio": "connected",
  "neo4j": "connected"
}
```

---

## Project

```http
POST /projects
GET /projects/{project_id}
```

Project fields:

```text
name
knowledge_objective
processing_mode
graph_depth
review_low_confidence
```

---

## Upload

```http
POST /projects/{project_id}/sources
GET  /projects/{project_id}/sources
DELETE /projects/{project_id}/sources/{source_id}
```

Support multipart file upload.

Validate extensions and file size.

---

## Generate

```http
POST /projects/{project_id}/runs
GET  /projects/{project_id}/runs/{run_id}
GET  /projects/{project_id}/runs/{run_id}/events
```

The generate call should return quickly with a run ID.

For POC, background execution can use an in-process FastAPI background task or a simple application task manager.

Do not introduce Celery/Kafka unless necessary.

---

## Assets

```http
GET /projects/{project_id}/assets
GET /projects/{project_id}/assets/entities
GET /projects/{project_id}/assets/relationships
GET /projects/{project_id}/assets/concepts
GET /projects/{project_id}/assets/facts
GET /projects/{project_id}/assets/events
```

Support:

```text
search
type
source
confidence range
review status
pagination
```

---

## Review

```http
POST /projects/{project_id}/assets/{asset_id}/approve
POST /projects/{project_id}/assets/{asset_id}/review
POST /projects/{project_id}/assets/{asset_id}/reject
```

---

## Publication

```http
POST /projects/{project_id}/publish/neo4j
GET  /projects/{project_id}/publish/status
```

Only publish approved assets by default.

---

## Graph

```http
GET  /projects/{project_id}/graph
GET  /projects/{project_id}/graph/node/{node_id}
POST /projects/{project_id}/graph/query
```

Graph endpoint should return Cytoscape-friendly data:

```json
{
  "nodes": [
    {
      "data": {
        "id": "ENT-1",
        "label": "ACME Corporation",
        "type": "Supplier"
      }
    }
  ],
  "edges": [
    {
      "data": {
        "id": "REL-1",
        "source": "ENT-1",
        "target": "ENT-2",
        "label": "HAS_CONTRACT"
      }
    }
  ]
}
```

---

# 17. Agent Event Streaming

The Build screen displays generation progress.

Preferred implementation:

```text
Server-Sent Events (SSE)
```

Endpoint:

```http
GET /projects/{project_id}/runs/{run_id}/stream
```

Event payload:

```json
{
  "timestamp": "...",
  "stage": "entity_resolution",
  "status": "running",
  "title": "Resolving entities",
  "message": "3 ambiguous entities found",
  "event_type": "replan"
}
```

Do not send hidden reasoning.

Only send user-safe operational events.

If SSE introduces unnecessary complexity early, polling may be implemented first, then upgraded.

---

# 18. Neo4j Integration

Environment variables:

```text
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j
```

Use a provider/service abstraction:

```python
class GraphStore:
    async def health_check(...)
    async def publish_package(...)
    async def get_subgraph(...)
    async def get_node(...)
    async def query(...)
```

Implementation:

```text
Neo4jGraphStore
```

Do not call Neo4j directly inside agents.

Agents may use graph tools that delegate to GraphStore.

---

# 19. Neo4j Publication Rules

Use stable canonical identifiers.

Prefer MERGE patterns.

Example conceptual behavior:

```cypher
MERGE (n:Supplier {asset_id: $asset_id})
SET
    n.name = $name,
    n.confidence = $confidence,
    n.project_id = $project_id
```

Relationship:

```cypher
MATCH (a {asset_id: $source_id})
MATCH (b {asset_id: $target_id})
MERGE (a)-[r:HAS_CONTRACT {asset_id: $relationship_id}]->(b)
SET r.confidence = $confidence
```

Do not create arbitrary relationship types directly from untrusted strings without sanitizing/whitelisting them.

Maintain publication metadata.

Do not delete existing graph data automatically.

---

# 20. Frontend Application Shell

Match the screenshots.

Desktop-first POC.

Target working width:

```text
1440–1600 px
```

Must still remain usable at smaller laptop widths.

Layout:

```text
Top Header
├── App Logo / Name
├── LM Studio status
├── Neo4j Aura status
└── Settings

Left Navigation
├── Build
├── Graph Assets
└── Graph Explorer

Main Content
└── active page
```

Keep the left navigation narrow.

No excessive tabs.

---

# 21. Design Language

Follow `application_screenshot/`.

Primary feel:

```text
clean
minimal
enterprise
light
technical
high information density without clutter
```

Use:

- white / near-white surfaces
- subtle gray borders
- restrained purple/indigo primary accent matching screenshots
- green for healthy/approved status
- orange/amber for review
- red/pink only for warnings/attention
- small subtle shadows only where visible in screenshots

Do not use:

- gradients unless present in screenshots
- glassmorphism
- excessive animation
- huge hero headings
- dark developer-dashboard aesthetics
- chat-first interface
- oversized cards
- unnecessary decorative graphs

---

# 22. Typography

Use a modern sans-serif consistent with screenshots.

Preferred:

```text
Inter
```

Fallback:

```text
system-ui
-apple-system
BlinkMacSystemFont
Segoe UI
sans-serif
```

Approximate scale:

```text
App title:           18–20 px
Page title:          22–26 px
Section title:       14–16 px
Body:                13–14 px
Secondary text:      11–12 px
Table text:          12–13 px
Metric values:       18–22 px
Buttons:             12–14 px
```

Avoid excessively bold typography.

---

# 23. Spacing and Shape

Approximate rules:

```text
Page padding:        24 px
Card padding:        16–20 px
Grid gap:            12–16 px
Section gap:         16–24 px

Small radius:        6–8 px
Card radius:         10–12 px
Button radius:       6–8 px
```

Borders:

```text
1px light gray
```

The application should appear crisp rather than heavily rounded.

---

# 24. Screen 1 — Build

Reference the Build screenshot.

Purpose:

```text
Define objective
Upload sources
Configure run
Generate graph assets
Observe latest generation
```

Main content:

## Left / Primary builder area

### 1. Define Knowledge Objective

Large textarea.

Example default demo objective:

```text
Understand suppliers, contracts, products and contractual obligations.
```

Helper text:

```text
This helps the agent determine what to extract and how to model your knowledge.
```

---

### 2. Upload Sources

Two adjacent upload cards:

```text
Structured Data
Unstructured Data
```

Structured:

```text
Upload Schema
.sql .json .csv
```

Unstructured:

```text
Upload Files
.pdf .docx .png .jpg
```

Below them show uploaded source list.

Each file should show:

```text
filename
summary
source category
status
remove action
```

---

### 3. Run Configuration

Controls:

```text
Processing Mode
Graph Depth
Review Low Confidence
Max Tokens
```

Processing mode:

```text
Auto
Structured
Unstructured
Hybrid
```

Graph depth:

```text
Metadata
Entity + Relationships
Semantic
Contextual Knowledge
```

Primary CTA:

```text
Generate Graph Assets
```

---

## Right / Run summary area

When no run exists, show a clean empty-state.

After generation show:

```text
Entities
Relationships
Concepts
Facts
Quality Score
```

Generation Progress:

```text
Analyzing sources
Discovering concepts
Extracting entities
Extracting relationships
Resolving entities
Validating assets
```

Quality Overview:

```text
Evidence Coverage
Confidence Avg.
Consistency
Completeness
Overall Quality
```

Recent Runs may show the latest few runs inside the Build page.

Do not create a separate Jobs tab.

---

# 25. Screen 2 — Graph Assets

Reference the approved Graph Assets screenshot.

Purpose:

```text
Review
Filter
Inspect evidence
Approve
Send to review
Publish
```

Top metric cards:

```text
Entities
Relationships
Concepts
Facts
Quality Score
```

Primary asset tabs:

```text
Entities
Relationships
Concepts
Facts
Events
```

Asset table filters:

```text
Search
Type
Source
Confidence
Review Status
```

Table should support pagination.

Typical columns:

```text
Asset Name
Type
Source
Confidence
Status
Actions
```

Status examples:

```text
Approved
Review
Needs Attention
Pending
Rejected
```

---

## Selected Asset Panel

Right-side details panel.

For an Entity:

```text
Canonical Name
Type
Aliases
Sources
Confidence
Relationships
Evidence References
```

Evidence references should show:

```text
file
page/section/table/column
```

Quick actions:

```text
Approve
Send to Review
Reject if required
```

---

## Validation and Publication

Bottom summary:

```text
Evidence Coverage
Confidence Avg.
Consistency
Completeness
```

Primary action:

```text
Publish Approved Assets to Neo4j
```

Publishing should not automatically include unapproved assets.

---

# 26. Screen 3 — Graph Explorer

Reference the Graph Explorer screenshot.

Purpose:

```text
Explore Neo4j graph
Search
Filter
Traverse
Inspect nodes
Inspect evidence
```

Main toolbar:

```text
Search nodes / relationships / properties
Node Types
Relationship Types
Depth
Clear Filters
```

Optional action:

```text
Open in Neo4j Browser
```

---

## Left graph-side utilities

Graph Overview:

```text
Nodes
Relationships
Node Types
Relationship Types
```

Legend by node type.

Basic control guidance:

```text
Drag
Pan
Scroll / Zoom
Click / Select Node
Box select if supported
Reset View
```

---

## Main graph canvas

Use Cytoscape.js.

Must support:

```text
pan
zoom
fit
node selection
edge selection
node-type styles
edge labels
search highlight
filter
depth-based traversal
re-layout
```

Use restrained node colors by semantic category.

Example categories:

```text
Supplier
Contract
Product
Obligation
Document
Other
```

Do not hardcode these as the only possible types.

Generate deterministic color assignments by node type.

---

## Right Node Details Panel

Tabs:

```text
Overview
Properties
Relationships
Evidence
```

Overview:

```text
name
labels/type
confidence
description
sources
relationship summary
```

Evidence:

```text
source file
page
section
chunk/table/column if available
```

---

## Cypher Panel

Provide an optional advanced panel at the bottom:

```text
Cypher
Template Queries
```

For POC, user-written Cypher should be read-only by default.

Reject dangerous write keywords from the custom query endpoint unless an explicit developer configuration enables writes.

Safe examples:

```text
MATCH
RETURN
WHERE
LIMIT
WITH
UNWIND
OPTIONAL MATCH
```

Do not expose credentials to the frontend.

---

# 27. Frontend State

Use straightforward state management.

Preferred initial approach:

```text
React Query / TanStack Query for server state
React local state for UI state
```

Do not add Redux unless complexity proves it is required.

Keep types under:

```text
frontend/src/types/
```

Generate API types manually or from OpenAPI if convenient.

---

# 28. Loading and Empty States

Every page must have good states.

Examples:

Build:

```text
No sources uploaded
Ready to generate
Agent running
Generation failed
Generation complete
```

Graph Assets:

```text
No package generated
No assets match filter
Assets awaiting review
All approved
```

Graph Explorer:

```text
Nothing published yet
Neo4j disconnected
Graph loading
No results for current filters
```

Avoid blank areas.

---

# 29. Error Handling

User-facing errors must be concise.

Examples:

```text
LM Studio is not reachable.
Start the LM Studio local server and retry.
```

```text
Neo4j Aura connection failed.
Check the configured Aura credentials.
```

```text
This PDF could not be parsed reliably.
The agent will retry using OCR.
```

Backend errors should include internal details in logs but not expose secrets.

---

# 30. Security Rules for POC

Even though this is local:

- use `.env`
- never commit secrets
- never log Neo4j password
- never expose LM Studio internal prompt history unnecessarily
- sanitize filenames
- enforce upload size limit
- validate file extension and MIME type
- sanitize Neo4j label and relationship identifiers
- custom Cypher should default to read-only
- do not execute uploaded SQL
- parse DDL as text only

---

# 31. Environment File

Create:

```text
.env.example
```

Containing:

```text
APP_ENV=development

LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_ORCHESTRATOR_MODEL=
LMSTUDIO_KNOWLEDGE_MODEL=
LMSTUDIO_EMBEDDING_MODEL=

NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

DATABASE_URL=sqlite:///./data/app.db

UPLOAD_DIR=./data/uploads
ARTIFACT_DIR=./data/artifacts

LOW_CONFIDENCE_THRESHOLD=0.80
AUTO_APPROVE_THRESHOLD=0.95
MAX_UPLOAD_MB=50
```

---

# 32. Quality Rules

Initial configurable POC defaults:

```text
>= 0.95
High confidence
eligible for auto-approval if review policy permits

0.80–0.95
Review recommended

< 0.80
Needs attention
```

Do not use confidence alone as the only graph quality measure.

Quality should include:

```text
evidence coverage
confidence
consistency
completeness
duplicate rate
unresolved references
```

---

# 33. Human-in-the-Loop

HITL is intentionally lightweight.

If:

```text
Review Low Confidence = ON
```

then low-confidence assets should be marked:

```text
Review
or
Needs Attention
```

Do not block the entire run because one asset needs review.

The run can complete with review items.

Publication should publish approved assets.

---

# 34. Source Provenance

Every material graph asset must retain provenance.

At minimum:

Structured:

```text
source file
table
column
schema relationship
```

Unstructured:

```text
source file
page if available
section if available
chunk or excerpt if available
```

Hybrid relationships may carry multiple evidence references.

This is a critical POC capability.

---

# 35. Entity Resolution

Implement a pragmatic tiered strategy.

Possible sequence:

```text
1. exact normalized name match
2. alias match
3. deterministic similarity
4. embedding similarity if available
5. LLM-assisted adjudication
6. human review for ambiguity
```

Do not use the LLM for every obvious duplicate.

Store resolution evidence.

---

# 36. Graph Generation Principles

Avoid creating one node for every chunk by default.

Distinguish:

```text
knowledge entity nodes
semantic/concept nodes
source/evidence nodes
```

Evidence may be stored either as graph nodes or external properties/records depending on the graph model.

For POC, prioritize graph readability.

The graph should visually demonstrate enterprise meaning, not become a raw document-chunk graph.

---

# 37. Observability

Use standard Python logging.

Persist high-level run events.

Capture:

```text
run start/end
agent stage
tool invocation
tool success/failure
re-plan event
asset counts
quality metrics
publish event
```

Do not log hidden model reasoning.

Do not build a full observability platform.

---

# 38. Testing

Backend:

```text
pytest
```

Frontend:

```text
Vitest
React Testing Library
```

Minimum backend tests:

- DDL parser
- schema JSON parser
- PDF parser smoke test
- entity model validation
- relationship model validation
- knowledge package validation
- confidence rules
- Neo4j mapping
- graph query sanitization
- agent tool registration
- failed structured output retry

Minimum API tests:

- create project
- upload file
- start run
- retrieve run
- retrieve assets
- approve asset
- publish
- graph retrieval

Frontend smoke tests:

- navigation
- upload list rendering
- generate action
- metric rendering
- asset filter
- selected asset drawer/panel
- graph page empty state
- graph node details rendering

---

# 39. Seed Demo Data

Create a small demo dataset for development.

Use generic fictional data.

Example:

```text
supplier_schema.sql
contracts.pdf or a generated text-equivalent fixture
product_catalog.docx or fixture
```

Concepts:

```text
Supplier
Contract
Product
Obligation
Document
```

Sample entities:

```text
ACME Corporation
Contract 1032
Product X
Master Supply Agreement
Payment Obligation
```

This should reproduce the visual examples from screenshots without depending on real client data.

---

# 40. Build Sequence for Codex

Do not attempt to build the entire application in one uncontrolled pass.

Follow these milestones.

---

## Milestone 0 — Inspect and Plan

Before coding:

1. inspect `application_screenshot/`
2. inspect current repository
3. identify screenshot-to-screen mapping
4. identify existing code that can be reused
5. produce a short implementation plan
6. do not modify screenshots

---

## Milestone 1 — Application Skeleton

Build:

- frontend shell
- backend FastAPI shell
- three navigation routes
- header status indicators
- common design tokens
- `.env.example`
- health endpoint
- basic README run instructions

Acceptance:

```text
Frontend loads.
Backend loads.
Build / Graph Assets / Graph Explorer navigation works.
UI visually resembles screenshots.
```

---

## Milestone 2 — Build Screen

Implement:

- knowledge objective
- source upload cards
- uploaded file list
- run configuration
- generate button
- backend project/upload APIs
- local filesystem storage
- SQLite project/source metadata

Use mocked run results initially if needed.

Acceptance:

```text
Files upload successfully.
File list updates.
Project config persists.
Screen matches approved screenshot closely.
```

---

## Milestone 3 — Domain Models and Parsers

Implement:

- Pydantic graph asset models
- DDL/schema parsers
- PDF
- DOCX
- image/OCR fallback
- normalized source representation

Acceptance:

```text
Uploaded sources can be parsed into typed normalized representations.
```

---

## Milestone 4 — LM Studio Provider

Implement:

- provider abstraction
- health check
- standard chat
- structured generation
- embeddings if an embedding model is configured

Acceptance:

```text
Backend can reach LM Studio.
Structured response validates against Pydantic schema.
Model configuration is externalized.
```

---

## Milestone 5 — Knowledge Extraction Tools

Implement:

- concept discovery
- entity extraction
- relationship extraction
- fact extraction
- event extraction
- semantic mapping
- entity resolution

Acceptance:

```text
A small source set produces a valid KnowledgeAssetPackage.
Every accepted extracted asset contains provenance and confidence.
```

---

## Milestone 6 — Agentic Orchestration

Implement:

```text
Deep Agents supervisor
Source Analyst subagent
Knowledge Engineer subagent
Graph Modeller subagent
Quality Reviewer subagent
LangGraph state / run loop
```

Implement at least one re-plan path.

Acceptance:

```text
Different source modality produces different plan/tool usage.
A validation problem can trigger retry/re-plan.
Run events are visible to the UI.
```

---

## Milestone 7 — Graph Assets Screen

Implement:

- metric cards
- asset tabs
- filters
- table
- pagination
- selected asset panel
- evidence view
- approve/review actions
- quality summary

Acceptance:

```text
Generated package is browsable.
Review state persists.
Evidence is inspectable.
UI matches screenshot.
```

---

## Milestone 8 — Neo4j Aura

Implement:

- connection health
- graph store abstraction
- package-to-Neo4j mapping
- safe MERGE publication
- publish-approved-only behavior
- publication history

Acceptance:

```text
Approved package publishes to configured Aura instance.
Re-publishing does not create obvious duplicate canonical nodes.
```

---

## Milestone 9 — Graph Explorer

Implement:

- Cytoscape graph
- search
- node type filter
- relationship filter
- traversal depth
- legend
- node details
- relationships tab
- evidence tab
- graph counts
- optional safe Cypher query panel

Acceptance:

```text
Neo4j graph is visible and interactive.
Selecting a node shows details and provenance.
Filters change displayed graph.
UI matches screenshot.
```

---

## Milestone 10 — POC Polish

Complete:

- loading states
- empty states
- failure states
- responsive laptop layout
- demo fixtures
- automated tests
- setup documentation
- reset-demo command/script

Acceptance:

```text
A new developer can clone, configure LM Studio + Neo4j, run the app, upload sources, generate assets, review, publish and explore the graph.
```

---

# 41. Definition of Done

The POC is complete when the following demo works end-to-end:

```text
1. Start LM Studio local server.
2. Start frontend and backend.
3. App reports LM Studio connected.
4. App reports Neo4j Aura connected.
5. User enters a knowledge objective.
6. User uploads structured schema.
7. User uploads PDF/DOCX/image.
8. User selects Hybrid mode.
9. User clicks Generate Graph Assets.
10. Agent dynamically plans processing.
11. Agent calls modality-specific tools.
12. Agent creates entities, relationships, concepts and facts.
13. Agent performs entity resolution.
14. Quality Reviewer evaluates output.
15. At least one retry/re-plan path is demonstrable.
16. Graph Assets screen shows generated assets.
17. User reviews evidence and confidence.
18. User approves assets.
19. User publishes approved assets.
20. Neo4j Aura contains the graph.
21. Graph Explorer displays the graph using Cytoscape.js.
22. User can select a node and inspect provenance.
```

---

# 42. POC Non-Goals

Do not implement unless specifically requested later:

```text
enterprise SSO
multi-tenant architecture
direct production database connections
CDC
Kafka
Kubernetes
distributed worker clusters
full ontology editor
enterprise governance workflow
complex RBAC
real-time collaboration
full document management
large-scale vector platform
custom model training
billing
enterprise audit platform
```

---

# 43. Coding Principles

Codex must follow these rules:

1. Prefer clear code over abstractions created “for future scale”.
2. Keep domain logic independent of UI and Neo4j.
3. Keep LM Studio behind a model provider abstraction.
4. Keep Neo4j behind a graph store abstraction.
5. Keep knowledge extraction outputs strongly typed.
6. Preserve provenance throughout the pipeline.
7. Never expose hidden chain-of-thought.
8. Use deterministic tools before LLM reasoning when practical.
9. Make retries explicit and bounded.
10. Avoid silent failures.
11. Do not invent missing extracted facts.
12. Separate candidate assets from approved assets.
13. Only approved assets are published by default.
14. Build to the screenshots.
15. Do not add product features not required by this file.

---

# 44. Implementation Behavior Expected from Codex

When asked to implement the application:

1. Read this `CODEX.md`.
2. Inspect `application_screenshot/`.
3. Inspect the existing repository.
4. Reuse working code where appropriate.
5. Build incrementally following the milestones.
6. Run tests after meaningful changes.
7. Fix lint/type/test errors introduced by the implementation.
8. Do not rewrite unrelated code.
9. Do not change the core architecture without explaining the reason.
10. Keep the application runnable after each milestone.
11. Prefer working vertical slices over placeholder architecture.
12. If a library API differs from this document, use the current official API while preserving the architectural intent.

---

# 45. Final Architecture Summary

```text
┌───────────────────────────────────────────────────────┐
│                    React Frontend                     │
│                                                       │
│  Build        Graph Assets        Graph Explorer      │
└──────────────────────────┬────────────────────────────┘
                           │ REST / SSE
                           ▼
┌───────────────────────────────────────────────────────┐
│                    FastAPI Backend                    │
│                                                       │
│ Projects │ Sources │ Runs │ Review │ Graph APIs       │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│          Knowledge Asset Construction Agent           │
│                                                       │
│               Deep Agents Supervisor                  │
│                         │                             │
│        ┌────────────────┼────────────────┐            │
│        ▼                ▼                ▼            │
│ Source Analyst   Knowledge Engineer   Graph Modeller  │
│                         │                             │
│                  Quality Reviewer                     │
│                         │                             │
│              Reactive Re-plan Loop                    │
└──────────────────────────┬────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 Structured Tools   Document Tools      Knowledge Tools
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  LM Studio Local LLM
                           │
                           ▼
                KnowledgeAssetPackage
                           │
                  Review / Approval
                           │
                           ▼
                  Neo4j Graph Publisher
                           │
                           ▼
                     Neo4j Aura
                           │
                           ▼
                 Cytoscape Graph View
```

---

# 46. Most Important Rule

The POC must feel simple to the user even if the backend is intelligent.

The user experience is intentionally:

```text
UPLOAD
   ↓
GENERATE GRAPH ASSETS
   ↓
REVIEW
   ↓
PUBLISH
   ↓
EXPLORE GRAPH
```

Do not expose orchestration complexity unless it provides useful status or explainability.

The intelligence belongs in the backend.

The frontend should remain minimal, polished, and enterprise-ready.
