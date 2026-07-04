"""Tests for the Frontend Editor skill."""
import json
import pytest
from pathlib import Path

from src.core.skills_manager import SkillsManager
from skills.frontend_editor.tools import (
    FRONTEND_DIR,
    _is_safe_path,
)


class TestListFrontendFiles:
    @pytest.mark.asyncio
    async def test_list_pages(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('list_frontend_files', {
            'subdir': 'src/pages',
            'extensions': ['.tsx']
        }))
        assert result['file_count'] > 0
        assert any('Chat.tsx' in f for f in result['files'])
        assert any('Dashboard.tsx' in f for f in result['files'])

    @pytest.mark.asyncio
    async def test_list_components(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('list_frontend_files', {
            'subdir': 'src/components',
            'extensions': ['.tsx']
        }))
        assert result['file_count'] > 0

    @pytest.mark.asyncio
    async def test_list_invalid_dir(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('list_frontend_files', {
            'subdir': 'nonexistent/dir'
        }))
        assert 'error' in result


class TestReadFrontendFile:
    @pytest.mark.asyncio
    async def test_read_app_tsx(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('read_frontend_file', {
            'file_path': 'src/App.tsx'
        }))
        assert 'content' in result
        assert 'Routes' in result['content']
        assert result['lines'] > 0

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('read_frontend_file', {
            'file_path': 'src/does_not_exist.tsx'
        }))
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('read_frontend_file', {
            'file_path': '../../etc/passwd'
        }))
        assert 'error' in result
        assert 'not allowed' in result['error']


class TestWriteFrontendFile:
    @pytest.mark.asyncio
    async def test_disallowed_extension(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('write_frontend_file', {
            'file_path': 'src/malware.py',
            'content': 'import os; os.system("rm -rf /")'
        }))
        assert 'error' in result
        assert 'not allowed' in result['error']

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('write_frontend_file', {
            'file_path': '../../etc/passwd',
            'content': 'malicious'
        }))
        assert 'error' in result


class TestGetFrontendInfo:
    @pytest.mark.asyncio
    async def test_get_routes(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('get_frontend_info', {
            'section': 'routes'
        }))
        assert 'routes' in result
        assert '/' in result['routes']
        assert '/chat' in result['routes']

    @pytest.mark.asyncio
    async def test_get_pages(self):
        sm = SkillsManager()
        await sm.load_skills()
        result = json.loads(await sm.execute_tool('get_frontend_info', {
            'section': 'pages'
        }))
        assert 'pages' in result
        assert 'Chat.tsx' in result['pages']


class TestSafePath:
    def test_safe_src_path(self):
        assert _is_safe_path(FRONTEND_DIR / 'src/App.tsx') is True

    def test_safe_pages_path(self):
        assert _is_safe_path(FRONTEND_DIR / 'src/pages/Chat.tsx') is True

    def test_blocked_node_modules(self):
        assert _is_safe_path(FRONTEND_DIR / 'node_modules/react/index.js') is False

    def test_blocked_hidden_dir(self):
        assert _is_safe_path(FRONTEND_DIR / '.git/config') is False

    def test_blocked_outside_frontend(self):
        assert _is_safe_path(Path('/etc/passwd')) is False

    def test_blocked_traversal(self):
        assert _is_safe_path(FRONTEND_DIR / '../secret.txt') is False
