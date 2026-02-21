from __future__ import annotations

import json
import math
import os
import ssl
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover - fallback path for minimal runtime envs
    httpx = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv() -> None:
        return None

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("korea_weather")

if not os.getenv("KOREA_WEATHER_API_KEY"):
    load_dotenv()

API_BASE = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
TIMEOUT_SECONDS = 15.0

PTY_MAP = {
    0: "없음",
    1: "비",
    2: "비/눈",
    3: "눈",
    4: "소나기",
    5: "빗방울",
    6: "빗방울눈날림",
    7: "눈날림",
}
SKY_MAP = {1: "맑음", 3: "구름많음", 4: "흐림"}
DIRECTION_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
DIRECTION_16_KR = ["북", "북북동", "북동", "동북동", "동", "동남동", "남동", "남남동", "남", "남남서", "남서", "서남서", "서", "서북서", "북서", "북북서"]


@dataclass(frozen=True)
class LambertConformalConic:
    """Lambert Conformal Conic Projection parameters."""

    re: float
    slat1_rad: float
    slat2_rad: float
    olon_rad: float
    sn: float
    sf: float
    ro: float
    xo: float
    yo: float
    pi: float
    degrad: float


@lru_cache(maxsize=1)
def get_projection() -> LambertConformalConic:
    re_km = 6371.00877
    grid = 5.0
    slat1 = 30.0
    slat2 = 60.0
    olon = 126.0
    olat = 38.0
    xo = 210 / grid
    yo = 675 / grid

    pi = math.pi
    degrad = pi / 180.0

    re = re_km / grid
    slat1_rad = slat1 * degrad
    slat2_rad = slat2 * degrad
    olon_rad = olon * degrad
    olat_rad = olat * degrad

    sn = math.tan(pi * 0.25 + slat2_rad * 0.5) / math.tan(pi * 0.25 + slat1_rad * 0.5)
    sn = math.log(math.cos(slat1_rad) / math.cos(slat2_rad)) / math.log(sn)
    sf = math.tan(pi * 0.25 + slat1_rad * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1_rad) / sn
    ro = math.tan(pi * 0.25 + olat_rad * 0.5)
    ro = re * sf / math.pow(ro, sn)

    return LambertConformalConic(
        re=re,
        slat1_rad=slat1_rad,
        slat2_rad=slat2_rad,
        olon_rad=olon_rad,
        sn=sn,
        sf=sf,
        ro=ro,
        xo=xo,
        yo=yo,
        pi=pi,
        degrad=degrad,
    )


def get_grid_coordinate_from_lonlat(lon: float, lat: float) -> tuple[int, int]:
    """위경도 좌표를 기상청 격자 좌표(nx, ny)로 변환합니다."""
    proj = get_projection()

    ra = math.tan(proj.pi * 0.25 + lat * proj.degrad * 0.5)
    ra = proj.re * proj.sf / math.pow(ra, proj.sn)
    theta = lon * proj.degrad - proj.olon_rad

    if theta > proj.pi:
        theta -= 2.0 * proj.pi
    if theta < -proj.pi:
        theta += 2.0 * proj.pi

    theta *= proj.sn

    x = ra * math.sin(theta) + proj.xo
    y = proj.ro - ra * math.cos(theta) + proj.yo
    return int(x + 1.5), int(y + 1.5)


def _require_api_key() -> str:
    api_key = os.getenv("KOREA_WEATHER_API_KEY")
    if not api_key:
        raise ValueError("KOREA_WEATHER_API_KEY 환경변수가 설정되어 있지 않습니다.")
    return urllib.parse.unquote(api_key)


def _wind_direction(degree: float, labels: list[str]) -> str:
    index = int((degree + 11.25) / 22.5) % 16
    return labels[index]


def _is_network_error(error: Exception) -> bool:
    return isinstance(error, urllib.error.URLError) or (
        httpx is not None and isinstance(error, httpx.RequestError)
    )


async def _fetch_weather(endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    url = f"{API_BASE}/{endpoint}"
    if httpx is not None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS)) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        result = response.json()
    else:
        query = urllib.parse.urlencode(params)
        request_url = f"{url}?{query}"
        context = ssl.create_default_context()
        with urllib.request.urlopen(request_url, timeout=TIMEOUT_SECONDS, context=context) as response:
            result = json.loads(response.read().decode("utf-8"))

    header = result.get("response", {}).get("header", {})
    if header.get("resultCode") and header.get("resultCode") != "00":
        raise ValueError(f"API 오류: {header.get('resultCode')} - {header.get('resultMsg', 'Unknown error')}")

    return result.get("response", {}).get("body", {}).get("items", {}).get("item", [])


