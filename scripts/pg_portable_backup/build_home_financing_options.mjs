import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "outputs/home_financing_options";
const workbook = Workbook.create();

workbook.comments.setSelf({ displayName: "User" });

const inputs = workbook.worksheets.add("Inputs");
const params = workbook.worksheets.add("Parameter Definitions");
const calc = workbook.worksheets.add("Calculation Definitions");
const comparison = workbook.worksheets.add("Comparison");
const checks = workbook.worksheets.add("Checks");

const euroFmt = '€#,##0;[Red](€#,##0);-';
const pctFmt = "0.0%;[Red](0.0%);-";
const wholeFmt = "#,##0;[Red](#,##0);-";

function title(sheet, range, text) {
  const r = sheet.getRange(range);
  r.merge();
  r.values = [[text]];
  r.format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "left",
    verticalAlignment: "middle",
  };
}

function section(sheet, range, text) {
  const r = sheet.getRange(range);
  r.merge();
  r.values = [[text]];
  r.format = {
    fill: "#D9EAF7",
    font: { bold: true, color: "#000000" },
    horizontalAlignment: "left",
  };
}

title(inputs, "A1:D1", "Home Financing Options - Inputs");
inputs.getRange("A2:D2").values = [["Change the blue input cells. Fixed percentages are shown separately for auditability.", "", "", ""]];
inputs.getRange("A2:D2").format = { font: { italic: true, color: "#666666" } };

section(inputs, "A4:D4", "Parametrised Value Assumptions");
inputs.getRange("A5:D11").values = [
  ["Input", "Value", "Units", "Notes"],
  ["Purchase price", 500000, "EUR", "Home purchase price"],
  ["Owner 1 ownership share", 0.5, "%", "Fixed at 50/50 per scenario"],
  ["Owner 2 ownership share", 0.5, "%", "Fixed at 50/50 per scenario"],
  ["Owner 1 capital input", 200000, "EUR", "Cash contributed by owner 1"],
  ["Owner 2 apartment value / sale proceeds", 300000, "EUR", "Retained asset in Scenario 1; cash source in Scenario 2"],
  ["Renovation budget", 250000, "EUR", "Renovation cost to fund"],
];

section(inputs, "A13:D13", "Rental Income");
inputs.getRange("A14:D14").values = [["Input", "Value", "Units", "Notes"]];
inputs.getRange("A15:D15").values = [["Annual rental income if Owner 2 keeps apartment", 12000, "EUR/year", "Scenario 1 income offset"]];
inputs.getRange("A16:D16").values = [["Expected annual capital gain on retained apartment", 0.025, "%", "Scenario 1 non-cash economic benefit"]];

section(inputs, "A17:D17", "Fixed Percentages And Loan Rules");
inputs.getRange("A18:D24").values = [
  ["Fixed input", "Value", "Units", "Notes"],
  ["Owner 1 registration fee rate", 0.02, "%", "Applies to Owner 1's purchase share"],
  ["Owner 2 registration fee rate if apartment kept", 0.12, "%", "Scenario 1"],
  ["Owner 2 registration fee rate if apartment sold", 0.02, "%", "Scenario 2"],
  ["Standard borrowing cost", 0.037, "%", "Annual interest rate"],
  ["Flemish Government loan rate", 0.01, "%", "Applies only to the first EUR 60,000"],
  ["Flemish Government loan cap", 60000, "EUR", "Maximum renovation loan amount"],
];

