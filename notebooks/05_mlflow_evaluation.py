# Databricks notebook source
import mlflow

evaluation_dimensions = [
    "readiness_status_accuracy",
    "tool_selection_correctness",
    "configuration_validity_accuracy",
    "recommendation_quality",
]
with mlflow.start_run(run_name="source-readiness-evaluation"):
    mlflow.log_dict({"dimensions": evaluation_dimensions, "note": "Bind a reviewed synthetic evaluation dataset."}, "evaluation_plan.json")
