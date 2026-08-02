# Security policy

## Supported versions

Security fixes are made on the current 0.2.0 development line; older snapshots
are not supported. Version 0.2.0 remains alpha software with an unstable public
API.

## Reporting a vulnerability

Do not open a public issue containing an exploitable vulnerability, private
study material, credentials, or provider payloads. Use GitHub's private
vulnerability-reporting feature when it is available for this repository. If it
is not available, open a public issue that asks the maintainers to enable a
private reporting channel, without including sensitive details.

Include the affected version or commit, the smallest safe reproduction, impact,
and any suggested mitigation. Do not use real student data or active
credentials in a reproduction.

## Scope notes

The reference CLI stores canonical events and source blobs locally. Its exports
are intentionally allowlisted, but users should still inspect bundles before
sharing them. Model credentials belong only in environment variables; never put
credential values in repository configuration, fixtures, logs, or reports.
