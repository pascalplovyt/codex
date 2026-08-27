import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const input = await FileBlob.load("outputs/home_financing_options/home_financing_options.xlsx");
const workbook = await SpreadsheetFile.importXlsx(input);

const sheets = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 2000,
});
console.log("SHEETS");
console.log(sheets.ndjson);

const comparison = await workbook.inspect({
  kind: "table",
  sheetId: "Comparison",
  range: "A17:C23",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 3,
  maxChars: 3000,
});
console.log("KEY_OUTPUTS");
console.log(comparison.ndjson);

const params = await workbook.inspect({
  kind: "table",
  sheetId: "Parameter Definitions",
  range: "A5:H19",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
  maxChars: 6000,
});
console.log("PARAMETER_DEFINITIONS");
console.log(params.ndjson);

const calc = await workbook.inspect({
  kind: "table",
  sheetId: "Calculation Definitions",
  range: "A4:F18",
  include: "values,formulas",
  tableMaxRows: 18,
  tableMaxCols: 6,
  maxChars: 5000,
});
console.log("CALCULATION_DEFINITIONS");
console.log(calc.ndjson);

const checks = await workbook.inspect({
  kind: "table",
  sheetId: "Checks",
  range: "A3:F9",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 6,
  maxChars: 4000,
});
console.log("CHECKS");
console.log(checks.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "saved workbook formula error scan",
});
console.log("ERROR_SCAN");
console.log(errors.ndjson);
