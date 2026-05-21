"""Cortex MCP server entry point."""

from __future__ import annotations

import sys


def main() -> None:
    from .server import cortex
    transport = 'stdio'
    if '--transport' in sys.argv:
        idx = sys.argv.index('--transport')
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    if '--init' in sys.argv:
        _init_project()
        return

    cortex.run(transport=transport)


def _init_project() -> None:
    import json
    import os
    from pathlib import Path

    project_dir = Path(os.getcwd())
    cortex_dir = project_dir / '.cortex'
    cortex_dir.mkdir(exist_ok=True)

    gitignore = cortex_dir / '.gitignore'
    if not gitignore.exists():
        gitignore.write_text('*\n', encoding='utf-8')

    mcp_config = project_dir / '.mcp.json'
    if mcp_config.exists():
        mcp_config.rename(mcp_config.with_suffix('.json.bak'))

    mcp_config.write_text(
        json.dumps({
            'mcpServers': {
                'cortex': {
                    'command': 'cortex-mcp',
                    'args': [],
                }
            }
        }, indent=2),
        encoding='utf-8',
    )

    print('Cortex initialized:')
    print(f'  .cortex/          — data directory')
    print(f'  .mcp.json         — MCP config (cortex-mcp)')
    print(f'')
    print(f'Next: start Claude Code in this directory.')
    print(f'  cortex_index will auto-detect and index the project.')


if __name__ == '__main__':
    main()
