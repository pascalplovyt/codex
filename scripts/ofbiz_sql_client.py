import html
import re
import ssl
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener


@dataclass
class OFBizConfig:
    base_url: str
    username: str
    password: str
    group: str = "org.ofbiz"
    timeout_seconds: int = 600

    @property
    def control_url(self) -> str:
        url = self.base_url.rstrip("/")
        for suffix in ("/EntitySQLProcessor", "/login", "/main"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
        return url

    @property
    def login_url(self) -> str:
        return self.control_url + "/login"

    @property
    def processor_url(self) -> str:
        return self.control_url + "/EntitySQLProcessor"


class OFBizSqlClient:
    def __init__(self, config: OFBizConfig):
        self.config = config
        self.opener = self._make_opener()
        self.logged_in = False

    def _make_opener(self):
        jar = CookieJar()
        ssl_context = ssl.create_default_context()
        return build_opener(HTTPCookieProcessor(jar), HTTPSHandler(context=ssl_context))

    def _request(self, url: str, data: Optional[Dict[str, str]] = None) -> str:
        payload = None
        headers = {}
        if data is not None:
            payload = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=payload, headers=headers)
        with self.opener.open(req, timeout=self.config.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _contains_login_form(content: str) -> bool:
        lowered = content.lower()
        return (
            'name="username"' in lowered
            and 'name="password"' in lowered
            or "/control/login" in lowered
            or "javascriptenabled" in lowered and "username" in lowered and "password" in lowered
        )

    @staticmethod
    def _response_summary(content: str) -> str:
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", content))).strip()
        return text[:300]

    def login(self, refresh_session: bool = False):
        if refresh_session:
            self.opener = self._make_opener()
        self._request(self.config.processor_url)
        response = self._request(
            self.config.login_url,
            {
                "USERNAME": self.config.username,
                "PASSWORD": self.config.password,
                "JavaScriptEnabled": "Y",
            },
        )
        if self._contains_login_form(response):
            raise RuntimeError("OFBiz login failed. The remote site returned the login form again after submitting credentials.")
        self.logged_in = True

    @staticmethod
    def _extract_results_block(content: str) -> str:
        marker = '<li class="h3">Results</li>'
        index = content.find(marker)
        if index == -1:
            raise RuntimeError(f"Results block not found in SQL processor response. Response preview: {OFBizSqlClient._response_summary(content)}")
        section = content[index:]
        match = re.search(
            r'<div class="screenlet-body">\s*(.*?)\s*</div>\s*</div>',
            section,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise RuntimeError(f"Results body not found in SQL processor response. Response preview: {OFBizSqlClient._response_summary(content)}")
        return match.group(1)

    @staticmethod
    def _parse_html_table(results_html: str):
        row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", results_html, flags=re.IGNORECASE | re.DOTALL)
        headers: List[str] = []
        rows: List[List[str]] = []
        for index, row_html in enumerate(row_matches):
            cells = [
                html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
                for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
            ]
            if not cells:
                continue
            is_header = "header-row" in row_html.lower() or (index == 0 and not headers)
            if is_header:
                headers = cells
            else:
                rows.append(cells)
        return headers, rows

    def run_sql(self, sql: str, row_limit: int = 2000) -> List[Dict[str, str]]:
        normalized_sql = " ".join(sql.split())
        payload = {
            "group": self.config.group,
            "sqlCommand": normalized_sql,
            "rowLimit": str(row_limit),
            "submitButton": "Submit",
        }
        last_error = None
        for attempt in range(2):
            try:
                if not self.logged_in:
                    self.login(refresh_session=(attempt > 0))

                content = self._request(self.config.processor_url, payload)
                if self._contains_login_form(content):
                    raise RuntimeError("OFBiz session expired and returned the login page.")

                results_html = self._extract_results_block(content)
                plain_text = html.unescape(re.sub(r"<[^>]+>", " ", results_html))
                if "SQL Exception while executing" in plain_text:
                    raise RuntimeError(" ".join(plain_text.split()))
                headers, rows = self._parse_html_table(results_html)
                return [dict(zip(headers, row)) for row in rows]
            except RuntimeError as exc:
                last_error = exc
                message = str(exc).lower()
                should_retry = (
                    attempt == 0
                    and (
                        "login" in message
                        or "results block not found" in message
                        or "results body not found" in message
                    )
                )
                if not should_retry:
                    raise
                self.logged_in = False
                self.login(refresh_session=True)

        raise last_error if last_error else RuntimeError("Unknown OFBiz SQL client failure.")
