#!/usr/bin/env python3
"""
PDF Manager Qt - GUI wrapper for PDF Manager using PySide6
Version 2.7 - Three columns: #, ToK Index, Filename
"""

import os
import re
import warnings
import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QInputDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox, QLineEdit, QFormLayout, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

# Suppress pypdf warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pypdf')
warnings.filterwarnings('ignore')
logging.getLogger('pypdf').setLevel(logging.ERROR)


class WorkerThread(QThread):
    """Worker thread for long-running operations"""
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class PDFManager:
    """Core PDF Manager functionality"""
    
    def __init__(self):
        self.bare_pdf_files = {}  # Maps display index to actual filename
        self.tok_data = {}  # In-memory ToK data
        self.home = Path.home()
        self.dropbox_path = self.home / "Dropbox"
        self.json_file = self.dropbox_path / "pdfmanager" / "pdf_manager_tok_init.json"
    
    @staticmethod
    def matches_pattern(filename):
        """Check if filename starts with pattern: 2+ pairs of (alphanumeric + space)"""
        pattern = r'^([a-zA-Z0-9] ){2,}'
        match = re.match(pattern, filename)
        if match:
            return match.group(0).strip()
        return None
    
    @staticmethod
    def get_pdf_title(pdf_path):
        """Extract the title from PDF metadata"""
        try:
            reader = PdfReader(pdf_path)
            metadata = reader.metadata
            if metadata and metadata.title:
                return metadata.title
            return ""
        except Exception as e:
            return f"[Error: {str(e)}]"
    
    def scan_pdfs(self):
        """Scan all PDFs in dropbox_path that match the pattern"""
        results = []
        
        for root, dirs, files in os.walk(self.dropbox_path):
            if 'RAG' in dirs:
                dirs.remove('RAG')
            
            for file in files:
                if file.lower().endswith('.pdf'):
                    pattern = self.matches_pattern(file)
                    if pattern:
                        filename_remainder = file[len(pattern):].strip()
                        full_path = os.path.join(root, file)
                        relative_folder = os.path.relpath(root, self.dropbox_path)
                        if relative_folder == '.':
                            relative_folder = '[root]'
                        
                        internal_title = self.get_pdf_title(full_path)
                        results.append((pattern, filename_remainder, relative_folder, internal_title))
        
        return results
    
    def load_tok_data(self):
        """Load ToK data from JSON file into memory"""
        if not self.json_file.exists():
            raise FileNotFoundError(f"JSON file not found at {self.json_file}")
        
        with open(self.json_file, 'r', encoding='utf-8') as f:
            self.tok_data = json.load(f)
        
        if 'ToK' not in self.tok_data:
            raise KeyError("'ToK' key not found in JSON file")
        
        return self.tok_data['ToK']
    
    def save_tok_data(self):
        """Save in-memory ToK data to JSON file with backup"""
        # Create backup
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"pdf_manager_tok_init_{timestamp}.json"
        backup_path = self.json_file.parent / backup_filename
        
        if self.json_file.exists():
            os.rename(self.json_file, backup_path)
        
        # Save new data
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(self.tok_data, f, indent=4, ensure_ascii=False)
        
        return backup_filename
    
    def update_tok_entry(self, old_code, new_code, new_label):
        """Update a ToK entry in memory"""
        # Find and update the entry
        for item in self.tok_data['ToK']:
            if item.get('prefix') == old_code:
                item['prefix'] = new_code
                item['string'] = new_label
                return True
        return False
    
    def add_tok_entry(self, code, label):
        """Add a new ToK entry"""
        new_entry = {"prefix": code, "string": label}
        self.tok_data['ToK'].append(new_entry)
        self.tok_data['ToK'].sort(key=lambda x: x.get('prefix', ''))
    
    def delete_tok_entry(self, code):
        """Delete a ToK entry"""
        for item in self.tok_data['ToK']:
            if item.get('prefix') == code:
                self.tok_data['ToK'].remove(item)
                return True
        return False
    
    def get_bare_pdfs(self, current_dir):
        """Get bare PDF files (without ToK pattern) in specified folder"""
        pdf_files = [f for f in os.listdir(current_dir) 
                     if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(current_dir, f))]
        
        bare_pdfs = [f for f in pdf_files if not self.matches_pattern(f)]
        
        if not bare_pdfs:
            return []
        
        # Sort by modification time, most recent first
        bare_pdfs_with_time = [(f, os.path.getmtime(os.path.join(current_dir, f))) for f in bare_pdfs]
        bare_pdfs_with_time.sort(key=lambda x: x[1], reverse=True)
        
        # Get all files (no limit)
        bare_pdfs_sorted = [f for f, mtime in bare_pdfs_with_time]
        
        # Store with display index starting at 1
        self.bare_pdf_files = {}
        for idx, filename in enumerate(bare_pdfs_sorted, start=1):
            self.bare_pdf_files[idx] = filename
        
        return list(self.bare_pdf_files.items())


