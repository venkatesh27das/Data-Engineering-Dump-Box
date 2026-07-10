# Deployment

Install the Databricks CLI, authenticate with a profile or workload identity, validate `databricks.yml`, and bind the production app to least-privilege catalog/schema, workflow, serving endpoint, and secret resources. Run `databricks bundle validate -t dev`, `databricks bundle deploy -t dev`, then `databricks apps deploy processing-quality-agent-dev --source-code-path .` if the workspace CLI version requires an explicit app deploy.

The sample bundle intentionally omits organization-specific hosts, IDs, principals, warehouse IDs, and permissions.