inputs.getRange("A5:D5").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
inputs.getRange("A14:D14").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
inputs.getRange("A18:D18").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
inputs.getRange("B6:B11").format = { font: { color: "#0000FF" }, fill: "#FFF2CC", numberFormat: euroFmt };
inputs.getRange("B7:B8").format.numberFormat = pctFmt;
inputs.getRange("B15").format = { font: { color: "#0000FF" }, fill: "#FFF2CC", numberFormat: euroFmt };
inputs.getRange("B16").format = { font: { color: "#0000FF" }, fill: "#FFF2CC", numberFormat: pctFmt };
inputs.getRange("B19:B23").format.numberFormat = pctFmt;
inputs.getRange("B24").format.numberFormat = euroFmt;
inputs.getRange("A1:D25").format.borders = { preset: "outside", style: "thin", color: "#A6A6A6" };
inputs.getRange("A5:D11").format.borders = { preset: "inside", style: "thin", color: "#D9D9D9" };
inputs.getRange("A18:D24").format.borders = { preset: "inside", style: "thin", color: "#D9D9D9" };
inputs.getRange("A:D").format.wrapText = true;
inputs.getRange("A:A").format.columnWidth = 42;
inputs.getRange("B:B").format.columnWidth = 18;
inputs.getRange("C:C").format.columnWidth = 14;
inputs.getRange("D:D").format.columnWidth = 58;
inputs.freezePanes.freezeRows(5);
inputs.showGridLines = false;

const commentTexts = {
  B6: "Editable value assumption. Formulas in the Comparison sheet reference this cell.",
  B9: "Owner 1 cash contribution used to reduce borrowing in both scenarios.",
  B10: "Scenario 2 assumes sale proceeds are available to reduce borrowing.",
  B11: "Renovation budget also determines the cap-eligible amount for the special loan.",
  B15: "Scenario 1 rental income is netted against annual financing cost before tax.",
  B16: "Scenario 1 expected capital gain is calculated as retained apartment value times this annual rate.",
};
for (const [cell, text] of Object.entries(commentTexts)) {
  workbook.comments.addThread({ cell: inputs.getRange(cell) }, text);
}

title(params, "A1:H1", "Parameter Definitions");
params.getRange("A2:H2").values = [["This tab documents every editable and fixed parameter so the workbook can be shared as a standalone model.", "", "", "", "", "", "", ""]];
params.getRange("A2:H2").format = { font: { italic: true, color: "#666666" } };

section(params, "A4:H4", "Model Parameters");
params.getRange("A5:H19").values = [
  ["Code", "Parameter", "Current value", "Status", "Units", "Definition", "Where used", "Notes"],
  ["P", "Purchase price", null, "Editable", "EUR", "Agreed price of the home being purchased.", "Registration fees, borrowing need", "Change on Inputs tab."],
  ["S1", "Owner 1 ownership share", null, "Fixed", "%", "Owner 1's legal/economic share of the purchased home.", "Registration fee allocation", "Set to 50% per prompt."],
  ["S2", "Owner 2 ownership share", null, "Fixed", "%", "Owner 2's legal/economic share of the purchased home.", "Registration fee allocation", "Set to 50% per prompt."],
  ["C1", "Owner 1 capital input", null, "Editable", "EUR", "Cash contributed by Owner 1 toward the project.", "Borrowing need in both scenarios", "Reduces standard borrowing."],
  ["A", "Owner 2 apartment value / sale proceeds", null, "Editable", "EUR", "Existing apartment value; sale proceeds in Scenario 2.", "Scenario text and Scenario 2 borrowing", "Scenario 1 keeps this as an asset."],
  ["R", "Renovation budget", null, "Editable", "EUR", "Expected renovation spending for the purchased home.", "Borrowing need and Flemish loan cap test", "Can be changed independently of purchase price."],
  ["Rent", "Annual rental income", null, "Editable", "EUR/year", "Annual income from Owner 2's existing apartment if retained.", "Scenario 1 net annual financing cost", "Shown before tax and operating-cost adjustments."],
  ["g_apartment", "Expected annual apartment capital gain", null, "Editable", "%", "Expected annual appreciation rate for the retained apartment.", "Scenario 1 economic benefit", "Default 2.5%; non-cash and before sale-tax effects."],
  ["T1", "Owner 1 registration fee rate", null, "Fixed", "%", "Registration fee rate applied to Owner 1's ownership share.", "Owner 1 registration fee", "Fixed at 2% per prompt."],
  ["T2_keep", "Owner 2 registration fee rate if apartment kept", null, "Fixed", "%", "Owner 2 share fee rate if the apartment is kept.", "Scenario 1 Owner 2 registration fee", "Fixed at 12% per prompt."],
  ["T2_sell", "Owner 2 registration fee rate if apartment sold", null, "Fixed", "%", "Owner 2 share fee rate if the apartment is sold.", "Scenario 2 Owner 2 registration fee", "Fixed at 2% per prompt."],
  ["i_std", "Standard borrowing cost", null, "Fixed", "%", "Annual interest rate for ordinary bank borrowing.", "Annual standard-loan interest", "Fixed at 3.7% per prompt."],
  ["i_gov", "Flemish Government loan rate", null, "Fixed", "%", "Interest rate on the first EUR 60,000 of renovation borrowing.", "Scenario 2 special-loan interest", "Fixed at 1%; applies only up to the cap."],
  ["G_cap", "Flemish Government loan cap", null, "Fixed", "EUR", "Maximum eligible amount for the special Flemish renovation loan.", "Scenario 2 special loan amount", "Fixed at up to EUR 60,000 per prompt."],
];
params.getRange("C6:C19").formulas = [
  ["='Inputs'!$B$6"],
  ["='Inputs'!$B$7"],
  ["='Inputs'!$B$8"],
  ["='Inputs'!$B$9"],
  ["='Inputs'!$B$10"],
  ["='Inputs'!$B$11"],
  ["='Inputs'!$B$15"],
  ["='Inputs'!$B$16"],
  ["='Inputs'!$B$19"],
  ["='Inputs'!$B$20"],
  ["='Inputs'!$B$21"],
  ["='Inputs'!$B$22"],
  ["='Inputs'!$B$23"],
  ["='Inputs'!$B$24"],
];

