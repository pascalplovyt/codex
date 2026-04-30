import argparse
import html
import json
import re
import ssl
import sys
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener


LOGIN_URL = "https://ofbiz-world.digitalocean.rcswimax.com:8443/webtools/control/login"
PROCESSOR_URL = "https://ofbiz-world.digitalocean.rcswimax.com:8443/webtools/control/EntitySQLProcessor"


def extract_results_block(content):
    marker = '<li class="h3">Results</li>'
    index = content.find(marker)
    if index == -1:
        raise RuntimeError("Results block not found in SQL processor response.")
    section = content[index:]
    match = re.search(
        r'<div class="screenlet-body">\s*(.*?)\s*</div>\s*</div>',
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("Results body not found in SQL processor response.")
    return match.group(1)


def parse_html_table(results_html):
    row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", results_html, flags=re.IGNORECASE | re.DOTALL)
    headers = []
    rows = []
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


def make_opener():
    jar = CookieJar()
    ssl_context = ssl.create_default_context()
    return build_opener(HTTPCookieProcessor(jar), HTTPSHandler(context=ssl_context))


def request(opener, url, data=None):
    payload = None
    headers = {}
    if data is not None:
        payload = urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=payload, headers=headers)
    with opener.open(req, timeout=600) as response:
        return response.read().decode("utf-8", errors="replace")


def login(opener, username, password):
    request(opener, PROCESSOR_URL)
    request(
        opener,
        LOGIN_URL,
        {
            "USERNAME": username,
            "PASSWORD": password,
            "JavaScriptEnabled": "Y",
        },
    )


