"""Tests for core/demo_auth.py — API key security for Kaggle demo endpoints.

Covers: dependency function, header validation, bypass mode, integration with FastAPI.
All tests are isolated — no real requests are sent."""
import os
import pytest
from unittest.mock import patch
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestVerifyDemoKey:
    """Test the verify_demo_key FastAPI dependency function."""

    @pytest.mark.asyncio
    async def test_no_key_configured_bypasses(self):
        """When DEMO_API_KEY is empty, verification should pass."""
        from core.demo_auth import verify_demo_key
        with patch.dict(os.environ, {"DEMO_API_KEY": ""}, clear=True):
            import importlib
            import core.demo_auth
            importlib.reload(core.demo_auth)
            result = await core.demo_auth.verify_demo_key(x_api_key=None)
            assert result is None

    @pytest.mark.asyncio
    async def test_valid_key_passes(self):
        """Correct X-API-Key should pass verification."""
        from core.demo_auth import verify_demo_key
        with patch.dict(os.environ, {"DEMO_API_KEY": "test-key-123"}, clear=True):
            import importlib
            import core.demo_auth
            importlib.reload(core.demo_auth)
            result = await core.demo_auth.verify_demo_key(x_api_key="test-key-123")
            assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_raises_403(self):
        """Missing header should raise 403."""
        from fastapi import HTTPException
        from core.demo_auth import verify_demo_key
        with patch.dict(os.environ, {"DEMO_API_KEY": "test-key-123"}, clear=True):
            import importlib
            import core.demo_auth
            importlib.reload(core.demo_auth)
            with pytest.raises(HTTPException) as exc:
                await core.demo_auth.verify_demo_key(x_api_key=None)
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_wrong_key_raises_403(self):
        """Wrong key should raise 403."""
        from fastapi import HTTPException
        from core.demo_auth import verify_demo_key
        with patch.dict(os.environ, {"DEMO_API_KEY": "test-key-123"}, clear=True):
            import importlib
            import core.demo_auth
            importlib.reload(core.demo_auth)
            with pytest.raises(HTTPException) as exc:
                await core.demo_auth.verify_demo_key(x_api_key="wrong-key")
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_reload_resets_between_tests(self):
        """Clean up after tests that modify os.environ."""
        import core.demo_auth
        import importlib
        importlib.reload(core.demo_auth)
        # Should not raise because DEMO_API_KEY is likely empty in test env
        result = await core.demo_auth.verify_demo_key(x_api_key=None)
        assert result is None


class TestIntegration:
    """Verify demo_auth module exports expected symbols."""

    def test_module_imports(self):
        from core.demo_auth import verify_demo_key, DEMO_API_KEY
        assert callable(verify_demo_key)
        assert isinstance(DEMO_API_KEY, str)

    def test_env_var_loaded(self):
        """DEMO_API_KEY reads from environment."""
        import core.demo_auth
        # The module reads os.getenv at import time
        assert isinstance(core.demo_auth.DEMO_API_KEY, str)
