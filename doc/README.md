# yaml-cfg-wizard-ui Documentation

## Overview
`yaml-cfg-wizard-ui` is a framework-independent scalar configuration editor page component. It provides:
- HTML/CSS/JS rendering for configuration UI
- CSRF protection out-of-the-box
- No external dependencies (pure Python)
- Works with any Python web framework

**Status**: Early alpha (0.1.0a1)  
**Python**: ≥3.10  

## Quick Start

```bash
pip install yaml-cfg-wizard-ui
```

```python
from yaml_cfg_wizard_ui import render_page

# Render a configuration editor page
html = render_page(
    config_data={"key": "value"},
    csrf_token="token_here",
    schema={"type": "object", "properties": {...}}
)
```

## Architecture

- **No Framework Dependency**: Pure Python component, integrate with Flask/Django/FastAPI
- **Packaged Assets**: HTML, CSS, JS bundled in the package
- **CSRF Protection**: Built-in CSRF token support
- **No Caching**: Includes `Cache-Control: no-store` headers for security

## Dependencies

None! Pure Python package with built-in HTML/CSS/JS assets.

## See Also

- [yaml-cfg-wizard](../yaml_cfg_wizard) - Core configuration library (sibling)
- [ki-core](../ki-core) - Uses config system for app configuration
- [Ecosystem](../../../) - Full ecosystem

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
