#!/usr/bin/env python3
"""
Analyze PDF duplicates to find which folders contain files
that also exist in protected folders.
"""

import json
from pathlib import Path
from collections import defaultdict

# Protected folders - do not delete from these
PROTECTED_FOLDERS = [
    'documents',
    '1hugefiles',
    'documents-in-folders',
    '1-spark-library'
]

# Folders to ignore completely (not protected, but shouldn't be considered for deletion)
IGNORE_FOLDERS = [
    'pdfmanager'
]


def is_protected_folder(folder_path):
    """Check if a folder path contains any protected folder name"""
    for protected in PROTECTED_FOLDERS:
        if f'/{protected}' in folder_path or folder_path.endswith(f'/{protected}'):
            return True
    return False


def is_ignored_folder(folder_path):
    """Check if a folder path contains any ignored folder name"""
    for ignored in IGNORE_FOLDERS:
        if f'/{ignored}' in folder_path or folder_path.endswith(f'/{ignored}'):
            return True
    return False


def analyze_duplicates(json_file_path):
    """
    Analyze the JSON file to find duplicates in non-protected folders.

    Returns:
        dict: Statistics about duplicates by folder
    """
    # Load JSON data
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Track files that exist in protected folders and their duplicates
    # folder_path -> list of (filename, size, protected_locations)
    deletable_by_folder = defaultdict(list)

    # Statistics
    total_files_in_protected = 0
    total_deletable_duplicates = 0

    # Process each size group
    for size_group in data:
        size = size_group['size']

        for file_entry in size_group['files']:
            filename = file_entry['filename']
            locations = file_entry['locations']

            # Check if this file exists in any protected folder
            protected_locations = []
            non_protected_locations = []

            for loc in locations:
                folder = loc['folder']
                # Skip ignored folders (like pdfmanager)
                if is_ignored_folder(folder):
                    continue

                if is_protected_folder(folder):
                    protected_locations.append(folder)
                else:
                    non_protected_locations.append(folder)

            # If file exists in at least one protected folder AND in other folders
            if protected_locations and non_protected_locations:
                total_files_in_protected += 1
                total_deletable_duplicates += len(non_protected_locations)

                # Add to deletable list for each non-protected folder
                for folder in non_protected_locations:
                    deletable_by_folder[folder].append({
                        'filename': filename,
                        'size': size,
                        'protected_locations': protected_locations
                    })

    return {
        'deletable_by_folder': deletable_by_folder,
        'total_files_in_protected': total_files_in_protected,
        'total_deletable_duplicates': total_deletable_duplicates
    }


def print_report(stats):
    """Print a formatted report of the analysis"""
    print("\n" + "="*80)
    print("DUPLICATE PDF ANALYSIS REPORT")
    print("="*80)
    print(f"\nProtected folders (DO NOT DELETE from these):")
    for folder in PROTECTED_FOLDERS:
        print(f"  - {folder}")

    print(f"\nIgnored folders (not included in analysis):")
    for folder in IGNORE_FOLDERS:
        print(f"  - {folder}")

    print(f"\n{'-'*80}")
    print(f"Files that exist in protected folders: {stats['total_files_in_protected']}")
    print(f"Total deletable duplicates in other folders: {stats['total_deletable_duplicates']}")
    print(f"{'-'*80}\n")

    # Sort folders by number of deletable duplicates (descending)
    deletable_by_folder = stats['deletable_by_folder']
    sorted_folders = sorted(deletable_by_folder.items(),
                           key=lambda x: len(x[1]),
                           reverse=True)

    print(f"Folders with deletable duplicates (sorted by count):\n")
    print(f"{'Count':<8} {'Folder'}")
    print("-" * 80)

    for folder, files in sorted_folders:
        count = len(files)
        print(f"{count:<8} {folder}")

    print("\n" + "="*80)

    # Show top 5 folders with details
    print("\nTOP 5 FOLDERS WITH MOST DELETABLE DUPLICATES:\n")

    for idx, (folder, files) in enumerate(sorted_folders[:5], 1):
        print(f"\n{idx}. {folder}")
        print(f"   Deletable files: {len(files)}")
        print(f"   Examples:")

        # Show first 5 examples
        for file_info in files[:5]:
            print(f"     - {file_info['filename']}")
            print(f"       (also in: {file_info['protected_locations'][0]})")

        if len(files) > 5:
            print(f"     ... and {len(files) - 5} more")

    print("\n" + "="*80)


def save_detailed_report(stats, output_file):
    """Save a detailed report to a file"""
    deletable_by_folder = stats['deletable_by_folder']
    sorted_folders = sorted(deletable_by_folder.items(),
                           key=lambda x: len(x[1]),
                           reverse=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("DETAILED DUPLICATE PDF ANALYSIS REPORT\n")
        f.write("="*80 + "\n\n")

        f.write(f"Protected folders (DO NOT DELETE from these):\n")
        for folder in PROTECTED_FOLDERS:
            f.write(f"  - {folder}\n")

        f.write(f"\nIgnored folders (not included in analysis):\n")
        for folder in IGNORE_FOLDERS:
            f.write(f"  - {folder}\n")

        f.write(f"\nTotal files in protected folders: {stats['total_files_in_protected']}\n")
        f.write(f"Total deletable duplicates: {stats['total_deletable_duplicates']}\n\n")
        f.write("="*80 + "\n\n")

        for folder, files in sorted_folders:
            f.write(f"\nFolder: {folder}\n")
            f.write(f"Deletable files: {len(files)}\n")
            f.write("-" * 80 + "\n")

            for file_info in files:
                f.write(f"  {file_info['filename']}\n")
                f.write(f"    Size: {file_info['size']:,} bytes\n")
                f.write(f"    Also in protected folder(s): {', '.join(file_info['protected_locations'])}\n")

            f.write("\n")

    print(f"\nDetailed report saved to: {output_file}")


if __name__ == "__main__":
    home = Path.home()
    json_file = home / "Dropbox" / "pdfmanager" / "pdf-files-by-size.json"
    output_file = home / "Dropbox" / "pdfmanager" / "duplicate-analysis.txt"

    print("Analyzing PDF duplicates...")
    print(f"Reading: {json_file}")

    stats = analyze_duplicates(json_file)

    # Print report to console
    print_report(stats)

    # Save detailed report to file
    save_detailed_report(stats, output_file)