def run_sql(opener, sql, row_limit="2000", group="org.ofbiz"):
    normalized_sql = " ".join(sql.split())
    content = request(
        opener,
        PROCESSOR_URL,
        {
            "group": group,
            "sqlCommand": normalized_sql,
            "rowLimit": row_limit,
            "submitButton": "Submit",
        },
    )
    results_html = extract_results_block(content)
    plain_text = html.unescape(re.sub(r"<[^>]+>", " ", results_html))
    if "SQL Exception while executing" in plain_text:
        raise RuntimeError(" ".join(plain_text.split()))
    headers, rows = parse_html_table(results_html)
    return [dict(zip(headers, row)) for row in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    opener = make_opener()
    login(opener, args.username, args.password)

    db_info = run_sql(
        opener,
        """
        SELECT current_database() AS database_name,
               current_schema() AS schema_name,
               version() AS db_version
        """,
        row_limit="10",
    )

    tables = run_sql(
        opener,
        """
        SELECT t.table_schema,
               t.table_name,
               (
                   xpath(
                       '/row/cnt/text()',
                       query_to_xml(
                           format('SELECT count(*) AS cnt FROM %I.%I', t.table_schema, t.table_name),
                           false,
                           true,
                           ''
                       )
                   )
               )[1]::text::bigint AS record_count
        FROM information_schema.tables t
        WHERE t.table_type = 'BASE TABLE'
          AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY t.table_schema, t.table_name
        """,
        row_limit="5000",
    )

    columns = run_sql(
        opener,
        """
        SELECT c.table_schema,
               c.table_name,
               c.ordinal_position,
               c.column_name,
               c.data_type,
               c.udt_name,
               c.is_nullable,
               c.column_default,
               c.character_maximum_length,
               c.numeric_precision,
               c.numeric_scale
        FROM information_schema.columns c
        WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """,
        row_limit="20000",
    )

    primary_unique_constraints = run_sql(
        opener,
        """
        SELECT tc.table_schema,
               tc.table_name,
               tc.constraint_name,
               tc.constraint_type,
               string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) AS columns,
               '' AS foreign_table_schema,
               '' AS foreign_table_name,
               '' AS foreign_columns,
               '' AS update_rule,
               '' AS delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        WHERE tc.table_schema NOT IN ('pg_catalog', 'information_schema')
          AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
        GROUP BY tc.table_schema,
                 tc.table_name,
                 tc.constraint_name,
                 tc.constraint_type
        ORDER BY tc.table_schema, tc.table_name, tc.constraint_type, tc.constraint_name
        """,
        row_limit="30000",
    )

    foreign_key_constraints = run_sql(
        opener,
        """
        SELECT src_ns.nspname AS table_schema,
               src_tbl.relname AS table_name,
               con.conname AS constraint_name,
               'FOREIGN KEY' AS constraint_type,
               string_agg(src_att.attname, ',' ORDER BY seq.i) AS columns,
               ref_ns.nspname AS foreign_table_schema,
               ref_tbl.relname AS foreign_table_name,
               string_agg(ref_att.attname, ',' ORDER BY seq.i) AS foreign_columns,
               CASE con.confupdtype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
               END AS update_rule,
               CASE con.confdeltype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
               END AS delete_rule
        FROM pg_constraint con
        JOIN pg_class src_tbl ON src_tbl.oid = con.conrelid
        JOIN pg_namespace src_ns ON src_ns.oid = src_tbl.relnamespace
        JOIN pg_class ref_tbl ON ref_tbl.oid = con.confrelid
        JOIN pg_namespace ref_ns ON ref_ns.oid = ref_tbl.relnamespace
        JOIN generate_subscripts(con.conkey, 1) AS seq(i) ON TRUE
        JOIN pg_attribute src_att
          ON src_att.attrelid = con.conrelid
         AND src_att.attnum = con.conkey[seq.i]
        JOIN pg_attribute ref_att
          ON ref_att.attrelid = con.confrelid
         AND ref_att.attnum = con.confkey[seq.i]
        WHERE con.contype = 'f'
          AND src_ns.nspname NOT IN ('pg_catalog', 'information_schema')
        GROUP BY src_ns.nspname,
                 src_tbl.relname,
                 con.conname,
                 ref_ns.nspname,
                 ref_tbl.relname,
                 con.confupdtype,
                 con.confdeltype
        ORDER BY src_ns.nspname, src_tbl.relname, con.conname
        """,
        row_limit="30000",
    )

    constraints = primary_unique_constraints + foreign_key_constraints

    indexes = run_sql(
        opener,
        """
        SELECT schemaname AS table_schema,
               tablename AS table_name,
               indexname AS index_name,
               indexdef AS index_definition
        FROM pg_indexes
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schemaname, tablename, indexname
        """,
        row_limit="30000",
    )

    views = run_sql(
        opener,
        """
        SELECT ns.nspname AS table_schema,
               cls.relname AS view_name,
               CASE cls.relkind
                    WHEN 'm' THEN 'materialized'
                    ELSE 'view'
               END AS view_type,
               pg_get_viewdef(cls.oid, true) AS definition
        FROM pg_class cls
        JOIN pg_namespace ns ON ns.oid = cls.relnamespace
        WHERE cls.relkind IN ('v', 'm')
          AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY ns.nspname, cls.relname
        """,
        row_limit="10000",
    )

    sequences = run_sql(
        opener,
        """
        SELECT sequence_schema,
               sequence_name,
               data_type,
               start_value,
               minimum_value,
               maximum_value,
               increment AS increment_by,
               cycle_option,
               '' AS cache_size
        FROM information_schema.sequences
        WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY sequence_schema, sequence_name
        """,
        row_limit="10000",
    )

    routines = run_sql(
        opener,
        """
        SELECT ns.nspname AS routine_schema,
               proc.proname AS routine_name,
               'FUNCTION' AS routine_type,
               pg_get_functiondef(proc.oid) AS definition
        FROM pg_proc proc
        JOIN pg_namespace ns ON ns.oid = proc.pronamespace
        WHERE ns.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY ns.nspname, proc.proname, proc.oid
        """,
        row_limit="20000",
    )

    triggers = run_sql(
        opener,
        """
        SELECT ns.nspname AS table_schema,
               cls.relname AS table_name,
               trg.tgname AS trigger_name,
               pg_get_triggerdef(trg.oid, true) AS definition
        FROM pg_trigger trg
        JOIN pg_class cls ON cls.oid = trg.tgrelid
        JOIN pg_namespace ns ON ns.oid = cls.relnamespace
        WHERE NOT trg.tgisinternal
          AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY ns.nspname, cls.relname, trg.tgname
        """,
        row_limit="20000",
    )

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "database": db_info[0] if db_info else {},
                "tables": tables,
                "columns": columns,
                "constraints": constraints,
                "indexes": indexes,
                "views": views,
                "sequences": sequences,
                "routines": routines,
                "triggers": triggers,
            },
            fh,
            indent=2,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