async def get_nowcast_observation_from_api(lon: float, lat: float) -> str:
    try:
        nx, ny = get_grid_coordinate_from_lonlat(lon, lat)
        now = datetime.now()
        if now.minute < 40:
            now -= timedelta(hours=1)

        items = await _fetch_weather(
            "getUltraSrtNcst",
            {
                "serviceKey": _require_api_key(),
                "numOfRows": "10",
                "pageNo": "1",
                "dataType": "JSON",
                "base_date": now.strftime("%Y%m%d"),
                "base_time": now.strftime("%H00"),
                "nx": nx,
                "ny": ny,
            },
        )

        weather_data: dict[str, str] = {}
        for item in items:
            category = item.get("category")
            value = item.get("obsrValue")
            if category == "T1H":
                weather_data["temperature"] = f"{value}°C"
            elif category == "RN1":
                weather_data["rainfall"] = f"{value}mm"
            elif category == "REH":
                weather_data["humidity"] = f"{value}%"
            elif category == "WSD":
                weather_data["wind_speed"] = f"{value}m/s"

        return (
            f"\n위도 {lat}, 경도 {lon} 현재 날씨:\n"
            f"기온: {weather_data.get('temperature', 'N/A')}\n"
            f"강수량: {weather_data.get('rainfall', 'N/A')}\n"
            f"습도: {weather_data.get('humidity', 'N/A')}\n"
            f"풍속: {weather_data.get('wind_speed', 'N/A')}\n"
        )
    except ValueError as e:
        return f"오류: {e}\n"
    except json.JSONDecodeError as e:
        return f"JSON 파싱 중 오류 발생: {e}\n"
    except Exception as e:
        if _is_network_error(e):
            return f"API 요청 중 오류 발생: {e}\n"
        return f"예상치 못한 오류 발생: {e}\n"


async def get_nowcast_forecast_from_api(lon: float, lat: float) -> str:
    try:
        nx, ny = get_grid_coordinate_from_lonlat(lon, lat)
        now = datetime.now()
        if now.minute < 45:
            now -= timedelta(hours=1)

        base_date = now.strftime("%Y%m%d")
        base_time = now.strftime("%H30")
        items = await _fetch_weather(
            "getUltraSrtFcst",
            {
                "serviceKey": _require_api_key(),
                "numOfRows": "60",
                "pageNo": "1",
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
            },
        )

        grouped: dict[str, dict[str, str]] = {}
        for item in items:
            time_key = f"{item['fcstDate']} {item['fcstTime']}"
            grouped.setdefault(time_key, {})[item["category"]] = item["fcstValue"]

        lines = [
            f"\n위도 {lat}, 경도 {lon} 초단기 예보 (발표: {base_date[:4]}년 {base_date[4:6]}월 {base_date[6:]}일 {base_time[:2]}:{base_time[2:]}시)",
            "=" * 50,
        ]

        for time_key in sorted(grouped):
            fcst_data = grouped[time_key]
            date_str = f"{time_key[:4]}년 {time_key[4:6]}월 {time_key[6:8]}일"
            hhmm = time_key[9:]
            lines.append(f"■ {date_str} {hhmm[:2]}:{hhmm[2:]}시 예보")

            if "T1H" in fcst_data:
                lines.append(f"  기온: {fcst_data['T1H']}°C")
            if "PTY" in fcst_data:
                lines.append(f"  강수형태: {PTY_MAP.get(int(fcst_data['PTY']), '알 수 없음')}")
            if "RN1" in fcst_data:
                lines.append(f"  1시간 강수량: {'없음' if fcst_data['RN1'] == '강수없음' else fcst_data['RN1']}")
            if "REH" in fcst_data:
                lines.append(f"  습도: {fcst_data['REH']}%")
            if "SKY" in fcst_data:
                lines.append(f"  하늘상태: {SKY_MAP.get(int(fcst_data['SKY']), '알 수 없음')}")
            if "WSD" in fcst_data:
                lines.append(f"  풍속: {fcst_data['WSD']}m/s")
            if "VEC" in fcst_data:
                lines.append(f"  풍향: {_wind_direction(float(fcst_data['VEC']), DIRECTION_16)} ({fcst_data['VEC']}°)")
            if "LGT" in fcst_data:
                lgt_value = int(fcst_data["LGT"])
                lines.append(f"  낙뢰: {'없음' if lgt_value == 0 else f'{lgt_value} kA/㎢'}")

            lines.append("")

        return "\n".join(lines)
    except ValueError as e:
        return f"오류: {e}\n"
    except json.JSONDecodeError as e:
        return f"JSON 파싱 중 오류 발생: {e}\n"
    except Exception as e:
        if _is_network_error(e):
            return f"API 요청 중 오류 발생: {e}\n"
        return f"예상치 못한 오류 발생: {e}\n"