params.getRange("A5:H5").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, wrapText: true };
params.getRange("C6:C19").format = { font: { color: "#008000" } };
params.getRange("D6:D19").conditionalFormats.add("containsText", { text: "Editable", format: { fill: "#FFF2CC", font: { color: "#0000FF", bold: true } } });
params.getRange("D6:D19").conditionalFormats.add("containsText", { text: "Fixed", format: { fill: "#E7E6E6", font: { color: "#000000" } } });
params.getRange("C6:C6").format.numberFormat = euroFmt;
params.getRange("C7:C8").format.numberFormat = pctFmt;
params.getRange("C9:C12").format.numberFormat = euroFmt;
params.getRange("C13:C18").format.numberFormat = pctFmt;
params.getRange("C19:C19").format.numberFormat = euroFmt;
params.getRange("A5:H19").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
params.getRange("A:H").format.wrapText = true;
params.getRange("A:A").format.columnWidth = 16;
params.getRange("B:B").format.columnWidth = 44;
params.getRange("C:C").format.columnWidth = 18;
params.getRange("D:D").format.columnWidth = 16;
params.getRange("E:E").format.columnWidth = 14;
params.getRange("F:F").format.columnWidth = 58;
params.getRange("G:G").format.columnWidth = 48;
params.getRange("H:H").format.columnWidth = 58;
params.getRange("5:5").format.rowHeight = 30;
params.getRange("6:19").format.rowHeight = 34;
params.freezePanes.freezeRows(5);
params.showGridLines = false;

