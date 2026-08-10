# Knowledge Graph Builder - Synthetic Test Pack

This folder contains synthetic procurement-domain fixtures for testing the Knowledge Graph Builder POC.

## Recommended knowledge objective

`Understand suppliers, contracts, products and contractual obligations.`

## Files

### Structured
- `supplier_schema.sql` - DDL with suppliers, products, contracts, contract-products and obligations.
- `schema_metadata.csv` - tabular schema metadata and business descriptions.
- `schema_context.json` - schema/domain context with a few representative semantic examples.
- `supplier_sample.csv` - optional tiny sample dataset for alias/entity-resolution testing.

### Unstructured
- `contract_1032.pdf` - two-page Master Supply Agreement.
- `product_catalog.docx` - catalog that deliberately uses supplier aliases.
- `purchase_order_77821.png` - image fixture for OCR/image processing.

### Validation
- `expected_graph_assets.json` - expected canonical entities, key relationships, contextual facts and quality behaviors.

## Test scenarios

### Scenario A - Structured only
Upload:
- supplier_schema.sql
- schema_metadata.csv
- schema_context.json

Expected:
- Supplier, Product, Contract and Obligation concepts.
- Explicit PK/FK relationships.
- Candidate canonical entities from supplied semantic examples.
- No OCR/document tools should run.

### Scenario B - Unstructured only
Upload:
- contract_1032.pdf
- product_catalog.docx
- purchase_order_77821.png

Expected:
- Parse PDF and DOCX.
- OCR/read the image.
- Extract ACME Corporation, Product X, Product Z, Master Supply Agreement and PO-77821.
- Resolve aliases ACME, ACME Co. and ACME Corporation.
- Extract Net 30, 15-business-day delivery requirement, USD 125 price and quarterly reporting obligation.
- Preserve file/page/section evidence where possible.

### Scenario C - Hybrid
Upload all files.

Expected:
- Structured schema and document paths both execute.
- SUP-001 / ACME Corp / ACME Co. / ACME / ACME Corporation resolve to one canonical Supplier.
- PRD-X and PRD-Z connect to the contract and supplier.
- Cross-source evidence is attached to canonical entities and relationships.
- Graph package contains source, entity, relationship, semantic and contextual assets.

## Useful quality checks

1. No duplicate ACME supplier nodes after resolution.
2. All important relationships have at least one evidence reference.
3. Foreign-key relationships are recognized without relying entirely on an LLM.
4. The image fixture triggers image/OCR processing.
5. Re-running publication should not duplicate canonical Neo4j nodes.
6. The application should show low-confidence/review status rather than silently inventing unsupported facts.

## Important

All names and content are synthetic and created only for application testing.