async def get_short_term_forecast_from_api(lon: float, lat: float) -> str:
    try:
        nx, ny = get_grid_coordinate_from_lonlat(lon, lat)
        now = datetime.now()
        base_times = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]

        available_time = None
        for bt in base_times:
            bt_hour = int(bt[:2])
            if now.hour > bt_hour or (now.hour == bt_hour and now.minute >= 10):
                available_time = bt

        if available_time is None:
            available_time = "2300"
            now -= timedelta(days=1)

        base_date = now.strftime("%Y%m%d")
        items = await _fetch_weather(
            "getVilageFcst",
            {
                "serviceKey": _require_api_key(),
                "numOfRows": "1000",
                "pageNo": "1",
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": available_time,
                "nx": nx,
                "ny": ny,
            },
        )

        by_date_time: dict[str, dict[str, dict[str, str]]] = {}
        for item in items:
            fcst_date = item["fcstDate"]
            fcst_time = item["fcstTime"]
            by_date_time.setdefault(fcst_date, {}).setdefault(fcst_time, {})[item["category"]] = item["fcstValue"]

        lines = [
            f"\n위도 {lat}, 경도 {lon} 단기 예보 (발표: {base_date} {available_time})",
            f"총 {len(items)}개 데이터 조회",
            "=" * 50,
        ]

        for fcst_date in sorted(by_date_time):
            lines.append(f"\n【 {fcst_date[:4]}년 {fcst_date[4:6]}월 {fcst_date[6:]}일 예보 】")
            day_values = by_date_time[fcst_date].values()
            tmn = next((data["TMN"] for data in day_values if data.get("TMN")), None)
            day_values = by_date_time[fcst_date].values()
            tmx = next((data["TMX"] for data in day_values if data.get("TMX")), None)
            if tmn:
                lines.append(f"  ▶ 최저기온: {tmn}°C")
            if tmx:
                lines.append(f"  ▶ 최고기온: {tmx}°C")

            lines.append("\n  시간별 예보:")
            for fcst_time in sorted(by_date_time[fcst_date]):
                hour = int(fcst_time[:2])
                am_pm = "오전" if hour < 12 else "오후"
                display_hour = 12 if hour == 0 else (hour if hour <= 12 else hour - 12)
                formatted_time = f"{am_pm} {display_hour}시"
                time_data = by_date_time[fcst_date][fcst_time]

                weather_info: list[str] = []
                if "TMP" in time_data:
                    weather_info.append(f"기온 {time_data['TMP']}°C")
                if "POP" in time_data:
                    weather_info.append(f"강수확률 {time_data['POP']}%")
                if "PTY" in time_data and int(time_data["PTY"]) in PTY_MAP and int(time_data["PTY"]) != 0:
                    weather_info.append(PTY_MAP[int(time_data["PTY"])])
                if "PCP" in time_data and time_data["PCP"] not in {"", "강수없음"}:
                    weather_info.append(f"강수량 {time_data['PCP']}")
                if "SNO" in time_data and time_data["SNO"] not in {"", "적설없음"}:
                    weather_info.append(f"적설 {time_data['SNO']}")
                if "SKY" in time_data and int(time_data["SKY"]) in SKY_MAP:
                    weather_info.append(SKY_MAP[int(time_data["SKY"])])
                if "REH" in time_data:
                    weather_info.append(f"습도 {time_data['REH']}%")

                lines.append(f"  ■ {formatted_time}: {', '.join(weather_info)}")

                if "VEC" in time_data and "WSD" in time_data:
                    wsd = float(time_data["WSD"])
                    wind_desc = "약한 바람" if wsd < 4 else "약간 강한 바람" if wsd < 9 else "강한 바람"
                    lines.append(
                        f"    - {_wind_direction(float(time_data['VEC']), DIRECTION_16_KR)}풍 {wind_desc}({wsd}m/s)"
                    )

        return "\n".join(lines)
    except ValueError as e:
        return f"오류: {e}\n"
    except json.JSONDecodeError as e:
        return f"JSON 파싱 중 오류 발생: {e}\n"
    except Exception as e:
        if _is_network_error(e):
            return f"API 요청 중 오류 발생: {e}\n"
        return f"예상치 못한 오류 발생: {e}\n"


@mcp.tool(description="특정 좌표의 현재 관측 날씨를 조회합니다.")
async def get_nowcast_observation(lon: float, lat: float) -> str:
    return await get_nowcast_observation_from_api(lon, lat)


@mcp.tool(description="특정 좌표의 초단기(6시간) 예보를 조회합니다.")
async def get_nowcast_forecast(lon: float, lat: float) -> str:
    return await get_nowcast_forecast_from_api(lon, lat)


@mcp.tool(description="특정 좌표의 단기(3~5일) 예보를 조회합니다.")
async def get_short_term_forecast(lon: float, lat: float) -> str:
    return await get_short_term_forecast_from_api(lon, lat)


if __name__ == "__main__":
    mcp.run(transport="stdio")
