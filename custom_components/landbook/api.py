"""Landbook API client — auth, device discovery, TSL model fetch."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import string
import urllib.parse
import urllib.request
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from .const import (
    APP_ID,
    APP_SYSTEM_TYPE,
    APP_VERSION,
    DEFAULT_REGION,
    REGIONS,
)


class LandbookAuthError(Exception):
    """Raised when login fails."""


class LandbookAPIError(Exception):
    """Raised when an API call fails."""


def _region_cfg(region: str) -> dict:
    return REGIONS.get(region, REGIONS[DEFAULT_REGION])


def _encrypt_password(password: str) -> tuple[str, str]:
    """Return (pwd_b64, rand) — AES-128-CBC, matches the Landbook app logic."""
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    md5_full = hashlib.md5(rand.encode()).hexdigest().upper()
    hash_random = md5_full[8:24]
    iv = hash_random[8:16] + hash_random[0:8]

    cipher = AES.new(hash_random.encode(), AES.MODE_CBC, iv.encode())
    encrypted = cipher.encrypt(pad(password.encode(), AES.block_size))
    pwd = base64.b64encode(encrypted).decode()
    return pwd, rand


def _default_headers() -> dict[str, str]:
    return {
        "appId": APP_ID,
        "appVersion": APP_VERSION,
        "appSystemType": APP_SYSTEM_TYPE,
        "Accept": "application/json",
    }


def login(email: str, password: str, region: str = DEFAULT_REGION) -> tuple[str, str]:
    """Authenticate and return (bearer_token, uid)."""
    cfg = _region_cfg(region)
    pwd, rand = _encrypt_password(password)

    sig = hashlib.sha256(
        (email + pwd + rand + cfg["app_domain_key"]).encode()
    ).hexdigest()

    data = urllib.parse.urlencode(
        {
            "email": email,
            "pwd": pwd,
            "random": rand,
            "userDomain": cfg["user_domain"],
            "signature": sig,
        }
    ).encode()

    login_url = cfg["api_base"] + "/v2/enduser/enduserapi/emailPwdLogin"
    headers = {**_default_headers(), "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(login_url, data=data, headers=headers)

    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except Exception as exc:
        raise LandbookAuthError(f"Login request failed: {exc}") from exc

    if resp.get("code") != 200 or "data" not in resp:
        raise LandbookAuthError(f"Login failed: {resp.get('msg', 'unknown error')}")

    bearer_token: str = resp["data"]["accessToken"]["token"]
    rest_token = bearer_token.replace("Bearer ", "")
    payload_b64 = rest_token.split(".")[1]
    uid: str = json.loads(base64.b64decode(payload_b64 + "=="))["uid"]

    return bearer_token, uid


def _api_get(bearer_token: str, api_base: str, path: str, params: dict | None = None) -> Any:
    url = api_base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {**_default_headers(), "Authorization": bearer_token}
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except Exception as exc:
        raise LandbookAPIError(f"API call to {path} failed: {exc}") from exc
    if resp.get("code") != 200:
        raise LandbookAPIError(f"API error on {path}: {resp.get('msg', 'unknown')}")
    return resp["data"]


def get_device_list(bearer_token: str, region: str = DEFAULT_REGION) -> list[dict]:
    api_base = _region_cfg(region)["api_base"]
    data = _api_get(bearer_token, api_base, "/v2/binding/enduserapi/userDeviceList", {"page": 1, "pageSize": 50})
    return data.get("list", [])


def get_tsl(bearer_token: str, pk: str, region: str = DEFAULT_REGION) -> list[dict]:
    api_base = _region_cfg(region)["api_base"]
    data = _api_get(bearer_token, api_base, "/v2/binding/enduserapi/productTSL", {"pk": pk})
    properties = [
        p for p in data.get("properties", [])
        if "W" in p.get("subType", "") and p["type"] == "PROPERTY"
    ]
    properties.sort(key=lambda p: p.get("sort", 0))
    return properties


def refresh_token(bearer_token: str, region: str = DEFAULT_REGION) -> str:
    api_base = _region_cfg(region)["api_base"]
    headers = {
        **_default_headers(),
        "Authorization": bearer_token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req = urllib.request.Request(
        api_base + "/v2/enduser/enduserapi/refreshToken",
        data=b"",
        headers=headers,
        method="PUT",
    )
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except Exception as exc:
        raise LandbookAPIError(f"Token refresh request failed: {exc}") from exc

    if resp.get("code") != 200 or "data" not in resp:
        raise LandbookAuthError(f"Token refresh rejected: {resp.get('msg', 'unknown error')}")
    return resp["data"]["accessToken"]["token"]


def get_device_attributes(bearer_token: str, pk: str, dk: str, region: str = DEFAULT_REGION) -> dict:
    api_base = _region_cfg(region)["api_base"]
    return _api_get(bearer_token, api_base, "/v2/binding/enduserapi/getDeviceBusinessAttributes", {"pk": pk, "dk": dk})


async def async_login(email: str, password: str, region: str = DEFAULT_REGION) -> tuple[str, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, login, email, password, region)


async def async_get_device_list(bearer_token: str, region: str = DEFAULT_REGION) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_device_list, bearer_token, region)


async def async_get_tsl(bearer_token: str, pk: str, region: str = DEFAULT_REGION) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_tsl, bearer_token, pk, region)


async def async_refresh_token(bearer_token: str, region: str = DEFAULT_REGION) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, refresh_token, bearer_token, region)


async def async_get_device_attributes(bearer_token: str, pk: str, dk: str, region: str = DEFAULT_REGION) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_device_attributes, bearer_token, pk, dk, region)
