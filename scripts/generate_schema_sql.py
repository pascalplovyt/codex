import argparse
import json
import re
from pathlib import Path


ARRAY_TYPE_MAP = {
    "_varchar": "character varying[]",
    "_text": "text[]",
    "_bpchar": "character[]",
    "_int2": "smallint[]",
    "_int4": "integer[]",
    "_int8": "bigint[]",
    "_numeric": "numeric[]",
    "_bool": "boolean[]",
    "_date": "date[]",
    "_timestamp": "timestamp without time zone[]",
    "_timestamptz": "timestamp with time zone[]",
    "_float4": "real[]",
    "_float8": "double precision[]",
    "_bytea": "bytea[]",
}


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def qname(schema: str, name: str) -> str:
    return f"{qident(schema)}.{qident(name)}"


def build_type(column: dict) -> str:
    data_type = (column.get("data_type") or "").strip()
    udt_name = (column.get("udt_name") or "").strip()
    char_len = (column.get("character_maximum_length") or "").strip()
    precision = (column.get("numeric_precision") or "").strip()
    scale = (column.get("numeric_scale") or "").strip()

    if data_type == "ARRAY":
        return ARRAY_TYPE_MAP.get(udt_name, f"{udt_name.lstrip('_')}[]")
    if data_type in {"character varying", "character"} and char_len:
        return f"{data_type}({char_len})"
    if data_type == "numeric" and precision:
        return f"numeric({precision},{scale or '0'})" if scale else f"numeric({precision})"
    if data_type == "USER-DEFINED" and udt_name:
        return qident(udt_name)
    return data_type or qident(udt_name)


def build_column(column: dict) -> str:
    parts = [qident(column["column_name"]), build_type(column)]
    default = (column.get("column_default") or "").strip()
    if default:
        parts.append(f"DEFAULT {default}")
    if (column.get("is_nullable") or "").upper() == "NO":
        parts.append("NOT NULL")
    return " ".join(parts)


def quote_ident_list(csv_text: str) -> str:
    seen = set()
    ordered = []
    for raw in csv_text.split(","):
        part = raw.strip()
        if not part or part in seen:
            continue
        seen.add(part)
        ordered.append(qident(part))
    return ", ".join(ordered)


def normalize_index_def(index_def: str) -> str:
    return re.sub(
        r"^CREATE(\s+UNIQUE)?\s+INDEX\s+",
        lambda m: f"CREATE{m.group(1) or ''} INDEX IF NOT EXISTS ",
        index_def,
        count=1,
        flags=re.IGNORECASE,
    )


def normalize_trigger_def(trigger_def: str) -> str:
    return re.sub(
        r"^CREATE\s+TRIGGER\s+",
        "CREATE OR REPLACE TRIGGER ",
        trigger_def,
        count=1,
        flags=re.IGNORECASE,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))

    tables = data["tables"]
    columns = data["columns"]
    constraints = data.get("constraints", [])
    indexes = data.get("indexes", [])
    views = data.get("views", [])
    sequences = data.get("sequences", [])
    routines = data.get("routines", [])
    triggers = data.get("triggers", [])

    columns_by_table = {}
    for column in columns:
        key = (column["table_schema"], column["table_name"])
        columns_by_table.setdefault(key, []).append(column)

    statements = [
        "-- Generated from OFBiz metadata snapshot",
        "CREATE SCHEMA IF NOT EXISTS public;",
        "",
    ]

    for table in tables:
        key = (table["table_schema"], table["table_name"])
        cols = sorted(columns_by_table.get(key, []), key=lambda c: int(c["ordinal_position"]))
        if not cols:
            continue
        statements.append(f"CREATE TABLE IF NOT EXISTS {qname(*key)} (")
        for idx, column in enumerate(cols):
            suffix = "," if idx < len(cols) - 1 else ""
            statements.append(f"    {build_column(column)}{suffix}")
        statements.append(");")
        statements.append("")

    for sequence in sequences:
        cycle_clause = " CYCLE" if str(sequence.get("cycle_option", "")).strip().upper() in {"YES", "TRUE", "T"} else " NO CYCLE"
        statements.append(
            f"CREATE SEQUENCE IF NOT EXISTS {qname(sequence['sequence_schema'], sequence['sequence_name'])} "
            f"AS {sequence.get('data_type', 'bigint')} "
            f"INCREMENT BY {sequence.get('increment_by', '1')} "
            f"MINVALUE {sequence.get('minimum_value', '1')} "
            f"MAXVALUE {sequence.get('maximum_value', '9223372036854775807')} "
            f"START WITH {sequence.get('start_value', '1')} "
            f"CACHE {sequence.get('cache_size', '1')}{cycle_clause};"
        )

    if sequences:
        statements.append("")

    primary_and_unique = [c for c in constraints if c["constraint_type"] in {"PRIMARY KEY", "UNIQUE"}]
    foreign_keys = [c for c in constraints if c["constraint_type"] == "FOREIGN KEY"]

    for constraint in primary_and_unique:
        table_ref = qname(constraint["table_schema"], constraint["table_name"])
        statements.append(
            f"ALTER TABLE {table_ref} "
            f"ADD CONSTRAINT {qident(constraint['constraint_name'])} "
            f"{constraint['constraint_type']} ({quote_ident_list(constraint['columns'])});"
        )

    if primary_and_unique:
        statements.append("")

    for constraint in foreign_keys:
        table_ref = qname(constraint["table_schema"], constraint["table_name"])
        foreign_ref = qname(constraint["foreign_table_schema"], constraint["foreign_table_name"])
        update_rule = constraint.get("update_rule") or "NO ACTION"
        delete_rule = constraint.get("delete_rule") or "NO ACTION"
        statements.append(
            f"ALTER TABLE {table_ref} "
            f"ADD CONSTRAINT {qident(constraint['constraint_name'])} "
            f"FOREIGN KEY ({quote_ident_list(constraint['columns'])}) "
            f"REFERENCES {foreign_ref} ({quote_ident_list(constraint['foreign_columns'])}) "
            f"ON UPDATE {update_rule} ON DELETE {delete_rule};"
        )

    if foreign_keys:
        statements.append("")

    reserved_index_names = {
        c["constraint_name"]
        for c in primary_and_unique
    }
    for index in indexes:
        if index["index_name"] in reserved_index_names:
            continue
        statements.append(normalize_index_def(index["index_definition"]) + ";")

    if indexes:
        statements.append("")

    for routine in routines:
        definition = (routine.get("definition") or "").strip()
        if definition:
            statements.append(definition.rstrip(";") + ";")
            statements.append("")

    for view in views:
        definition = (view.get("definition") or "").strip()
        if not definition:
            continue
        if (view.get("view_type") or "").lower() == "materialized":
            statements.append(
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {qname(view['table_schema'], view['view_name'])} AS "
                f"{definition} WITH NO DATA;"
            )
        else:
            statements.append(
                f"CREATE OR REPLACE VIEW {qname(view['table_schema'], view['view_name'])} AS {definition};"
            )

    if views:
        statements.append("")

    for trigger in triggers:
        definition = (trigger.get("definition") or "").strip()
        if definition:
            statements.append(normalize_trigger_def(definition.rstrip(";")) + ";")

    Path(args.output).write_text("\n".join(statements) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