title(calc, "A1:F1", "Calculation Definitions");
calc.getRange("A2:F2").values = [["This tab explains how the scenario comparison is calculated from the parameters. It is documentation only; live formulas are on the Comparison tab.", "", "", "", "", ""]];
calc.getRange("A2:F2").format = { font: { italic: true, color: "#666666" } };
calc.getRange("A4:F4").values = [["Output", "Scenario 1 formula", "Scenario 2 formula", "Units", "Interpretation", "Important limitation"]];
calc.getRange("A5:F18").values = [
  ["Owner 1 registration fee", "P x S1 x T1", "P x S1 x T1", "EUR", "Same in both scenarios.", "Assumes fee applies to each partner's 50% purchase share."],
  ["Owner 2 registration fee", "P x S2 x T2_keep", "P x S2 x T2_sell", "EUR", "Lower in Scenario 2 because the rate changes from 12% to 2%.", "Does not include notary or other acquisition costs."],
  ["Total registration fees", "Owner 1 fee + Owner 2 fee", "Owner 1 fee + Owner 2 fee", "EUR", "Scenario 2 saving is Scenario 1 total less Scenario 2 total.", "Tax treatment not modeled."],
  ["Borrowing before special loan", "MAX(0, P + R - C1)", "MAX(0, P + R - C1 - A)", "EUR", "Scenario 2 uses apartment sale proceeds to reduce debt.", "Assumes sale proceeds are fully available for the project."],
  ["Special Flemish renovation loan", "0", "MIN(G_cap, R, borrowing before special loan)", "EUR", "Capped at EUR 60,000, renovation spend, and remaining borrowing need.", "Eligibility criteria beyond the prompt are not modeled."],
  ["Standard loan after special loan", "Borrowing before special loan", "Borrowing before special loan - special loan", "EUR", "This is the base for 3.7% interest.", "Principal amortization is not modeled."],
  ["Annual standard-loan interest", "Standard loan x i_std", "Standard loan x i_std", "EUR/year", "Uses the fixed 3.7% rate.", "Interest-only comparison before tax."],
  ["Annual special-loan interest", "0", "Special loan x i_gov", "EUR/year", "Applies the 1% special rate to only the first EUR 60,000.", "Does not model repayment timing."],
  ["Rental income offset", "Rent", "0", "EUR/year", "Reduces Scenario 1 net annual financing cost.", "Before tax, vacancy, maintenance, and service charges."],
  ["Expected apartment capital gain", "A x g_apartment", "0", "EUR/year", "Adds expected appreciation to Scenario 1 economic benefit.", "Non-cash estimate; excludes market risk and sale-tax effects."],
  ["Net annual financing cost", "Standard interest + special interest - Rent", "Standard interest + special interest", "EUR/year", "Uses 3.7% standard debt plus 1% on the special loan.", "Before tax and principal repayment."],
  ["Annual economic cost after capital gain", "Net financing cost - expected capital gain", "Net financing cost", "EUR/year", "Shows annual cost after rent and expected appreciation.", "Capital gain is estimated and unrealized until sale."],
  ["Annual financing advantage", "0 baseline", "Scenario 1 net cost - Scenario 2 net cost", "EUR/year", "Positive value means Scenario 2 has lower annual financing cost.", "Excludes retained apartment appreciation or sale-tax effects."],
  ["Annual economic advantage after capital gain", "0 baseline", "S1 economic cost - S2 economic cost", "EUR/year", "Positive value means Scenario 2 is better after capital gain.", "Depends heavily on the capital-gain estimate."],
];
calc.getRange("A4:F4").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, wrapText: true };
calc.getRange("A4:F18").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
calc.getRange("A:F").format.wrapText = true;
calc.getRange("A:A").format.columnWidth = 48;
calc.getRange("B:C").format.columnWidth = 38;
calc.getRange("D:D").format.columnWidth = 14;
calc.getRange("E:F").format.columnWidth = 60;
calc.getRange("4:4").format.rowHeight = 32;
calc.getRange("5:18").format.rowHeight = 54;
calc.freezePanes.freezeRows(4);
calc.showGridLines = false;

title(comparison, "A1:D1", "Scenario Comparison");
comparison.getRange("A3:D3").values = [["Metric", "Scenario 1: Owner 2 keeps apartment", "Scenario 2: Owner 2 sells apartment", "Formula / interpretation"]];
comparison.getRange("A3:D3").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, wrapText: true };

comparison.getRange("A4:A23").values = [
  ["Purchase price"],
  ["Ownership split"],
  ["Owner 1 capital input"],
  ["Owner 2 existing apartment / sale proceeds"],
  ["Renovation budget"],
  ["Owner 1 registration fee"],
  ["Owner 2 registration fee"],
  ["Total registration fees"],
  ["Total standard borrowing before special loan"],
  ["Special Flemish renovation loan"],
  ["Standard loan after special loan"],
  ["Annual standard-loan interest"],
  ["Annual special-loan interest"],
  ["Rental income offset"],
  ["Expected apartment capital gain"],
  ["Net annual financing cost"],
  ["Annual economic cost after capital gain"],
  ["One-off registration fee saving vs Scenario 1"],
  ["Annual financing advantage vs Scenario 1"],
  ["Annual economic advantage after capital gain"],
];

