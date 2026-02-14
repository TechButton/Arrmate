---
name: Bug Report
about: Report a bug or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## Describe the Bug
A clear and concise description of what the bug is.

## To Reproduce
Steps to reproduce the behavior:
1. Run command '...'
2. With settings '...'
3. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- **Deployment**: [Docker / Local Python]
- **OS**: [e.g., Ubuntu 22.04, Windows 11, macOS 14]
- **Python Version**: [e.g., 3.11.5]
- **Arrmate Version**: [e.g., 0.1.0]
- **LLM Provider**: [Ollama / OpenAI / Anthropic]
- **LLM Model**: [e.g., llama3.1, gpt-4]

## Services
- [ ] Sonarr - Version:
- [ ] Radarr - Version:
- [ ] Lidarr - Version:

## Command/Input
```bash
# The command you ran
arrmate execute "your command here"
```

## Error Output
```
Paste the error output here
```

## Configuration
```yaml
# Relevant parts of your .env (REMOVE API KEYS!)
LLM_PROVIDER=ollama
SONARR_URL=http://localhost:8989
```

## Additional Context
Add any other context about the problem here (screenshots, logs, etc.).
