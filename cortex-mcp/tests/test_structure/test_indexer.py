"""Integration tests for the incremental indexer."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.storage.db import CortexDB
from cortex.structure.indexer import index_project


@pytest.fixture
async def db(tmp_path: Path) -> CortexDB:
    cortex_dir = tmp_path / '.cortex'
    cortex_dir.mkdir()
    store = CortexDB(cortex_dir / 'cortex.db')
    await store.start()
    yield store
    await store.stop()


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'main.py').write_text(
        'def main():\n    pass\n\nclass App:\n    def run(self):\n        pass\n',
        encoding='utf-8',
    )
    (src / 'utils.py').write_text(
        'def validate(token: str) -> bool:\n    return len(token) > 0\n',
        encoding='utf-8',
    )
    (src / 'app.ts').write_text(
        'export function initApp(): void {\n  console.log("init")\n}\n',
        encoding='utf-8',
    )
    (tmp_path / 'README.md').write_text('# Test project\n', encoding='utf-8')
    return tmp_path


class TestIndexProject:
    async def test_indexes_python_files(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        stats = await index_project(db, sample_project)
        assert stats['files_indexed'] >= 2
        assert stats['symbols_extracted'] >= 3

    async def test_populates_symbols_table(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        rows = await db.read('SELECT COUNT(*) FROM symbols', ())
        assert rows[0][0] >= 3

    async def test_populates_file_index(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        rows = await db.read('SELECT COUNT(*) FROM file_index', ())
        assert rows[0][0] >= 2

    async def test_populates_projects(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        rows = await db.read('SELECT name FROM projects', ())
        assert len(rows) == 1
        assert rows[0][0] == sample_project.name

    async def test_skips_non_source_files(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        rows = await db.read(
            "SELECT file_path FROM file_index WHERE file_path LIKE '%README%'", ()
        )
        assert len(rows) == 0

    async def test_populates_fts(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        rows = await db.read(
            "SELECT file_path FROM source_fts WHERE content MATCH 'validate'", ()
        )
        assert len(rows) >= 1

    async def test_indexes_typescript(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        rows = await db.read(
            "SELECT name FROM symbols WHERE language = 'typescript'", ()
        )
        assert any(r[0] == 'initApp' for r in rows)


class TestIncrementalIndexing:
    async def test_skip_unchanged_files(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        stats1 = await index_project(db, sample_project)
        stats2 = await index_project(db, sample_project)
        assert stats2['files_skipped'] >= stats1['files_indexed']
        assert stats2['files_indexed'] == 0

    async def test_reindex_changed_file(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        src = sample_project / 'src' / 'utils.py'
        src.write_text(
            'def validate(token: str) -> bool:\n    return len(token) > 0\n\n'
            'def new_function():\n    pass\n',
            encoding='utf-8',
        )
        stats = await index_project(db, sample_project)
        assert stats['files_indexed'] >= 1

    async def test_force_reindex(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        stats = await index_project(db, sample_project, force=True)
        assert stats['files_indexed'] >= 2

    async def test_deleted_file_purged(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        await index_project(db, sample_project)
        (sample_project / 'src' / 'utils.py').unlink()
        stats = await index_project(db, sample_project)
        assert stats['files_deleted'] >= 1
        rows = await db.read(
            "SELECT COUNT(*) FROM symbols WHERE file_path LIKE '%utils.py'", ()
        )
        assert rows[0][0] == 0


class TestEdgeExtraction:
    async def test_creates_calls_edges(
        self, db: CortexDB, tmp_path: Path
    ) -> None:
        src = tmp_path / 'src'
        src.mkdir(exist_ok=True)
        (src / 'main.py').write_text(
            'from utils import validate\n\n'
            'def main():\n    validate()\n',
            encoding='utf-8',
        )
        (src / 'utils.py').write_text(
            'def validate():\n    return True\n',
            encoding='utf-8',
        )
        await index_project(db, tmp_path, force=True)
        rows = await db.read(
            "SELECT edge_type FROM edges WHERE edge_type = 'CALLS'", ()
        )
        assert len(rows) >= 1

    async def test_creates_imports_edges(
        self, db: CortexDB, tmp_path: Path
    ) -> None:
        src = tmp_path / 'src'
        src.mkdir(exist_ok=True)
        (src / 'main.py').write_text(
            'from utils import validate\n\ndef main():\n    pass\n',
            encoding='utf-8',
        )
        (src / 'utils.py').write_text(
            'def validate():\n    return True\n',
            encoding='utf-8',
        )
        await index_project(db, tmp_path, force=True)
        rows = await db.read(
            "SELECT edge_type FROM edges WHERE edge_type = 'IMPORTS'", ()
        )
        assert len(rows) >= 1

    async def test_edges_deleted_on_reindex(
        self, db: CortexDB, tmp_path: Path
    ) -> None:
        src = tmp_path / 'src'
        src.mkdir(exist_ok=True)
        (src / 'main.py').write_text(
            'from utils import validate\n\ndef main():\n    validate()\n',
            encoding='utf-8',
        )
        (src / 'utils.py').write_text(
            'def validate():\n    return True\n',
            encoding='utf-8',
        )
        await index_project(db, tmp_path, force=True)
        (src / 'main.py').write_text(
            'def main():\n    pass\n',
            encoding='utf-8',
        )
        await index_project(db, tmp_path, force=True)
        rows = await db.read(
            "SELECT edge_type FROM edges WHERE edge_type = 'CALLS'", ()
        )
        assert len(rows) == 0

    async def test_ts_imports_edges(
        self, db: CortexDB, tmp_path: Path
    ) -> None:
        src = tmp_path / 'src'
        src.mkdir(exist_ok=True)
        (src / 'app.ts').write_text(
            "import { Router } from './router'\n\n"
            "export function initApp(): void {}\n",
            encoding='utf-8',
        )
        (src / 'router.ts').write_text(
            "export class Router {\n  navigate(): void {}\n}\n",
            encoding='utf-8',
        )
        await index_project(db, tmp_path, force=True)
        rows = await db.read(
            "SELECT edge_type FROM edges WHERE edge_type = 'IMPORTS'", ()
        )
        assert len(rows) >= 1


class TestFileSizeLimit:
    async def test_skips_large_files(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        large = sample_project / 'src' / 'huge.py'
        large.write_text('x = 1\n' * 100000, encoding='utf-8')
        await index_project(db, sample_project)
        rows = await db.read(
            "SELECT COUNT(*) FROM file_index WHERE file_path LIKE '%huge.py'", ()
        )
        assert rows[0][0] == 0

    async def test_skips_binary_files(
        self, db: CortexDB, sample_project: Path
    ) -> None:
        binary = sample_project / 'src' / 'data.py'
        binary.write_bytes(b'# python\n\x00\x01\x02binary content')
        await index_project(db, sample_project)
        rows = await db.read(
            "SELECT COUNT(*) FROM file_index WHERE file_path LIKE '%data.py'", ()
        )
        assert rows[0][0] == 0
