# Contributing to Arrmate

First off, thank you for considering contributing to Arrmate! 🎉

## Code of Conduct

Be respectful, inclusive, and collaborative. We're all here to make media management easier!

## How Can I Contribute?

### Reporting Bugs

Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, LLM provider)
- Error messages and logs

### Suggesting Features

Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md) and explain:
- What problem it solves
- How it should work
- Example commands

### Pull Requests

1. **Fork the repo** and create a branch from `main`
2. **Make your changes**:
   - Follow existing code style (Black + Ruff)
   - Add docstrings to new functions
   - Update documentation if needed
3. **Test your changes**:
   - Test with at least one LLM provider
   - Test with Docker and/or local Python
   - Verify existing tests still pass: `pytest`
4. **Submit PR** with clear description

## Development Setup

### Quick Start

```bash
# Clone your fork
git clone https://github.com/yourusername/arrmate.git
cd arrmate

# Run setup script
bash scripts/dev-setup.sh
source venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Configure .env
cp .env.example .env
# Edit .env with your settings
```

### Project Structure

```
arrmate/
├── src/arrmate/
│   ├── core/          # Core logic (parser, executor)
│   ├── llm/           # LLM providers
│   ├── clients/       # API clients (Sonarr, Radarr)
│   └── interfaces/    # CLI, API, Web
├── tests/             # Test suite
├── docker/            # Docker deployment
└── docs/              # Documentation
```

## Coding Standards

### Python Style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type Hints**: Use type hints everywhere
- **Docstrings**: Google-style docstrings

```bash
# Format code
black src/

# Lint
ruff check src/

# Type check
mypy src/
```

### Commit Messages

Use clear, descriptive commit messages:

```
Add support for Lidarr music management

- Implement LidarrClient with API v3 support
- Add music media type to models
- Update executor to handle music actions
```

## Adding New Features

### Adding a New LLM Provider

1. Create `src/arrmate/llm/yourprovider.py`
2. Inherit from `BaseLLMProvider`
3. Implement `parse_command()` and `generate_response()`
4. Register in `llm/factory.py`
5. Add settings to `config/settings.py`
6. Update documentation

### Adding a New Media Service

1. Create `src/arrmate/clients/yourservice.py`
2. Inherit from `BaseMediaClient`
3. Implement required methods (search, get_item, delete_item, etc.)
4. Add to `clients/discovery.py`
5. Update `MediaType` enum
6. Add configuration to `.env.example`

### Adding a New Action

1. Add to `ActionType` enum in `core/models.py`
2. Update tool schema in `llm/schemas.py`
3. Add handler in `core/executor.py`
4. Update documentation with examples

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=arrmate

# Specific test
pytest tests/test_models.py -v
```

### Writing Tests

- Write tests for new features
- Use `pytest` fixtures
- Mock external services (httpx-mock for API calls)
- Test both success and error cases

## Documentation

### Update Documentation When:

- Adding new features
- Changing command syntax
- Adding new configuration options
- Changing behavior

### Files to Update:

- `README.md` - Main documentation
- `QUICKSTART.md` - If setup process changes
- `.env.example` - New configuration options
- Docstrings - In-code documentation

## Release Process

(For maintainers)

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release tag: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. Build and publish to PyPI
6. Build and publish Docker image

## Questions?

- Open an issue for discussion
- Check existing issues and PRs
- Read the documentation

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- GitHub contributors page

Thank you for making Arrmate better! 🚀
