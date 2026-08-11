# End-to-end demo runbook

The canonical synthetic fixture pack is in `test/knowledge_graph_test_pack`. Its companies, contracts, products, and obligations are fictional.

## Build

1. Confirm the selected model provider and Neo4j show `Connected` in the application header.
2. On **Build**, use the objective: `Understand suppliers, contracts, products and contractual obligations.`
3. Upload these structured fixtures:
   - `supplier_schema.sql`
   - `schema_metadata.csv`
   - `schema_context.json`
   - `supplier_sample.csv`
4. Upload these unstructured fixtures:
   - `contract_1032.pdf`
   - `product_catalog.docx`
   - `purchase_order_77821.png`
5. Select **Hybrid**, **Contextual Knowledge**, and enable low-confidence review.
6. Click **Start Run**, then open **Run Queue** to watch the plan, specialist tools, quality stage, intermediate assets, lineage, and any re-plan event.

## Review and publish

1. Open **Graph Assets** after the run completes.
2. Inspect evidence and confidence for entities and relationships.
3. Confirm ACME aliases resolve to one canonical supplier rather than duplicate suppliers.
4. Approve the assets needed for the graph. Publication intentionally skips pending, review, or rejected assets.
5. Click **Publish Approved Assets to Neo4j**.
6. Publish a second time and confirm the result is idempotent rather than creating duplicate nodes.

## Explore

1. Open **Graph Explorer**.
2. Search for `ACME`, filter node and relationship types, and change traversal depth.
3. Select a node and inspect Overview, Properties, Relationships, and Evidence.
4. Run one of the provided read-only Cypher templates.

Expected fixture behaviors are documented in `test/knowledge_graph_test_pack/README_TEST_PACK.md` and `expected_graph_assets.json`.

## Reset the demo

Stop the API before resetting. From the repository root:

```bash
make reset-demo
```

The command first lists every local table count and managed file, then requires the exact confirmation `reset-demo`. It preserves configuration, `.env`, the fixture pack, SQLite itself, and `.gitkeep` placeholders.

The default reset does not touch Neo4j. To also remove only the graph nodes belonging to a known demo project:

```bash
cd backend
uv run python -m scripts.reset_demo --neo4j-project-id PROJECT_UUID
```

This performs a read-only count first and requires the same confirmation. It only deletes `KnowledgeAsset` nodes whose `project_id` exactly matches the supplied UUID.
