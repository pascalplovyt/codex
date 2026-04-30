import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error("Usage: node build_schema_workbook.mjs <input.json> <output.xlsx>");
  process.exit(1);
}

const raw = await fs.readFile(inputPath, "utf8");
const data = JSON.parse(raw);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("Tables");
const columnsSheet = workbook.worksheets.add("Columns");
const infoSheet = workbook.worksheets.add("Database");

const tables = (data.tables || []).map((row) => ({
  table_schema: row.table_schema,
  table_name: row.table_name,
  record_count: Number(row.record_count ?? 0),
}));

const columns = (data.columns || []).map((row) => ({
  table_schema: row.table_schema,
  table_name: row.table_name,
  ordinal_position: Number(row.ordinal_position ?? 0),
  column_name: row.column_name,
  data_type: row.data_type,
  udt_name: row.udt_name,
  is_nullable: row.is_nullable,
  column_default: row.column_default,
  character_maximum_length: row.character_maximum_length,
  numeric_precision: row.numeric_precision,
  numeric_scale: row.numeric_scale,
}));

const tableMap = new Map();
for (const column of columns) {
  const key = `${column.table_schema}.${column.table_name}`;
  tableMap.set(key, (tableMap.get(key) || 0) + 1);
}

const summaryRows = [
  ["Schema", "Table", "Field Count", "Record Count"],
  ...tables.map((table) => {
    const key = `${table.table_schema}.${table.table_name}`;
    return [
      table.table_schema,
      table.table_name,
      tableMap.get(key) || 0,
      table.record_count,
    ];
  }),
];

summarySheet.getRange(`A1:D${summaryRows.length}`).values = summaryRows;
summarySheet.tables.add(`A1:D${summaryRows.length}`, true, "SchemaTables");
summarySheet.freezePanes.freezeRows(1);
summarySheet.getRange("A1:D1").format = {
  fill: "#0F4C5C",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
summarySheet.getRange(`D2:D${summaryRows.length}`).format.numberFormat = "#,##0";
summarySheet.getRange(`A1:D${summaryRows.length}`).format.autofitColumns();

const columnRows = [
  [
    "Schema",
    "Table",
    "Position",
    "Column",
    "Data Type",
    "UDT",
    "Nullable",
    "Default",
    "Char Max Length",
    "Numeric Precision",
    "Numeric Scale",
  ],
  ...columns.map((column) => [
    column.table_schema,
    column.table_name,
    column.ordinal_position,
    column.column_name,
    column.data_type,
    column.udt_name,
    column.is_nullable,
    column.column_default,
    column.character_maximum_length,
    column.numeric_precision,
    column.numeric_scale,
  ]),
];

columnsSheet.getRange(`A1:K${columnRows.length}`).values = columnRows;
columnsSheet.tables.add(`A1:K${columnRows.length}`, true, "SchemaColumns");
columnsSheet.freezePanes.freezeRows(1);
columnsSheet.getRange("A1:K1").format = {
  fill: "#1D7874",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
columnsSheet.getRange(`C2:C${columnRows.length}`).format.numberFormat = "0";
columnsSheet.getRange(`I2:K${columnRows.length}`).format.numberFormat = "0";
columnsSheet.getRange(`A1:K${columnRows.length}`).format.wrapText = true;
columnsSheet.getRange(`A1:K${columnRows.length}`).format.autofitColumns();

const db = data.database || {};
const infoRows = [
  ["Property", "Value"],
  ["Database", db.database_name || ""],
  ["Schema", db.schema_name || ""],
  ["Version", db.db_version || ""],
  ["Table Count", tables.length],
  ["Column Count", columns.length],
];
infoSheet.getRange(`A1:B${infoRows.length}`).values = infoRows;
infoSheet.tables.add(`A1:B${infoRows.length}`, true, "DatabaseInfo");
infoSheet.getRange("A1:B1").format = {
  fill: "#274C77",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
infoSheet.getRange("A1:B20").format.wrapText = true;
infoSheet.getRange("A1:B20").format.autofitColumns();

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
