# Git String Introduction Finder

A Python script to search a local Git repository for a specific string and identify the commits where that string was first introduced (added). It generates an HTML report summarizing the findings.

## Description

This script helps developers trace when a specific piece of text, configuration value, or code snippet was added to a codebase. It leverages `git log -S` (the "pickaxe" search) to find commits that changed the number of occurrences of the specified string and then analyzes the diffs to pinpoint commits where the string was specifically added.

The results are presented in a user-friendly, timestamped HTML file styled with Bootstrap, showing the commit details (hash, date, author, subject), the branches containing the commit, and the context (added lines) where the string was found.

## Features

- Searches for a specific string within a Git repository's history.
- Identifies commits that _introduced_ (added) the string.
- Works on the current repository if run from within it (auto-detects `.git` folder).
- Can search across all branches (`--all`) or a specific branch.
- Generates a clear, sortable HTML report (sorted chronologically, oldest first).
- Displays full commit hashes with a one-click "Copy to Clipboard" button.
- Shows associated branches for each commit.
- Provides context (the added lines containing the string and their file).
- Uses Python's built-in `subprocess` module (no external Git libraries needed).

## Requirements

- **Python 3.6+** (due to f-strings and `datetime.fromisoformat`, though older versions might work with minor date parsing adjustments).
- **Git** installed and accessible in your system's PATH.

## Usage

1.  **Placement:** Place the `git_string_finder.py` script in the root directory of your local Git repository (the same directory containing the `.git` folder). You can also run it from elsewhere, but it will then prompt you for the repository path.
2.  **Run from Terminal:** Open your terminal or command prompt, navigate to the directory containing the script (or the repository root), and run it using Python:
    ```bash
    python git_string_finder.py
    ```
3.  **Input Prompts:** The script will ask for:
    - **Repository Path (if not auto-detected):** Enter the full path if the script isn't inside the repo.
    - **Search String:** Enter the exact text you want to search for (case-sensitive).
    - **Branches:** Enter `--all` to search all branches, or type the name of a specific branch (e.g., `main`, `develop`). Press Enter to default to `--all`.
4.  **Execution:** The script will execute Git commands and analyze the results, printing progress messages.

## Output

- The script will generate an HTML file in the directory where it was run.
- The filename will be `git_search_[sanitized_search_string]_[timestamp].html` (e.g., `git_search_my_config_value_20250422_113000.html`).
- The script will attempt to automatically open the generated HTML report in your default web browser.
- The report contains a table with columns for Commit Date, Commit Hash (with copy button), Branches, Author, Subject, and Context.

## License

This project is licensed under the MIT License.
