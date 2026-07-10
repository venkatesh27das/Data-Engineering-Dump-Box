# Deployment

Install the Databricks CLI, authenticate through the approved profile, populate bundle variables without committing secrets, then run `databricks bundle validate -t dev`, `databricks bundle deploy -t dev`, and the App start command supported by the installed CLI.

Create governed catalog/configuration/Bronze/operations schemas, raw UC Volume, Delta operational tables, service principal/managed identity, App resource bindings, Workflow job, optional ADF pipeline, approved model/parser endpoints, secret scopes, and MLflow experiment. Grant source read/list separately from landing/Bronze writes and activation.