comparison.getRange("B4:C23").formulas = [
  ["='Inputs'!$B$6", "='Inputs'!$B$6"],
  ['=TEXT(\'Inputs\'!$B$7,"0%")&" / "&TEXT(\'Inputs\'!$B$8,"0%")', '=TEXT(\'Inputs\'!$B$7,"0%")&" / "&TEXT(\'Inputs\'!$B$8,"0%")'],
  ["='Inputs'!$B$9", "='Inputs'!$B$9"],
  ['="Keeps asset worth "&TEXT(\'Inputs\'!$B$10,"€#,##0")', '="Sells asset: "&TEXT(\'Inputs\'!$B$10,"€#,##0")'],
  ["='Inputs'!$B$11", "='Inputs'!$B$11"],
  ["='Inputs'!$B$6*'Inputs'!$B$7*'Inputs'!$B$19", "='Inputs'!$B$6*'Inputs'!$B$7*'Inputs'!$B$19"],
  ["='Inputs'!$B$6*'Inputs'!$B$8*'Inputs'!$B$20", "='Inputs'!$B$6*'Inputs'!$B$8*'Inputs'!$B$21"],
  ["=SUM(B9:B10)", "=SUM(C9:C10)"],
  ["=MAX(0,'Inputs'!$B$6+'Inputs'!$B$11-'Inputs'!$B$9)", "=MAX(0,'Inputs'!$B$6+'Inputs'!$B$11-'Inputs'!$B$9-'Inputs'!$B$10)"],
  ["=0", "=MIN('Inputs'!$B$24,'Inputs'!$B$11,C12)"],
  ["=B12-B13", "=C12-C13"],
  ["=B14*'Inputs'!$B$22", "=C14*'Inputs'!$B$22"],
  ["=B13*'Inputs'!$B$23", "=C13*'Inputs'!$B$23"],
  ["='Inputs'!$B$15", "=0"],
  ["='Inputs'!$B$10*'Inputs'!$B$16", "=0"],
  ["=B15+B16-B17", "=C15+C16-C17"],
  ["=B19-B18", "=C19-C18"],
  ["=0", "=B11-C11"],
  ["=0", "=B19-C19"],
  ["=0", "=B20-C20"],
];

comparison.getRange("D4:D23").values = [
  ["Linked from purchase price input"],
  ["Fixed ownership split"],
  ["Linked from Owner 1 capital input"],
  ["Scenario wording driven by property value input"],
  ["Linked from renovation budget input"],
  ["Purchase price x Owner 1 share x 2%"],
  ["Purchase price x Owner 2 share x scenario registration rate"],
  ["Owner 1 registration fee + Owner 2 registration fee"],
  ["Purchase + renovation less available cash proceeds, before special loan"],
  ["Scenario 2 only, capped at Flemish loan cap and renovation budget"],
  ["Standard borrowing after special loan"],
  ["Standard loan x 3.7%"],
  ["Special loan x 1%"],
  ["Rental income offsets Scenario 1 financing cost"],
  ["Retained apartment value x expected annual capital-gain rate"],
  ["Standard interest + special-loan interest - rental income"],
  ["Net annual financing cost less expected capital gain"],
  ["Scenario 1 fees less Scenario 2 fees"],
  ["Scenario 1 net cost less Scenario 2 net cost"],
  ["Scenario 1 economic cost less Scenario 2 economic cost"],
];

comparison.getRange("A4:A23").format = { font: { bold: true } };
comparison.getRange("B4:C4").format.numberFormat = euroFmt;
comparison.getRange("B6:C6").format.numberFormat = euroFmt;
comparison.getRange("B8:C23").format.numberFormat = euroFmt;
comparison.getRange("B5:C5").format.numberFormat = "@";
comparison.getRange("B7:C7").format.numberFormat = "@";
comparison.getRange("A3:D23").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
comparison.getRange("A17:C20").format = { fill: "#E2F0D9", font: { bold: true }, numberFormat: euroFmt };
comparison.getRange("A21:C23").format = { fill: "#DDEBF7", font: { bold: true }, numberFormat: euroFmt };
comparison.getRange("D4:D23").format = { font: { color: "#666666" }, wrapText: true };
comparison.getRange("A:D").format.wrapText = true;
comparison.getRange("A:A").format.columnWidth = 52;
comparison.getRange("B:C").format.columnWidth = 38;
comparison.getRange("D:D").format.columnWidth = 64;
comparison.getRange("3:3").format.rowHeight = 34;
comparison.getRange("21:23").format.rowHeight = 32;
comparison.freezePanes.freezeRows(3);
comparison.showGridLines = false;

