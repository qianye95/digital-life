"""Tests for wiki tool integration."""

import pytest
from pathlib import Path


class TestWikiToolImport:
    """Test that wiki tools can be imported and instantiated."""

    def test_wiki_tool_import(self):
        """WikiTool class should be importable."""
        from domain.tools.wiki_tool import WikiTool
        assert WikiTool is not None

    def test_wiki_tool_instantiation(self):
        """WikiTool should instantiate with valid path."""
        from domain.tools.wiki_tool import WikiTool
        wiki_path = "/Users/mac/Documents/qianye/hermes/个人助手/wiki"
        if Path(wiki_path).exists():
            tool = WikiTool(wiki_path)
            assert tool is not None

    def test_wiki_tool_invalid_path(self):
        """WikiTool should raise error for invalid path."""
        from domain.tools.wiki_tool import WikiTool
        with pytest.raises(ValueError):
            WikiTool("/nonexistent/path")


class TestWikiToolsRegistration:
    """Test that wiki tools register correctly."""

    def test_wiki_tools_module_import(self):
        """wiki_tools module should be importable."""
        from interfaces.tools import wiki_tools
        assert wiki_tools is not None

    def test_wiki_tools_registered(self):
        """Wiki tools should be in registry after import."""
        from interfaces.tools import wiki_tools
        from interfaces.tools.registry import registry
        
        expected_tools = [
            "wiki_index", "wiki_list", "wiki_read",
            "wiki_search", "wiki_write_session",
            "wiki_update_entity", "wiki_update_index"
        ]
        
        all_tools = registry.get_all_tool_names()
        for tool_name in expected_tools:
            assert tool_name in all_tools, f"Tool {tool_name} not registered"

    def test_wiki_toolset_available(self):
        """Wiki toolset should be available."""
        from interfaces.tools import wiki_tools
        from interfaces.tools.registry import registry
        
        assert registry.is_toolset_available("wiki")

    def test_wiki_tool_definitions(self):
        """Wiki tools should have valid OpenAI function definitions."""
        from interfaces.tools import wiki_tools
        from interfaces.tools.registry import registry
        
        expected_tools = {
            "wiki_index", "wiki_list", "wiki_read",
            "wiki_search", "wiki_write_session",
            "wiki_update_entity", "wiki_update_index"
        }
        
        # 使用 get_definitions 方法，传入工具名称集合
        definitions = registry.get_definitions(expected_tools)
        assert len(definitions) == 7
        
        # Check each has required fields
        for defn in definitions:
            assert "type" in defn
            assert defn["type"] == "function"
            assert "function" in defn
            assert "name" in defn["function"]
            assert "description" in defn["function"]
            assert "parameters" in defn["function"]


class TestWikiToolOperations:
    """Test actual wiki operations with real data."""

    @pytest.fixture
    def wiki_tool(self):
        from domain.tools.wiki_tool import WikiTool
        wiki_path = "/Users/mac/Documents/qianye/hermes/个人助手/wiki"
        if not Path(wiki_path).exists():
            pytest.skip("Wiki path does not exist")
        return WikiTool(wiki_path)

    def test_read_index(self, wiki_tool):
        """Should read wiki index successfully."""
        result = wiki_tool.read_index()
        assert "error" not in result
        assert "path" in result
        assert "last_updated" in result
        assert "stats" in result

    def test_list_files(self, wiki_tool):
        """Should list files successfully."""
        files = wiki_tool.list_files()
        assert isinstance(files, list)
        # Should have some files
        assert len(files) > 0

    def test_list_files_by_category(self, wiki_tool):
        """Should list files by category."""
        files = wiki_tool.list_files("sessions")
        assert isinstance(files, list)

    def test_search(self, wiki_tool):
        """Should search wiki content."""
        results = wiki_tool.search("AI")
        assert isinstance(results, list)

    def test_read_nonexistent_document(self, wiki_tool):
        """Should return error for nonexistent document."""
        result = wiki_tool.read_document("nonexistent/path")
        assert "error" in result
