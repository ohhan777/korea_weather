import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


# 테스트 환경에서 외부 의존성(httpx, mcp, dotenv)이 없더라도 모듈 로드를 가능하게 처리
if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class _Timeout:
        def __init__(self, *_args, **_kwargs):
            pass

    class _RequestError(Exception):
        pass

    class _AsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):  # pragma: no cover
            raise NotImplementedError

    httpx_stub.Timeout = _Timeout
    httpx_stub.RequestError = _RequestError
    httpx_stub.AsyncClient = _AsyncClient
    sys.modules["httpx"] = httpx_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv_stub

if "mcp" not in sys.modules:
    mcp_mod = types.ModuleType("mcp")
    mcp_server_mod = types.ModuleType("mcp.server")
    mcp_fastmcp_mod = types.ModuleType("mcp.server.fastmcp")

    class _FastMCP:
        def __init__(self, *_args, **_kwargs):
            pass

        def tool(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def run(self, *_args, **_kwargs):
            return None

    mcp_fastmcp_mod.FastMCP = _FastMCP

    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.server"] = mcp_server_mod
    sys.modules["mcp.server.fastmcp"] = mcp_fastmcp_mod

import korea_weather


class WeatherServerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ["KOREA_WEATHER_API_KEY"] = "dummy"

    def test_grid_coordinate_conversion(self):
        nx, ny = korea_weather.get_grid_coordinate_from_lonlat(126.9780, 37.5665)
        self.assertIsInstance(nx, int)
        self.assertIsInstance(ny, int)
        self.assertGreater(nx, 0)
        self.assertGreater(ny, 0)

    async def test_nowcast_observation_format(self):
        mock_items = [
            {"category": "T1H", "obsrValue": "21.5"},
            {"category": "REH", "obsrValue": "60"},
            {"category": "RN1", "obsrValue": "0"},
            {"category": "WSD", "obsrValue": "2.3"},
        ]
        with patch.object(korea_weather, "_fetch_weather", AsyncMock(return_value=mock_items)):
            result = await korea_weather.get_nowcast_observation_from_api(126.9780, 37.5665)

        self.assertIn("현재 날씨", result)
        self.assertIn("기온: 21.5°C", result)

    async def test_nowcast_forecast_format(self):
        mock_items = [
            {"fcstDate": "20260101", "fcstTime": "1200", "category": "T1H", "fcstValue": "22"},
            {"fcstDate": "20260101", "fcstTime": "1200", "category": "PTY", "fcstValue": "0"},
        ]
        with patch.object(korea_weather, "_fetch_weather", AsyncMock(return_value=mock_items)):
            result = await korea_weather.get_nowcast_forecast_from_api(126.9780, 37.5665)

        self.assertIn("초단기 예보", result)
        self.assertIn("기온: 22°C", result)


if __name__ == "__main__":
    unittest.main()