title(checks, "A1:F1", "Model Checks");
checks.getRange("A3:F3").values = [["Check", "Actual", "Expected", "Difference", "Tolerance", "Status"]];
checks.getRange("A3:F3").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
checks.getRange("A4:A9").values = [
  ["Ownership adds to 100%"],
  ["Scenario 2 standard borrowing is non-negative"],
  ["Scenario 2 special loan does not exceed cap"],
  ["Registration saving ties to total registration fees"],
  ["Special-loan interest equals special loan x 1% rate"],
  ["Capital gain equals apartment value x capital gain rate"],
];
checks.getRange("B4:E9").formulas = [
  ["='Inputs'!$B$7+'Inputs'!$B$8", "=1", "=B4-C4", "=0.000001"],
  ["='Comparison'!$C$12", "=MAX(0,'Comparison'!$C$12)", "=B5-C5", "=0"],
  ["='Comparison'!$C$13", "='Inputs'!$B$24", "=MAX(0,B6-C6)", "=0"],
  ["='Comparison'!$C$21", "='Comparison'!$B$11-'Comparison'!$C$11", "=B7-C7", "=0.01"],
  ["='Comparison'!$C$16", "='Comparison'!$C$13*'Inputs'!$B$23", "=B8-C8", "=0.01"],
  ["='Comparison'!$B$18", "='Inputs'!$B$10*'Inputs'!$B$16", "=B9-C9", "=0.01"],
];
checks.getRange("F4:F9").formulas = [
  ['=IF(ABS(D4)<=E4,"OK","Check")'],
  ['=IF(ABS(D5)<=E5,"OK","Check")'],
  ['=IF(ABS(D6)<=E6,"OK","Check")'],
  ['=IF(ABS(D7)<=E7,"OK","Check")'],
  ['=IF(ABS(D8)<=E8,"OK","Check")'],
  ['=IF(ABS(D9)<=E9,"OK","Check")'],
];
checks.getRange("B4:E4").format.numberFormat = pctFmt;
checks.getRange("B5:E9").format.numberFormat = euroFmt;
checks.getRange("A3:F9").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
checks.getRange("F4:F9").conditionalFormats.add("containsText", { text: "OK", format: { fill: "#C6EFCE", font: { color: "#006100" } } });
checks.getRange("F4:F9").conditionalFormats.add("containsText", { text: "Check", format: { fill: "#FFC7CE", font: { color: "#9C0006" } } });
checks.getRange("A:A").format.columnWidth = 44;
checks.getRange("B:E").format.columnWidth = 16;
checks.getRange("F:F").format.columnWidth = 14;
checks.showGridLines = false;

const summaryInspect = await workbook.inspect({
  kind: "table",
  sheetId: "Comparison",
  range: "A3:D23",
  include: "values,formulas",
  tableMaxRows: 25,
  tableMaxCols: 4,
  maxChars: 7000,
});
console.log("COMPARISON_INSPECT");
console.log(summaryInspect.ndjson);

const checkInspect = await workbook.inspect({
  kind: "table",
  sheetId: "Checks",
  range: "A3:F9",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 6,
  maxChars: 4000,
});
console.log("CHECKS_INSPECT");
console.log(checkInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log("ERROR_SCAN");
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
for (const sheetName of ["Inputs", "Parameter Definitions", "Calculation Definitions", "Comparison", "Checks"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${sheetName.toLowerCase().replaceAll(" ", "_")}_preview.png`, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/home_financing_options.xlsx`);
console.log(`${outputDir}/home_financing_options.xlsx`);