class PDFManagerWindow(QMainWindow):
    """Main window for PDF Manager Qt"""
    
    def __init__(self):
        super().__init__()
        self.manager = PDFManager()
        self.current_dir = os.getcwd()
        self.files_being_edited = set()  # Track which files are currently being edited
        self.tok_being_edited = set()  # Track which ToK entries are being edited
        self.table_font_size = 9  # Default font size for tables
        self.init_ui()
        
        # Auto-load ToK codes on startup
        try:
            self.load_tok_codes()
        except:
            pass  # Silently fail if ToK data not available
    
    def init_ui(self):
        self.setWindowTitle("PDF Manager - Tree of Knowledge (ToK) System")
        self.setMinimumSize(1400, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # No margins at top
        
        # Three-way splitter (goes to the very top)
        splitter = QSplitter(Qt.Horizontal)
        
        # ===== LEFT PANEL - Buttons =====
        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        button_layout.setAlignment(Qt.AlignTop)
        
        # Set larger font for all buttons
        button_font = QFont()
        button_font.setPointSize(11)  # Larger font for buttons
        
        # Section label
        btn_label = QLabel("Operations")
        btn_label_font = QFont()
        btn_label_font.setBold(True)
        btn_label_font.setPointSize(12)
        btn_label.setFont(btn_label_font)
        button_layout.addWidget(btn_label)
        
        # Create buttons
        btn_scan = QPushButton("Scan PDFs\nwith ToK Index")
        btn_scan.setFont(button_font)
        btn_scan.clicked.connect(self.scan_pdfs)
        button_layout.addWidget(btn_scan)
        
        btn_bare_pdfs = QPushButton("Load Bare\nPDF Files")
        btn_bare_pdfs.setFont(button_font)
        btn_bare_pdfs.clicked.connect(self.show_bare_pdfs)
        button_layout.addWidget(btn_bare_pdfs)
        
        button_layout.addSpacing(20)
        
        btn_add_prefix = QPushButton("Add ToK Prefix\nto Selected File")
        btn_add_prefix.setFont(button_font)
        btn_add_prefix.clicked.connect(self.add_tok_prefix_to_file)
        button_layout.addWidget(btn_add_prefix)
        
        button_layout.addSpacing(20)
        
        btn_add_tok = QPushButton("Add New\nToK Entry")
        btn_add_tok.setFont(button_font)
        btn_add_tok.clicked.connect(self.add_to_tok)
        button_layout.addWidget(btn_add_tok)
        
        btn_delete_tok = QPushButton("Delete\nToK Entry")
        btn_delete_tok.setFont(button_font)
        btn_delete_tok.clicked.connect(self.delete_from_tok)
        button_layout.addWidget(btn_delete_tok)
        
        button_layout.addSpacing(20)
        
        # Font size controls
        font_label = QLabel("Font Size")
        font_label.setFont(btn_label_font)
        button_layout.addWidget(font_label)
        
        btn_increase_font = QPushButton("Increase Font")
        btn_increase_font.setFont(button_font)
        btn_increase_font.clicked.connect(self.increase_font_size)
        button_layout.addWidget(btn_increase_font)
        
        btn_decrease_font = QPushButton("Decrease Font")
        btn_decrease_font.setFont(button_font)
        btn_decrease_font.clicked.connect(self.decrease_font_size)
        button_layout.addWidget(btn_decrease_font)
        
        button_layout.addSpacing(20)
        
        btn_show_folder = QPushButton("Show Current\nFolder")
        btn_show_folder.setFont(button_font)
        btn_show_folder.clicked.connect(self.show_current_folder)
        button_layout.addWidget(btn_show_folder)
        
        btn_goto_coffee = QPushButton("Go to\nCoffeetable")
        btn_goto_coffee.setFont(button_font)
        btn_goto_coffee.clicked.connect(self.go_to_coffeetable)
        button_layout.addWidget(btn_goto_coffee)
        
        button_layout.addStretch()
        
        # ===== MIDDLE PANEL - Files Table =====
        files_panel = QWidget()
        files_layout = QVBoxLayout(files_panel)
        
        files_label = QLabel("PDF Files (Editable)")
        files_label_font = QFont()
        files_label_font.setBold(True)
        files_label.setFont(files_label_font)
        files_layout.addWidget(files_label)
        
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["#", "ToK Index", "Filename"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.files_table.setFont(QFont("Courier", self.table_font_size))
        self.files_table.setSelectionBehavior(QTableWidget.SelectRows)  # Select entire rows
        self.files_table.itemChanged.connect(self.on_file_item_changed)
        files_layout.addWidget(self.files_table)
        
        # ===== RIGHT PANEL - ToK Table =====
        tok_panel = QWidget()
        tok_layout = QVBoxLayout(tok_panel)
        
        tok_label = QLabel("ToK Codes (Editable)")
        tok_label_font = QFont()
        tok_label_font.setBold(True)
        tok_label.setFont(tok_label_font)
        tok_layout.addWidget(tok_label)
        
        self.tok_table = QTableWidget()
        self.tok_table.setColumnCount(2)
        self.tok_table.setHorizontalHeaderLabels(["ToK Code", "Label"])
        self.tok_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tok_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tok_table.setFont(QFont("Courier", self.table_font_size))
        self.tok_table.setSelectionBehavior(QTableWidget.SelectRows)  # Select entire rows
        self.tok_table.itemChanged.connect(self.on_tok_item_changed)
        tok_layout.addWidget(self.tok_table)
        
        # Add all panels to splitter
        splitter.addWidget(button_widget)
        splitter.addWidget(files_panel)
        splitter.addWidget(tok_panel)
        
        # Set initial sizes (roughly 1:2:2 ratio)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        
        main_layout.addWidget(splitter)
        
        # Progress label for long operations
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("padding: 2px; background-color: #ffffcc; color: #cc6600;")
        self.progress_label.setMaximumHeight(25)
        self.progress_label.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.progress_label)
        
        # Current folder display at the bottom (minimal height)
        self.folder_label = QLabel(f"Current Folder: {self.current_dir}")
        self.folder_label.setStyleSheet("padding: 2px; background-color: #f0f0f0;")
        self.folder_label.setMaximumHeight(25)  # Limit height
        main_layout.addWidget(self.folder_label)
        
        # Status bar
        self.statusBar().showMessage("Ready - Load files to begin")
    
    def show_message(self, title, message, icon=QMessageBox.Information):
        """Show a message box"""
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec()
    
    def increase_font_size(self):
        """Increase font size in both tables"""
        if self.table_font_size < 20:  # Max size
            self.table_font_size += 1
            self.update_table_fonts()
            self.statusBar().showMessage(f"Font size: {self.table_font_size}")
    
    def decrease_font_size(self):
        """Decrease font size in both tables"""
        if self.table_font_size > 6:  # Min size
            self.table_font_size -= 1
            self.update_table_fonts()
            self.statusBar().showMessage(f"Font size: {self.table_font_size}")
    
    def update_table_fonts(self):
        """Update font size for both tables"""
        font = QFont("Courier", self.table_font_size)
        self.files_table.setFont(font)
        self.tok_table.setFont(font)
    
    def scan_pdfs(self):
        """Scan PDFs and create list"""
        self.progress_label.setText("Scanning PDFs in Dropbox folder... Please wait...")
        self.progress_label.setVisible(True)
        self.statusBar().showMessage("Scanning PDFs...")
        QApplication.processEvents()
        
        if not self.manager.dropbox_path.exists():
            self.progress_label.setVisible(False)
            self.show_message("Error", f"Dropbox folder not found at {self.manager.dropbox_path}", 
                            QMessageBox.Critical)
            return
        
        # Use worker thread for long operation
        self.worker = WorkerThread(self.manager.scan_pdfs)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()
    
    def on_scan_finished(self, results):
        """Handle scan completion"""
        # Hide progress indicator
        self.progress_label.setVisible(False)
        
        if not results:
            self.show_message("Scan Complete", "No PDFs matching the pattern were found.")
            self.statusBar().showMessage("Scan complete - no results")
            self.files_table.setRowCount(0)
            return
        
        # Write to file
        output_dir = self.manager.dropbox_path / "coffeetable"
        output_dir.mkdir(exist_ok=True)
        output_file_path = output_dir / "pdf-document.txt"
        
        # Format results for file
        col1_width = max(len(r[0]) for r in results) + 2
        col2_width = max(len(r[1]) for r in results) + 2
        col3_width = max(len(r[2]) for r in results) + 2
        
        col1_width = max(col1_width, 10)
        col2_width = max(col2_width, 20)
        col3_width = max(col3_width, 20)
        
        output_text = f"{'Pattern':<{col1_width}} {'Filename':<{col2_width}} {'Folder':<{col3_width}} Internal Title\n"
        output_text += "-" * (col1_width + col2_width + col3_width + 50) + "\n"
        
        for pattern, filename, folder, title in sorted(results, key=lambda x: (x[0], x[1])):
            output_text += f"{pattern:<{col1_width}} {filename:<{col2_width}} {folder:<{col3_width}} {title}\n"
        
        # Write to file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(output_text)
        
        # Populate the files table with 3 columns
        self.files_table.blockSignals(True)
        self.files_table.setRowCount(len(results))
        
        sorted_results = sorted(results, key=lambda x: (x[0], x[1]))
        
        for row_idx, (pattern, filename, folder, title) in enumerate(sorted_results):
            # Column 0: Sequential index number
            index_item = QTableWidgetItem(str(row_idx + 1))
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)  # Make read-only
            
            # Column 1: ToK Index (the pattern like "A B")
            tok_item = QTableWidgetItem(pattern)
            
            # Column 2: Filename (rest of the name)
            filename_item = QTableWidgetItem(filename)
            
            self.files_table.setItem(row_idx, 0, index_item)
            self.files_table.setItem(row_idx, 1, tok_item)
            self.files_table.setItem(row_idx, 2, filename_item)
        
        self.files_table.blockSignals(False)
        
        self.show_message("Scan Complete", 
                         f"Found {len(results)} PDFs with ToK indices.\n\n"
                         f"Results displayed in table and written to:\n{output_file_path}")
        
        self.statusBar().showMessage(f"Scan complete - {len(results)} PDFs found")
    
    def load_tok_codes(self):
        """Load and display ToK codes in the table"""
        try:
            tok_items = self.manager.load_tok_data()
            
            if not tok_items:
                self.show_message("No Data", "No ToK codes found in database.")
                return
            
            # Disable signals while populating
            self.tok_table.blockSignals(True)
            
            # Clear and populate table
            self.tok_table.setRowCount(len(tok_items))
            
            for row, item in enumerate(tok_items):
                code = item.get('prefix', '')
                label = item.get('string', '')
                
                code_item = QTableWidgetItem(code)
                label_item = QTableWidgetItem(label)
                
                self.tok_table.setItem(row, 0, code_item)
                self.tok_table.setItem(row, 1, label_item)
            
            # Re-enable signals
            self.tok_table.blockSignals(False)
            
            self.statusBar().showMessage(f"Loaded {len(tok_items)} ToK codes")
            
        except Exception as e:
            self.show_message("Error", f"Error loading ToK codes: {str(e)}", QMessageBox.Critical)
    
    def show_bare_pdfs(self):
        """Load and display bare PDF files in the table"""
        try:
            bare_pdfs = self.manager.get_bare_pdfs(self.current_dir)
            
            if not bare_pdfs:
                self.show_message("No Files", "No bare PDF files found in current folder.")
                self.files_table.setRowCount(0)
                return
            
            # Disable signals while populating
            self.files_table.blockSignals(True)
            
            # Clear and populate table
            self.files_table.setRowCount(len(bare_pdfs))
            
            for row_idx, (idx, filename) in enumerate(bare_pdfs):
                filename_item = QTableWidgetItem(filename)
                self.files_table.setItem(row_idx, 0, filename_item)
            
            # Re-enable signals
            self.files_table.blockSignals(False)
            
            self.statusBar().showMessage(f"Loaded {len(bare_pdfs)} bare PDF files from {self.current_dir}")
            
        except Exception as e:
            self.show_message("Error", f"Error loading files: {str(e)}", QMessageBox.Critical)
    
    def add_tok_prefix_to_file(self):
        """Add ToK prefix from selected ToK entry to selected file"""
        # Check if a file is selected
        selected_file_rows = self.files_table.selectedItems()
        if not selected_file_rows:
            self.show_message("No File Selected", 
                            "Please select a file from the Files table first.", 
                            QMessageBox.Warning)
            return
        
        # Check if a ToK entry is selected
        selected_tok_rows = self.tok_table.selectedItems()
        if not selected_tok_rows:
            self.show_message("No ToK Selected", 
                            "Please select a ToK code from the ToK table first.", 
                            QMessageBox.Warning)
            return
        
        # Get the selected row numbers
        file_row = self.files_table.currentRow()
        tok_row = self.tok_table.currentRow()
        
        if file_row < 0 or tok_row < 0:
            self.show_message("Invalid Selection", 
                            "Please select one file and one ToK entry.", 
                            QMessageBox.Warning)
            return
        
        # Get the ToK code from the selected row
        tok_code_item = self.tok_table.item(tok_row, 0)
        if not tok_code_item:
            self.show_message("Error", "Could not read ToK code.", QMessageBox.Critical)
            return
        
        tok_code = tok_code_item.text().strip()
        
        # Get the current filename
        filename_item = self.files_table.item(file_row, 0)
        if not filename_item:
            self.show_message("Error", "Could not read filename.", QMessageBox.Critical)
            return
        
        old_filename = filename_item.text().strip()
        
        # Check if old filename exists in manager's data
        file_index = file_row + 1  # Row is 0-indexed, display index is 1-indexed
        if file_index not in self.manager.bare_pdf_files:
            self.show_message("Error", "File not found in database.", QMessageBox.Critical)
            return
        
        actual_old_filename = self.manager.bare_pdf_files[file_index]
        
        try:
            # Format ToK code by adding space after each character
            formatted_code = ' '.join(tok_code) + ' '
            
            # Create new filename by prepending the ToK code
            new_filename = formatted_code + actual_old_filename
            
            # Rename the file on disk
            old_path = os.path.join(self.current_dir, actual_old_filename)
            new_path = os.path.join(self.current_dir, new_filename)
            
            if not os.path.exists(old_path):
                self.show_message("Error", f"File '{actual_old_filename}' not found on disk.", 
                                QMessageBox.Critical)
                return
            
            if os.path.exists(new_path):
                self.show_message("Error", f"A file named '{new_filename}' already exists.", 
                                QMessageBox.Warning)
                return
            
            os.rename(old_path, new_path)
            
            # Update the manager's data
            self.manager.bare_pdf_files[file_index] = new_filename
            
            # Update the display
            self.files_table.blockSignals(True)
            self.files_table.item(file_row, 0).setText(new_filename)
            self.files_table.blockSignals(False)
            
            self.statusBar().showMessage(f"Added prefix '{tok_code}' to file: {new_filename}")
            self.show_message("Success", 
                            f"ToK prefix added successfully!\n\n"
                            f"Old: {actual_old_filename}\n"
                            f"New: {new_filename}")
            
        except Exception as e:
            self.show_message("Error", f"Error renaming file: {str(e)}", QMessageBox.Critical)
    
    def on_file_item_changed(self, item):
        """Handle changes to file table items"""
        row = item.row()
        
        # Get the filename item
        filename_item = self.files_table.item(row, 0)
        
        if not filename_item:
            return
        
        # Create a unique identifier for this row
        row_id = f"{row}"
        
        # Skip if already processing this row
        if row_id in self.files_being_edited:
            return
        
        try:
            self.files_being_edited.add(row_id)
            
            new_filename = filename_item.text().strip()
            
            if not new_filename:
                self.show_message("Error", "Filename cannot be empty.", QMessageBox.Warning)
                self.files_being_edited.discard(row_id)
                self.show_bare_pdfs()  # Reload to reset
                return
            
            # Find the old filename from manager's data
            old_filename = None
            for idx, fname in self.manager.bare_pdf_files.items():
                if idx == row + 1:  # Row is 0-indexed, display index is 1-indexed
                    old_filename = fname
                    break
            
            if not old_filename:
                self.show_message("Error", "Could not find original file.", QMessageBox.Critical)
                self.files_being_edited.discard(row_id)
                return
            
            # If filename hasn't changed, do nothing
            if old_filename == new_filename:
                self.files_being_edited.discard(row_id)
                return
            
            # Rename the file to exactly the new filename
            old_path = os.path.join(self.current_dir, old_filename)
            new_path = os.path.join(self.current_dir, new_filename)
            
            if not os.path.exists(old_path):
                self.show_message("Error", f"File '{old_filename}' not found.", QMessageBox.Critical)
                self.files_being_edited.discard(row_id)
                self.show_bare_pdfs()  # Reload to reset
                return
            
            if os.path.exists(new_path):
                self.show_message("Error", f"A file named '{new_filename}' already exists.", QMessageBox.Warning)
                self.files_being_edited.discard(row_id)
                self.show_bare_pdfs()  # Reload to reset
                return
            
            os.rename(old_path, new_path)
            
            # Update the manager's data
            self.manager.bare_pdf_files[row + 1] = new_filename
            
            self.statusBar().showMessage(f"Renamed: {old_filename} → {new_filename}")
            
        except Exception as e:
            self.show_message("Error", f"Error renaming file: {str(e)}", QMessageBox.Critical)
            self.show_bare_pdfs()  # Reload to reset
        
        finally:
            self.files_being_edited.discard(row_id)
    
    def on_tok_item_changed(self, item):
        """Handle changes to ToK table items"""
        row = item.row()
        col = item.column()
        
        # Get both items from the row
        code_item = self.tok_table.item(row, 0)
        label_item = self.tok_table.item(row, 1)
        
        if not code_item or not label_item:
            return
        
        # Create a unique identifier for this row
        row_id = f"{row}"
        
        # Skip if already processing this row
        if row_id in self.tok_being_edited:
            return
        
        try:
            self.tok_being_edited.add(row_id)
            
            new_code = code_item.text().strip()
            new_label = label_item.text().strip()
            
            if not new_code or not new_label:
                self.show_message("Error", "ToK code and label cannot be empty.", QMessageBox.Warning)
                self.tok_being_edited.discard(row_id)
                self.load_tok_codes()  # Reload to reset
                return
            
            # Validate ToK code
            if not new_code.isalnum():
                self.show_message("Error", "ToK code must be alphanumeric only.", QMessageBox.Warning)
                self.tok_being_edited.discard(row_id)
                self.load_tok_codes()  # Reload to reset
                return
            
            # Find the old code (what this entry was before)
            old_code = None
            if row < len(self.manager.tok_data['ToK']):
                old_code = self.manager.tok_data['ToK'][row].get('prefix')
            
            if not old_code:
                self.show_message("Error", "Could not find original ToK entry.", QMessageBox.Critical)
                self.tok_being_edited.discard(row_id)
                return
            
            # Check if new code conflicts with existing (unless it's the same as old)
            if new_code != old_code:
                for idx, entry in enumerate(self.manager.tok_data['ToK']):
                    if idx != row and entry.get('prefix') == new_code:
                        self.show_message("Error", 
                                        f"ToK code '{new_code}' already exists.\nPlease use a unique code.", 
                                        QMessageBox.Warning)
                        self.tok_being_edited.discard(row_id)
                        self.load_tok_codes()  # Reload to reset
                        return
            
            # Update the entry
            self.manager.update_tok_entry(old_code, new_code, new_label)
            
            # Save to JSON
            backup_file = self.manager.save_tok_data()
            
            self.statusBar().showMessage(f"Updated ToK: '{new_code}' - '{new_label}' (backup: {backup_file})")
            
        except Exception as e:
            self.show_message("Error", f"Error updating ToK: {str(e)}", QMessageBox.Critical)
            self.load_tok_codes()  # Reload to reset
        
        finally:
            self.tok_being_edited.discard(row_id)
    
    def add_to_tok(self):
        """Add a new ToK entry via dialog"""
        tok_code, ok1 = QInputDialog.getText(self, "Add ToK Entry", 
                                             "Enter ToK code (alphanumeric):")
        if not ok1 or not tok_code:
            return
        
        tok_code = tok_code.strip()
        
        if not tok_code.isalnum():
            self.show_message("Error", "ToK code must be alphanumeric only.", QMessageBox.Warning)
            return
        
        # Check if exists
        for entry in self.manager.tok_data.get('ToK', []):
            if entry.get('prefix') == tok_code:
                self.show_message("Error", 
                                f"ToK code '{tok_code}' already exists.\nEdit it in the table instead.", 
                                QMessageBox.Warning)
                return
        
        label, ok2 = QInputDialog.getText(self, "Add ToK Entry", 
                                         "Enter label:")
        if not ok2 or not label:
            return
        
        label = label.strip()
        
        try:
            self.manager.add_tok_entry(tok_code, label)
            backup_file = self.manager.save_tok_data()
            
            self.show_message("Success", 
                            f"Added ToK entry:\nCode: {tok_code}\nLabel: {label}\n\nBackup: {backup_file}")
            
            # Reload the table
            self.load_tok_codes()
            
            self.statusBar().showMessage(f"Added ToK: '{tok_code}' - '{label}'")
            
        except Exception as e:
            self.show_message("Error", f"Error adding ToK entry: {str(e)}", QMessageBox.Critical)
    
    def delete_from_tok(self):
        """Delete a ToK entry"""
        tok_code, ok = QInputDialog.getText(self, "Delete ToK Entry", 
                                           "Enter ToK code to delete:")
        if not ok or not tok_code:
            return
        
        tok_code = tok_code.strip()
        
        # Find the entry
        found_label = None
        for entry in self.manager.tok_data.get('ToK', []):
            if entry.get('prefix') == tok_code:
                found_label = entry.get('string')
                break
        
        if not found_label:
            self.show_message("Error", f"ToK code '{tok_code}' not found.", QMessageBox.Warning)
            return
        
        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Deletion",
                                    f"Delete ToK entry?\n\nCode: {tok_code}\nLabel: {found_label}",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.manager.delete_tok_entry(tok_code)
                backup_file = self.manager.save_tok_data()
                
                self.show_message("Success", 
                                f"Deleted ToK entry:\nCode: {tok_code}\nLabel: {found_label}\n\nBackup: {backup_file}")
                
                # Reload the table
                self.load_tok_codes()
                
                self.statusBar().showMessage(f"Deleted ToK: '{tok_code}'")
                
            except Exception as e:
                self.show_message("Error", f"Error deleting ToK entry: {str(e)}", QMessageBox.Critical)
    
    def show_current_folder(self):
        """Show current working folder"""
        self.show_message("Current Folder", f"Current working directory:\n{self.current_dir}")
    
    def go_to_coffeetable(self):
        """Go to coffeetable folder"""
        coffeetable_path = self.manager.home / "Dropbox" / "coffeetable"
        
        if not coffeetable_path.exists():
            reply = QMessageBox.question(self, "Create Folder?",
                                        f"Coffeetable folder not found.\n\nCreate it at:\n{coffeetable_path}?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                coffeetable_path.mkdir(parents=True, exist_ok=True)
            else:
                return
        
        self.current_dir = str(coffeetable_path)
        os.chdir(self.current_dir)
        self.folder_label.setText(f"Current Folder: {self.current_dir}")
        
        self.statusBar().showMessage(f"Changed to: {self.current_dir}")
        
        # Reload files if any
        if self.files_table.rowCount() > 0:
            self.show_bare_pdfs()
    
    def on_worker_error(self, error_msg):
        """Handle worker thread errors"""
        self.progress_label.setVisible(False)
        self.show_message("Error", f"An error occurred: {error_msg}", QMessageBox.Critical)
        self.statusBar().showMessage("Error occurred")


def main():
    """Main function"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a modern look
    
    window = PDFManagerWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
