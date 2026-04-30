import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error("Usage: node build_data_report.mjs <input.json> <output.xlsx>");
  process.exit(1);
}

const raw = await fs.readFile(inputPath, "utf8");
const data = JSON.parse(raw);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("Summary");
summarySheet.showGridLines = false;

summarySheet.getRange("A1:F1").merge();
summarySheet.getRange("A1").values = [[data.report_name || "Data Explorer Report"]];
summarySheet.getRange("A1").format = {
  fill: "#0F4C5C",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "left",
  verticalAlignment: "center",
};

const metaRows = [
  ["Generated At", data.generated_at || ""],
  ["Selections", (data.sheets || []).length],
  ["Export Limit Per Sheet", Number(data.export_limit || 0)],
];
summarySheet.getRange(`A3:B${metaRows.length + 2}`).values = metaRows;
summarySheet.getRange("A3:A5").format = {
  fill: "#EAF4F4",
  font: { bold: true, color: "#0F4C5C" },
};

const summaryRows = [
  ["Object", "Type", "Filters", "Sort", "Total Rows", "Rows Exported", "Truncated"],
  ...((data.summary_rows || []).map((row) => [
    row[0],
    row[1],
    row[2],
    `${row[3] || ""} ${row[4] || ""}`.trim(),
    Number(row[5] || 0),
    Number(row[6] || 0),
    row[7],
  ])),
];

summarySheet.getRange(`A7:G${summaryRows.length + 6}`).values = summaryRows;
summarySheet.tables.add(`A7:G${summaryRows.length + 6}`, true, "ReportSelections");
summarySheet.freezePanes.freezeRows(7);
summarySheet.getRange("A7:G7").format = {
  fill: "#1D7874",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
summarySheet.getRange(`E8:F${summaryRows.length + 6}`).format.numberFormat = "#,##0";
summarySheet.getRange("A1:G40").format.wrapText = true;
summarySheet.getRange("A1:G40").format.autofitColumns();

for (const [index, sheetInfo] of (data.sheets || []).entries()) {
  const sheet = workbook.worksheets.add(sheetInfo.sheet_name || `Selection ${index + 1}`);
  sheet.showGridLines = false;

  sheet.getRange("A1:F1").merge();
  sheet.getRange("A1").values = [[sheetInfo.title || sheetInfo.sheet_name || `Selection ${index + 1}`]];
  sheet.getRange("A1").format = {
    fill: "#274C77",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "left",
  };

  const infoRows = [
    ["Object Type", sheetInfo.object_type || ""],
    ["Filters", sheetInfo.filters_text || "No filters"],
    ["Sort", sheetInfo.sort_text || ""],
    ["Total Rows", Number(sheetInfo.row_count || 0)],
    ["Rows Exported", Number(sheetInfo.rows_exported || 0)],
    ["Truncated", sheetInfo.truncated ? "Yes" : "No"],
  ];
  sheet.getRange(`A3:B${infoRows.length + 2}`).values = infoRows;
  sheet.getRange(`A3:A${infoRows.length + 2}`).format = {
    fill: "#F3EADF",
    font: { bold: true, color: "#213039" },
  };

  const rows = sheetInfo.rows || [];
  if (rows.length) {
    const columnCount = rows[0].length;
    const lastColumn = columnName(columnCount);
    sheet.getRange(`A10:${lastColumn}${rows.length + 9}`).values = rows;
    sheet.tables.add(`A10:${lastColumn}${rows.length + 9}`, true, `Selection${index + 1}`);
    sheet.freezePanes.freezeRows(10);
    sheet.getRange(`A10:${lastColumn}10`).format = {
      fill: "#0F4C5C",
      font: { bold: true, color: "#FFFFFF" },
      horizontalAlignment: "center",
    };
    sheet.getRange(`A10:${lastColumn}${rows.length + 9}`).format.wrapText = true;
    sheet.getRange(`A10:${lastColumn}${Math.min(rows.length + 9, 40)}`).format.autofitColumns();
  } else {
    sheet.getRange("A10").values = [["No rows matched this selection."]];
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

function columnName(index) {
  let current = index;
  let label = "";
  while (current > 0) {
    const remainder = (current - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    current = Math.floor((current - 1) / 26);
  }
  return label;
}
