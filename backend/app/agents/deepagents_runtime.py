import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from PIL import Image, ImageDraw
from pydantic import BaseModel

from app.agents.schemas import (
    ChartInterpretation,
    FeedbackInterpretation,
    OCRExtraction,
    ProcessingPlan,
    SemanticInterpretation,
    ValidationSummary,
    VisualInterpretation,
)
from app.core.config import Settings
from app.llm.lmstudio_client import LMStudioClient, LMStudioError
from app.llm.model_registry import ModelRegistry
from app.processing.extractor import ExtractionResult

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class DeepAgentsRuntime:
    """Deep Agents adapter with direct structured-output recovery for local models."""

    framework_name = "langchain_deep_agents"

    def __init__(self, settings: Settings, models: ModelRegistry, client: LMStudioClient):
        self.settings = settings
        self.models = models
        self.client = client

    def enrich(self, result: ExtractionResult) -> dict[str, Any]:
        status = self.models.status()
        reasoning_model = status.get("reasoning_model", "")
        report: dict[str, Any] = {
            "framework": self.framework_name,
            "reasoning_model": reasoning_model,
            "vision_model": status.get("vision_model", ""),
            "agents": {},
        }
        if not status["reachable"] or not reasoning_model:
            result.manifest["semantic_mode"] = "deterministic_fallback"
            report["agents"]["supervisor"] = "offline_fallback"
            result.manifest["agent_runtime"] = report
            return report

        metadata = self._compact_metadata(result)
        try:
            plan, mode = self._invoke(
                "supervisor",
                ProcessingPlan,
                "Plan the interpretation of supplied workbook metadata. Use only supplied facts. "
                "Do not request or access files and do not use tools.",
                metadata,
                use_deep_agent=True,
            )
            result.manifest["processing_plan"] = plan.model_dump()
            report["agents"]["supervisor"] = mode
        except LMStudioError as error:
            report["agents"]["supervisor"] = f"degraded: {error}"

        try:
            interpretation, mode = self._invoke(
                "semantic_agent",
                SemanticInterpretation,
                "Interpret supplied workbook metadata into a concise business summary and candidate "
                "entities/relationships. Do not invent cell values. Every candidate needs evidence and "
                "confidence. Do not request or access files and do not use tools.",
                metadata,
            )
            self._apply_semantics(result, interpretation)
            report["agents"]["semantic_agent"] = mode
        except LMStudioError as error:
            report["agents"]["semantic_agent"] = f"degraded: {error}"

        self._interpret_visuals(result, report, status.get("vision_model", ""))
        self._interpret_charts(result, report)

        try:
            validation_input = json.dumps(
                {
                    "metadata": json.loads(metadata),
                    "semantic_analysis": result.manifest.get("semantic_analysis", {}),
                    "deterministic_review_count": len(result.reviews),
                },
                default=str,
            )
            validation, mode = self._invoke(
                "validation_agent",
                ValidationSummary,
                "Review supplied extraction and interpretation metadata for unsupported claims, missing "
                "provenance, or low-confidence mappings. Do not request or access files or use tools.",
                validation_input,
            )
            result.manifest["agent_validation"] = validation.model_dump()
            report["agents"]["validation_agent"] = mode
            if validation.status == "review_recommended" and validation.findings:
                result.reviews.append(
                    self._review(
                        "agent_validation",
                        "Review semantic validation findings",
                        "; ".join(validation.findings[:5]),
                        validation.confidence,
                    )
                )
        except LMStudioError as error:
            report["agents"]["validation_agent"] = f"degraded: {error}"

        successful = any(value in {"deep_agent", "structured_adapter"} for value in report["agents"].values())
        result.manifest["semantic_mode"] = "local_model" if successful else "deterministic_fallback"
        result.manifest["agent_runtime"] = report
        return report

    def create_embeddings(self, chunks: list[dict]) -> list[dict]:
        status = self.models.status()
        model = status.get("embedding_model", "")
        if not self.settings.enable_embeddings or not status["reachable"] or not model:
            return []
        selected = chunks[: self.settings.embedding_max_chunks]
        records: list[dict[str, Any]] = []
        for offset in range(0, len(selected), self.settings.embedding_batch_size):
            batch = selected[offset : offset + self.settings.embedding_batch_size]
            vectors = self.client.embeddings(model, [item["embedding_text"] for item in batch])
            for item, vector in zip(batch, vectors, strict=True):
                records.append(
                    {
                        "chunk_id": item["chunk_id"],
                        "source_unit_id": item["source_unit_id"],
                        "model": model,
                        "dimensions": len(vector),
                        "vector": vector,
                    }
                )
        return records

    def interpret_feedback(self, text: str) -> FeedbackInterpretation:
        payload = json.dumps({"feedback": text}, ensure_ascii=False)
        result, _ = self._invoke(
            "feedback_agent",
            FeedbackInterpretation,
            "Convert user workbook-processing feedback into executable directives. Allowed types are "
            "override_header_row, exclude_sheet, confirm_semantic_mapping, and set_business_context. "
            "Preserve explicit sheet and field names. Never create an empty directive list. "
            "Do not use tools.",
            payload,
        )
        return result

    def probe(self) -> dict[str, Any]:
        status = self.models.status()
        checks: dict[str, Any] = {}
        reasoning = status.get("reasoning_model", "")
        embedding = status.get("embedding_model", "")
        if status["reachable"] and reasoning:
            try:
                response = self.client.structured_chat(
                    reasoning,
                    ValidationSummary,
                    "Return a capability check result.",
                    "Mark this local structured-output check as passed with no findings and confidence 1.",
                    max_tokens=180,
                )
                checks["reasoning"] = {
                    "status": "ready",
                    "model": reasoning,
                    "structured_output": response.status == "passed",
                }
            except LMStudioError as error:
                checks["reasoning"] = {"status": "failed", "model": reasoning, "error": str(error)}
        else:
            checks["reasoning"] = {"status": "unavailable", "model": reasoning}
        if status["reachable"] and embedding and self.settings.enable_embeddings:
            try:
                vector = self.client.embeddings(embedding, ["Workbook Agent capability check"])[0]
                checks["embedding"] = {
                    "status": "ready",
                    "model": embedding,
                    "dimensions": len(vector),
                }
            except (LMStudioError, IndexError) as error:
                checks["embedding"] = {"status": "failed", "model": embedding, "error": str(error)}
        else:
            checks["embedding"] = {"status": "unavailable", "model": embedding}
        vision = status.get("vision_model", "")
        if status["reachable"] and vision and self.settings.enable_vision:
            try:
                image = Image.new("RGB", (96, 64), "white")
                draw = ImageDraw.Draw(image)
                draw.rectangle((8, 8, 88, 56), fill="#e6f6ed", outline="#0b9954", width=3)
                draw.text((22, 24), "DATA", fill="#122033")
                output = BytesIO()
                image.save(output, format="PNG")
                visual = self.client.structured_chat(
                    vision,
                    VisualInterpretation,
                    "Describe only visible evidence in the supplied test image.",
                    "Classify this local capability-check image.",
                    image=(output.getvalue(), "image/png"),
                    max_tokens=240,
                )
                checks["vision"] = {
                    "status": "ready",
                    "model": vision,
                    "classification": visual.classification,
                    "confidence": visual.confidence,
                }
            except LMStudioError as error:
                checks["vision"] = {"status": "failed", "model": vision, "error": str(error)}
        else:
            checks["vision"] = {"status": "unavailable", "model": vision}
        return {**status, "framework": self.framework_name, "checks": checks}

    def _invoke(
        self,
        agent_name: str,
        schema: type[SchemaT],
        system_prompt: str,
        payload: str,
        *,
        use_deep_agent: bool = False,
    ) -> tuple[SchemaT, str]:
        model_name = self.models.status().get("reasoning_model", "")
        if not model_name:
            raise LMStudioError("No reasoning model is available")
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        prompt = (
            f"Input metadata:\n{payload}\n\nReturn JSON only. It must match this schema exactly:\n"
            f"{schema_text}"
        )
        if use_deep_agent:
            try:
                return self._invoke_with_deep_agent(agent_name, model_name, schema, system_prompt, prompt)
            except Exception:
                pass
        try:
            direct = self.client.structured_chat(
                model_name,
                schema,
                system_prompt,
                payload,
            )
            return direct, "structured_adapter"
        except LMStudioError:
            raise
        except Exception as error:
            raise LMStudioError(f"{agent_name} failed: {error}") from error

    def _invoke_with_deep_agent(
        self,
        agent_name: str,
        model_name: str,
        schema: type[SchemaT],
        system_prompt: str,
        prompt: str,
    ) -> tuple[SchemaT, str]:
        try:
            model = ChatOpenAI(
                model=model_name,
                base_url=self.settings.lm_studio_base_url,
                api_key=self.settings.lm_studio_api_key,
                temperature=0.1,
                max_tokens=700,
                reasoning_effort="none",
                timeout=min(self.settings.llm_request_timeout_seconds, 30),
                max_retries=0,
            )
            agent = create_deep_agent(
                model=model,
                tools=[],
                system_prompt=system_prompt,
                name=agent_name,
            )
            response = agent.invoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"recursion_limit": 6},
            )
            raw = response["messages"][-1].content
            if isinstance(raw, list):
                raw = "".join(block.get("text", "") for block in raw if isinstance(block, dict))
            return schema.model_validate(LMStudioClient._json_value(raw)), "deep_agent"
        except Exception as error:
            raise LMStudioError(f"Deep agent {agent_name} failed: {error}") from error

    def _interpret_visuals(self, result: ExtractionResult, report: dict[str, Any], vision_model: str) -> None:
        if not result.media:
            report["agents"]["visual_agent"] = "not_needed"
            return
        if not self.settings.enable_vision or not vision_model:
            report["agents"]["visual_agent"] = "unavailable"
            return
        interpreted = 0
        failures = 0
        media_by_name = dict(result.media)
        for image in result.images[: self.settings.vision_max_images]:
            filename = image.get("media_file", "")
            binary = media_by_name.get(filename)
            if not binary:
                continue
            suffix = Path(filename).suffix.lower().lstrip("/").lstrip(".") or "png"
            media_type = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
            try:
                visual = self.client.structured_chat(
                    vision_model,
                    VisualInterpretation,
                    "Interpret an image extracted from a spreadsheet. Describe only visible evidence. "
                    "Put every visible text string verbatim in extracted_text, even when that text is "
                    "also mentioned in the description.",
                    json.dumps(
                        {
                            "sheet_name": image.get("sheet_name"),
                            "anchor_cell": image.get("anchor_cell"),
                            "dimensions": [image.get("width"), image.get("height")],
                        }
                    ),
                    image=(binary, media_type),
                    max_tokens=900,
                )
                if (
                    not visual.extracted_text
                    and self.settings.enable_ocr
                    and interpreted < self.settings.ocr_max_images
                ):
                    try:
                        ocr = self.client.structured_chat(
                            vision_model,
                            OCRExtraction,
                            "Act only as OCR. Transcribe all visible text exactly into full_text. "
                            "Do not describe or interpret the image.",
                            json.dumps(
                                {
                                    "sheet_name": image.get("sheet_name"),
                                    "anchor_cell": image.get("anchor_cell"),
                                }
                            ),
                            image=(binary, media_type),
                            max_tokens=600,
                        )
                        visual.extracted_text = [
                            line.strip()
                            for line in ocr.full_text.splitlines()
                            if line.strip()
                        ]
                    except LMStudioError:
                        pass
                image.update(visual.model_dump())
                image["ocr"] = {
                    "provider": "local_vision_model",
                    "model": vision_model,
                    "text": visual.extracted_text,
                    "status": "completed" if visual.extracted_text else "no_text_detected",
                }
                for asset in result.assets:
                    if asset["id"] == image["image_id"]:
                        asset["summary"] = visual.description
                        asset["confidence"] = visual.confidence
                        asset["review_status"] = "open" if visual.confidence < 0.7 else "not_required"
                interpreted += 1
                if visual.confidence < 0.7:
                    result.reviews.append(
                        self._review(
                            image["image_id"],
                            "Confirm visual interpretation",
                            visual.description,
                            visual.confidence,
                        )
                    )
            except LMStudioError:
                failures += 1
        report["agents"]["visual_agent"] = (
            f"interpreted:{interpreted}" if interpreted else f"degraded:{failures}_failed"
        )

    def _interpret_charts(self, result: ExtractionResult, report: dict[str, Any]) -> None:
        if not result.charts:
            report["agents"]["chart_agent"] = "not_needed"
            return
        model = self.models.status().get("reasoning_model", "")
        if not model:
            report["agents"]["chart_agent"] = "unavailable"
            return
        completed = 0
        failed = 0
        for chart in result.charts[: self.settings.chart_max_items]:
            try:
                interpretation = self.client.structured_chat(
                    model,
                    ChartInterpretation,
                    "Interpret spreadsheet chart metadata. Use only supplied titles, series, ranges, "
                    "and axes. Do not claim trends when cell values were not supplied.",
                    json.dumps(chart, ensure_ascii=False, default=str),
                    max_tokens=650,
                )
                chart["summary"] = interpretation.summary
                chart["insights"] = interpretation.insights
                chart["business_purpose"] = interpretation.business_purpose
                chart["confidence"] = interpretation.confidence
                chart["interpretation_method"] = "local_chart_agent"
                for asset in result.assets:
                    if asset["id"] == chart["chart_id"]:
                        asset["summary"] = interpretation.summary
                        asset["confidence"] = interpretation.confidence
                        asset["review_status"] = "open" if interpretation.confidence < 0.7 else "not_required"
                completed += 1
            except LMStudioError:
                failed += 1
        report["agents"]["chart_agent"] = (
            f"interpreted:{completed}" if completed else f"degraded:{failed}_failed"
        )

    @staticmethod
    def _compact_metadata(result: ExtractionResult) -> str:
        tables = []
        for table in result.tables[:30]:
            rows = result.table_rows.get(table["table_id"], [])
            tables.append(
                {
                    "table_id": table["table_id"],
                    "name": table["name"],
                    "sheet": next(
                        (s["name"] for s in result.sheets if s["sheet_id"] == table["sheet_id"]),
                        None,
                    ),
                    "source_range": table["source_range"],
                    "headers": table["normalized_headers"][:30],
                    "row_count": table["row_count"],
                    "sample_rows": [
                        {key: value for key, value in row.items() if not key.startswith("_")}
                        for row in rows[:2]
                    ],
                }
            )
        payload = {
            "source_file": result.manifest.get("source_file"),
            "purpose": result.manifest.get("purpose", "knowledge extraction"),
            "complexity": result.manifest.get("complexity", {}),
            "sheets": result.sheets[:40],
            "tables": tables,
            "formulas": result.formulas[:80],
            "named_ranges": result.named_ranges[:40],
            "charts": result.charts[:30],
            "images": result.images[:30],
            "comments": result.comments[:40],
            "forms": result.forms[:20],
            "pivots": result.pivots[:20],
            "connections": result.connections[:20],
            "queries": result.queries[:20],
            "external_links": result.external_links[:20],
            "conditional_formats": result.conditional_formats[:30],
            "data_validations": result.data_validations[:30],
            "directives": result.manifest.get("applied_directives", []),
        }
        return json.dumps(payload, ensure_ascii=False, default=str)[: DeepAgentsRuntime.MAX_PROMPT_CHARS]

    MAX_PROMPT_CHARS = 36_000

    def _apply_semantics(self, result: ExtractionResult, interpretation: SemanticInterpretation) -> None:
        result.manifest["semantic_analysis"] = interpretation.model_dump()
        result.manifest["summary"] = interpretation.summary
        for unit in result.units:
            unit["semantic_context"]["domain"] = interpretation.domain
            unit["semantic_context"]["business_terms"] = interpretation.business_terms[:20]
            unit["quality"]["semantic_confidence"] = interpretation.confidence
        summary_id = f"{result.manifest['workbook_id']}.semantic_summary"
        result.assets.append(
            {
                "id": summary_id,
                "asset_type": "semantic_summary",
                "title": "AI workbook summary",
                "summary": interpretation.summary,
                "source_uri": f"workbook://{result.manifest['source_file']}",
                "content_uri": "",
                "source_sheet": None,
                "source_range": None,
                "confidence": interpretation.confidence,
                "review_status": "open" if interpretation.confidence < 0.7 else "not_required",
            }
        )
        labels: dict[str, str] = {}
        for entity in interpretation.entities:
            node_id = f"entity.{uuid4().hex[:12]}"
            labels[entity.label.casefold()] = node_id
            result.nodes.append(
                {
                    "node_id": node_id,
                    "node_type": "entity_candidate",
                    "label": entity.label,
                    "entity_type": entity.entity_type,
                    "evidence": entity.evidence,
                    "confidence": entity.confidence,
                    "provenance": {
                        "source_sheet": entity.source_sheet,
                        "source_range": entity.source_range,
                        "method": "semantic_agent",
                    },
                }
            )
            result.assets.append(
                {
                    "id": node_id,
                    "asset_type": "entity_candidate",
                    "title": entity.label,
                    "summary": f"{entity.entity_type}: {entity.evidence}",
                    "source_uri": (
                        f"workbook://{entity.source_sheet or 'workbook'}/{entity.source_range or ''}"
                    ),
                    "content_uri": "",
                    "source_sheet": entity.source_sheet,
                    "source_range": entity.source_range,
                    "confidence": entity.confidence,
                    "review_status": "open" if entity.confidence < 0.7 else "not_required",
                }
            )
        for relation in interpretation.relationships:
            relation_type = re.sub(r"[^A-Z0-9]+", "_", relation.relationship_type.upper()).strip("_")
            edge_id = f"edge.{uuid4().hex[:12]}"
            result.edges.append(
                {
                    "edge_id": edge_id,
                    "source_id": labels.get(relation.source.casefold(), relation.source),
                    "relationship_type": relation_type or "RELATED_TO",
                    "target_id": labels.get(relation.target.casefold(), relation.target),
                    "relationship_description": relation.evidence,
                    "evidence": [relation.evidence],
                    "confidence": relation.confidence,
                    "provenance": {
                        "source_sheet": relation.source_sheet,
                        "source_range": relation.source_range,
                        "method": "semantic_agent",
                    },
                }
            )
            result.assets.append(
                {
                    "id": edge_id,
                    "asset_type": "relationship_candidate",
                    "title": f"{relation.source} {relation_type or 'RELATED_TO'} {relation.target}",
                    "summary": relation.evidence,
                    "source_uri": (
                        f"workbook://{relation.source_sheet or 'workbook'}/{relation.source_range or ''}"
                    ),
                    "content_uri": "",
                    "source_sheet": relation.source_sheet,
                    "source_range": relation.source_range,
                    "confidence": relation.confidence,
                    "review_status": "open" if relation.confidence < 0.7 else "not_required",
                }
            )

    @staticmethod
    def _review(asset_id: str, title: str, description: str, confidence: float) -> dict[str, Any]:
        return {
            "id": f"review.{uuid4().hex[:12]}",
            "asset_id": asset_id,
            "review_type": "agent_review",
            "title": title,
            "description": description,
            "evidence": "Local model interpretation",
            "suggested_action": "Confirm or correct this interpretation before accepting the run.",
            "confidence": confidence,
            "severity": "medium" if confidence < 0.7 else "low",
        }
