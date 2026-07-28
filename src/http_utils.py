from __future__ import annotations

import json as jsonlib
import sys
from pathlib import Path
from typing import Any, Mapping

import httpx


def curl(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    data: Any = None,
    json: Any = None,
    files: Mapping[str, Any] | None = None,
    cookies: Mapping[str, str] | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 30.0,
    follow_redirects: bool = False,
    verify: bool | str = True,
    proxy: str | None = None,
    output: str | Path | None = None,
    include_headers: bool = False,
    verbose: bool = False,
    raise_for_status: bool = False,
) -> httpx.Response:
    """
    使用 httpx 模拟常见 curl 功能。

    对应关系：
      method            curl -X
      headers           curl -H
      params            URL 查询参数
      data              curl -d / --data
      json              curl --json
      files             curl -F
      auth              curl -u
      follow_redirects  curl -L
      verify=False      curl -k
      proxy             curl -x
      output            curl -o
      include_headers   curl -i
      verbose           curl -v
    """

    request_method = method.upper()

    if verbose:
        print(f"> {request_method} {url}", file=sys.stderr)
        for name, value in (headers or {}).items():
            print(f"> {name}: {value}", file=sys.stderr)

    with httpx.Client(
        timeout=timeout,
        follow_redirects=follow_redirects,
        verify=verify,
        proxy=proxy,
    ) as client:
        response = client.request(
            method=request_method,
            url=url,
            headers=headers,
            params=params,
            content=data if isinstance(data, (str, bytes)) else None,
            data=data if not isinstance(data, (str, bytes)) else None,
            json=json,
            files=files,
            cookies=cookies,
            auth=auth,
        )

    if verbose:
        print(
            f"< HTTP/{response.http_version} "
            f"{response.status_code} {response.reason_phrase}",
            file=sys.stderr,
        )
        for name, value in response.headers.multi_items():
            print(f"< {name}: {value}", file=sys.stderr)

    if raise_for_status:
        response.raise_for_status()

    if output is not None:
        Path(output).write_bytes(response.content)
        return response

    if include_headers:
        print(
            f"HTTP/{response.http_version} "
            f"{response.status_code} {response.reason_phrase}"
        )
        for name, value in response.headers.multi_items():
            print(f"{name}: {value}")
        print()

    content_type = response.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            print(
                jsonlib.dumps(
                    response.json(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        except ValueError:
            print(response.text)
    elif content_type.startswith("text/") or not content_type:
        print(response.text)
    else:
        sys.stdout.buffer.write(response.content)

    return response