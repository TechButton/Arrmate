# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | ✅        |

Arrmate is self-hosted software in active development. Security fixes are applied
to the current `main` branch only. We recommend always running the latest image.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately via GitHub's
[Security Advisories](../../security/advisories/new) feature
(Repository → Security → Advisories → "Report a vulnerability").

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept or sample config)
- Any suggested mitigations you have identified

### What to expect

| Timeline | Action |
|----------|--------|
| 3 business days | Acknowledgement of your report |
| 14 days | Initial assessment and triage |
| 90 days | Target remediation and public disclosure |

We will credit reporters who responsibly disclose vulnerabilities in the
release notes, unless you prefer to remain anonymous.

## Scope

The following are **in scope**:
- The Arrmate API and web interface
- Authentication and session management
- Docker container configuration
- Integration with external services (Sonarr, Radarr, etc.)

The following are **out of scope**:
- Vulnerabilities in upstream services (Sonarr, Radarr, Plex, Ollama, etc.)
- Issues requiring physical access to the host machine
- Social engineering attacks

## Security Hardening Recommendations

For production deployments:

1. **Put Arrmate behind a reverse proxy** (nginx, Caddy, Traefik) with TLS — the
   application itself does not terminate HTTPS.
2. **Restrict network access** — expose Arrmate only to trusted networks or VPN.
3. **Do not expose Ollama externally** — the Ollama API has no authentication;
   keep it internal to your Docker network.
4. **Set `TRANSCODE_ALLOWED_ROOTS`** — limit ffmpeg to your media directories only.
5. **Use strong, unique passwords** — change the default admin credentials
   immediately after first login.
6. **Rotate API tokens** regularly and revoke unused ones at `/web/api-tokens`.
