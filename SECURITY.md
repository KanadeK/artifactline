# Security policy

## Supported versions

Security fixes are provided for the latest tagged release.

## Reporting a vulnerability

Please use the repository's **Security > Report a vulnerability** form so the
report and any proof of concept remain private. Do not open a public issue for
an unpatched vulnerability.

Include the affected version, operating system, workflow input, observed
impact, and a minimal reproduction. Reports about malicious workflow YAML are
especially useful when they show unintended execution, network access, file
access beyond the selected workflow inputs, or terminal-control output.

Artifactline intentionally reads local workflow files selected by the caller.
It does not execute workflow commands, evaluate expressions, fetch actions, or
contact GitHub during analysis.
