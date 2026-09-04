# Security Policy

## Supported version

Security fixes are applied to the latest revision of the `main` branch.

## Reporting a vulnerability

Do not include credentials, connection strings, server names, query results, or other operational data in a public issue.

If private vulnerability reporting is available in the repository Security tab, use that channel. Otherwise, open a public issue containing only a request for a private reporting channel and no sensitive technical details.

## Operational guidance

- Use a dedicated SQL Server account with the minimum permissions required by the selected diagnostics.
- Prefer Windows Authentication where the environment supports it.
- Use a trusted SQL Server TLS certificate.
- Do not package or publish `connection_config.json` or `user_queries.json`.
- Review saved custom queries before sharing an application directory.
