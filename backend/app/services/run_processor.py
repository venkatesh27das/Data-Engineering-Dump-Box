import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from app.agents.runtime import AgentRuntime
from app.llm.model_registry import ModelRegistry
from app.processing.extractor import extract_workbook
from app.processing.package_writer import build_embedding_chunks, write_package
from app.storage.database import Database, now_iso
from app.storage.local_store import LocalStore

STAGES = [
    ("profiling", 12, "Inspecting workbook structure and safety metadata"),
    ("planning", 25, "Selecting the deterministic processing path"),
    ("extracting", 48, "Extracting sheets, regions, tables, formulas, and visuals"),
    ("interpreting", 67, "Creating contextual semantic assets and relationships"),
    ("validating", 82, "Validating provenance, lineage, and quality"),
    ("packaging", 94, "Writing the canonical knowledge package"),
]


class RunProcessor:
    def __init__(
        self,
        database: Database,
        store: LocalStore,
        models: ModelRegistry,
        agent_runtime: AgentRuntime,
    ):
        self.database = database
        self.store = store
        self.models = models
        self.agent_runtime = agent_runtime
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="workbook-run")
        self.cancelled: set[str] = set()
        self.lock = threading.Lock()

    def submit(self, run_id: str, directives: list[dict] | None = None) -> None:
        self.executor.submit(self._process, run_id, directives or [])

    def cancel(self, run_id: str) -> None:
        with self.lock:
            self.cancelled.add(run_id)

    def _is_cancelled(self, run_id: str) -> bool:
        with self.lock:
            return run_id in self.cancelled

    def _event(
        self, run_id: str, stage: str, status: str, progress: int, message: str, details: dict | None = None
    ) -> None:
        timestamp = now_iso()
        self.database.update_run(run_id, status=status, current_stage=stage, progress_percent=progress)
        self.database.add_event(
            {
                "event_id": f"evt_{uuid4().hex[:14]}",
                "run_id": run_id,
                "timestamp": timestamp,
                "stage": stage,
                "status": status,
                "progress_percent": progress,
                "message": message,
                "details": details or {},
            }
        )

    def _detail_event(
        self, run_id: str, stage: str, progress: int, message: str, details: dict
    ) -> None:
        self.database.add_event(
            {
                "event_id": f"evt_{uuid4().hex[:14]}",
                "run_id": run_id,
                "timestamp": now_iso(),
                "stage": stage,
                "status": stage,
                "progress_percent": progress,
                "message": message,
                "details": details,
            }
        )

    def _process(self, run_id: str, directives: list[dict]) -> None:
        started = time.monotonic()
        try:
            run = self.database.get_run(run_id)
            if not run:
                return
            workbook = self.database.get_workbook(run["workbook_id"])
            if not workbook:
                return
            result = None
            embeddings: list[dict] = []
            for stage, progress, message in STAGES:
                if self._is_cancelled(run_id):
                    self._finish_cancelled(run_id, started)
                    return
                self._event(run_id, stage, stage, progress, message)
                if stage == "extracting":
                    model_status = self.models.status()
                    result = extract_workbook(
                        Path(workbook["storage_uri"]),
                        workbook["id"],
                        run_id,
                        model_status["reachable"],
                        directives,
                    )
                    result.manifest["purpose"] = workbook.get("purpose", "")
                    result.manifest["applied_directives"] = directives
                    self._detail_event(
                        run_id,
                        stage,
                        progress,
                        "Deterministic workbook extraction completed",
                        {
                            "sheets": len(result.sheets),
                            "tables": len(result.tables),
                            "formulas": len(result.formulas),
                            "images": len(result.images),
                            "charts": len(result.charts),
                            "forms": len(result.forms),
                            "connections": len(result.connections),
                            "queries": len(result.queries),
                        },
                    )
                elif stage == "interpreting" and result:
                    agent_report = self.agent_runtime.enrich(result)
                    self.database.add_event(
                        {
                            "event_id": f"evt_{uuid4().hex[:14]}",
                            "run_id": run_id,
                            "timestamp": now_iso(),
                            "stage": "interpreting",
                            "status": "interpreting",
                            "progress_percent": progress,
                            "message": "Local specialist agents completed semantic interpretation",
                            "details": agent_report,
                        }
                    )
                elif stage == "validating" and result:
                    chunks = build_embedding_chunks(result)
                    try:
                        embeddings = self.agent_runtime.create_embeddings(chunks)
                        embedded_ids = {item["source_unit_id"] for item in embeddings}
                        for unit in result.units:
                            unit["embedding_status"] = (
                                "completed" if unit["unit_id"] in embedded_ids else "not_generated"
                            )
                        result.manifest["embedding_status"] = {
                            "status": "completed" if embeddings else "not_generated",
                            "vector_count": len(embeddings),
                            "chunk_count": len(chunks),
                        }
                    except Exception as error:
                        result.manifest["embedding_status"] = {
                            "status": "degraded",
                            "vector_count": 0,
                            "error": str(error),
                        }
                    self._detail_event(
                        run_id,
                        stage,
                        progress,
                        "Validation and embedding preparation completed",
                        {
                            "semantic_units": len(result.units),
                            "graph_nodes": len(result.nodes),
                            "graph_edges": len(result.edges),
                            "review_items": len(result.reviews),
                            "embedding_status": result.manifest["embedding_status"],
                        },
                    )
                elif stage == "packaging" and result:
                    run_root = self.store.run_path(workbook["id"], run_id)
                    (run_root / "intermediate").mkdir(exist_ok=True)
                    (run_root / "intermediate" / "processing_plan.json").write_text(
                        json.dumps(
                            {
                                "workbook_archetype": result.manifest.get("complexity", {}).get(
                                    "archetype", "unknown"
                                ),
                                "steps": [item[0] for item in STAGES],
                                "excluded_steps": ["macro_execution"],
                                "reasoning_summary": result.manifest.get("processing_plan", {}).get(
                                    "reasoning_summary",
                                    "Deterministic evidence selected the workbook processing path.",
                                ),
                                "agent_runtime": result.manifest.get("agent_runtime", {}),
                                "applied_directives": directives,
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    archive = write_package(result, run_root, embeddings)
                    for asset in result.assets:
                        asset["content_uri"] = str(archive)
                    self.database.replace_assets(run_id, workbook["id"], result.assets)
                    self.database.replace_reviews(run_id, result.reviews)
                    self._detail_event(
                        run_id,
                        stage,
                        progress,
                        "Knowledge package indexed and ready for delivery",
                        {
                            "indexed_assets": len(result.assets),
                            "review_items": len(result.reviews),
                            "embedding_vectors": len(embeddings),
                            "package_created": archive.is_file(),
                        },
                    )
                time.sleep(0.08)
            if not result:
                raise RuntimeError("Extraction produced no result")
            confidence_values = [asset["confidence"] for asset in result.assets] or [0.75]
            confidence = sum(confidence_values) / len(confidence_values)
            if result.manifest.get("semantic_mode") == "deterministic_fallback":
                confidence = max(0.0, confidence - 0.04)
            final_status = "needs_review" if result.reviews else "completed"
            duration = time.monotonic() - started
            count = len(result.assets) + len(result.units) + len(result.nodes) + len(result.edges)
            self.database.update_run(
                run_id,
                status=final_status,
                current_stage="complete",
                progress_percent=100,
                completed_at=now_iso(),
                duration_seconds=duration,
                overall_confidence=round(confidence, 3),
                output_unit_count=count,
            )
            self.database.add_event(
                {
                    "event_id": f"evt_{uuid4().hex[:14]}",
                    "run_id": run_id,
                    "timestamp": now_iso(),
                    "stage": "complete",
                    "status": final_status,
                    "progress_percent": 100,
                    "message": "Workbook knowledge package created",
                    "details": {"output_units": count, "review_items": len(result.reviews)},
                }
            )
        except Exception as error:
            duration = time.monotonic() - started
            self.database.update_run(
                run_id,
                status="failed",
                current_stage="failed",
                completed_at=now_iso(),
                duration_seconds=duration,
                error_code="PARSER_FAILURE",
                error_message=str(error),
            )
            self.database.add_event(
                {
                    "event_id": f"evt_{uuid4().hex[:14]}",
                    "run_id": run_id,
                    "timestamp": now_iso(),
                    "stage": "failed",
                    "status": "failed",
                    "progress_percent": 100,
                    "message": "Workbook processing failed",
                    "details": {"error_code": "PARSER_FAILURE"},
                }
            )

    def _finish_cancelled(self, run_id: str, started: float) -> None:
        self.database.update_run(
            run_id,
            status="cancelled",
            current_stage="cancelled",
            completed_at=now_iso(),
            duration_seconds=time.monotonic() - started,
        )
        self.database.add_event(
            {
                "event_id": f"evt_{uuid4().hex[:14]}",
                "run_id": run_id,
                "timestamp": now_iso(),
                "stage": "cancelled",
                "status": "cancelled",
                "progress_percent": 100,
                "message": "Processing cancelled",
                "details": {},
            }
        )
