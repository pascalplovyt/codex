# Thuraya Prepay Airtime Sales

Windows desktop application for importing Thuraya scratchcards, allocating airtime sales, generating Excel/PDF sale files, and tracking inventory and sales history in a local SQLite database.

## Features

- Unified desktop UI with navy/green styling
- Scratchcard import from `.xlsx`
- Inventory list with search, filters, and inline editing
- Sales workflow that allocates unsold cards automatically
- Excel and PDF sale output files saved to the user's Downloads folder
- Sales history and dashboard metrics
- Analytics charts for recent sales and value mix

## Project Files

- `app.py`: Main desktop application
- `requirements.txt`: Python dependencies
- `Install Dependencies.cmd`: Installs required Python packages
- `Launch Thuraya Prepay Airtime Sales.cmd`: Starts the app

## Setup

1. Open `Install Dependencies.cmd`
2. After installation finishes, open `Launch Thuraya Prepay Airtime Sales.cmd`

## Import Template

The importer expects these column names in the source Excel file:

- `serial number`
- `pin number`
- `value`
- `date of purchase`
- `expiry date`
- `supplier`
- `date of sale`
- `number of units sold in that sale`
- `client`
- `dealer`

Notes:

- `serial number` must be 15 digits and unique.
- `pin number` must be 14 digits and unique.
- `supplier` defaults to `Xtralink` when blank.
- Date cells can be real Excel dates or text values.

## Sales Workflow

The sales screen asks for:

- Client name
- Dealer
- Selling date
- Value needed
- Number of units needed

When a sale is submitted, the app:

1. Finds unsold cards matching the requested value
2. Allocates the required quantity
3. Generates an Excel file in Downloads
4. Generates a PDF file in Downloads
5. Updates the chosen rows in the database with the sale metadata
6. Stores a separate sale record for dashboard and analytics reporting

## Filename Format

Windows does not allow `*` in filenames, so sale files use:

- `YYMMDD-ValuexUnits-ClientName.xlsx`
- `YYMMDD-ValuexUnits-ClientName.pdf`

This keeps the intended structure while remaining valid on Windows 11.
