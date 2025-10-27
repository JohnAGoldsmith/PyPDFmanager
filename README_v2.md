# PDF Manager Qt - Version 2.0

A Qt-based graphical user interface for the PDF Manager program that manages PDFs with ToK (Tree of Knowledge) indices.

## What's New in Version 2.0

- **Three-panel layout** with adjustable splitters
- **Editable tables** for both files and ToK codes
- **Instant file renaming** - edit index or filename in the table, file updates on disk immediately
- **Instant ToK updates** - edit ToK codes or labels in the table, saves to JSON immediately
- **Automatic backups** - JSON backups created with timestamps before each save

## Features

### Three-Panel Interface

1. **Left Panel - Operations**
   - Scan PDFs with ToK indices
   - Load bare PDF files
   - Load ToK codes
   - Add/Delete ToK entries
   - Folder navigation

2. **Middle Panel - Files Table (Both Columns Editable)**
   - **Index**: The ToK code prefix for the file
   - **Filename**: The rest of the filename
   - When you edit either column, the file is renamed to: `<index> <filename>`
   - Changes apply immediately when you press Enter or click away

3. **Right Panel - ToK Table (Both Columns Editable)**
   - **ToK Code**: The alphanumeric code
   - **Label**: The description/label
   - Changes save to JSON immediately with automatic backup
   - Must be unique and alphanumeric

## Installation

1. Make sure you have Python 3.7+ installed

2. Install the required dependencies:
   ```bash
   pip install PySide6 pypdf
   ```

## Usage

Run the application:
```bash
python pdf_manager_qt_v2.py
```

Or make it executable:
```bash
chmod +x pdf_manager_qt_v2.py
./pdf_manager_qt_v2.py
```

## How to Use

### Initial Setup
1. Click "Load ToK Codes" to load your ToK database
2. Click "Load Bare PDF Files" to load PDF files from the current folder

### Editing Files
1. Load files using "Load Bare PDF Files"
2. Double-click any cell in the Files table
3. Edit the Index (ToK code) or Filename
4. Press Enter or click away - **file is renamed immediately on disk**

**Example:**
- Original file: `myfile.pdf`
- Edit Index to: `A1`
- Edit Filename to: `important-document.pdf`
- Result on disk: `A 1 important-document.pdf`

(Note: The index characters are automatically separated by spaces in the actual filename)

### Editing ToK Codes
1. Load codes using "Load ToK Codes"
2. Double-click any cell in the ToK table
3. Edit the ToK Code or Label
4. Press Enter or click away - **saves to JSON immediately with backup**

**Important:**
- ToK codes must be alphanumeric only
- ToK codes must be unique
- Changes are saved immediately with timestamped backup

### Adding New ToK Entry
1. Click "Add New ToK Entry"
2. Enter the code (alphanumeric)
3. Enter the label
4. Entry is added and saved with backup

### Deleting ToK Entry
1. Click "Delete ToK Entry"
2. Enter the code to delete
3. Confirm deletion
4. Entry is removed and saved with backup

### Scanning PDFs
1. Click "Scan PDFs with ToK Index"
2. Scans your entire Dropbox folder for PDFs with ToK patterns
3. Results saved to `~/Dropbox/coffeetable/pdf-document.txt`

## File Renaming Logic

When you edit the Files table:
- The system takes the **Index** and **Filename** values
- Formats the Index by adding spaces between characters: `A1` → `A 1`
- Creates the new filename: `<formatted_index> <filename>`
- Renames the actual file on disk immediately

**Example transformations:**
- Index: `AB`, Filename: `test.pdf` → File: `A B test.pdf`
- Index: `X2Y`, Filename: `report.pdf` → File: `X 2 Y report.pdf`

## Automatic Backups

Every time you save changes to the ToK database:
- A backup is created: `pdf_manager_tok_init_YYYY-MM-DD_HH-MM-SS.json`
- The backup contains the previous state
- Backups are stored in the same folder as the JSON file
- You can restore from any backup if needed

## Adjustable Layout

All three panels are in a splitter:
- Drag the dividers between panels to adjust widths
- Customize the layout to your preference
- Changes persist during the session

## Requirements

- Python 3.7+
- PySide6 (Qt for Python)
- pypdf
- A Dropbox folder at `~/Dropbox`
- ToK database JSON file at `~/Dropbox/pdfmanager/pdf_manager_tok_init.json`

## File Structure

```
~/Dropbox/
├── pdfmanager/
│   ├── pdf_manager_tok_init.json           # Current ToK database
│   └── pdf_manager_tok_init_*.json         # Automatic backups
├── coffeetable/
│   └── pdf-document.txt                    # Scan results
└── [your PDF files]
```

## Tips

1. **Always load before editing**: Click "Load Bare PDF Files" and "Load ToK Codes" before making edits
2. **Changes are immediate**: No save button needed - edits apply instantly
3. **Check status bar**: Shows confirmation messages for all operations
4. **Backups are automatic**: Every ToK change creates a timestamped backup
5. **Index formatting**: When renaming files, the index gets spaces added automatically (e.g., `AB` → `A B`)

## Troubleshooting

### "Could not find original file"
- Reload the files table by clicking "Load Bare PDF Files"

### "ToK code already exists"
- Each ToK code must be unique
- Edit the existing entry or choose a different code

### "ToK code must be alphanumeric"
- Only letters and numbers allowed in ToK codes
- No spaces, punctuation, or special characters

### Files table empty
- Make sure you're in a folder with PDF files
- Click "Load Bare PDF Files" to refresh
- Use "Go to Coffeetable" to navigate to your PDF folder

### Import errors
```bash
pip install PySide6 pypdf
```

## Advantages Over Version 1

- ✅ **Faster workflow**: Edit directly in tables instead of dialogs
- ✅ **Better visibility**: See all files and ToK codes at once
- ✅ **Immediate feedback**: Changes apply instantly
- ✅ **Adjustable layout**: Customize panel sizes
- ✅ **Safer**: Automatic backups on every change

## License

This is a personal-use tool. Use as needed for managing your PDF collection.
