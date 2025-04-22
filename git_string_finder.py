import subprocess
import os
import datetime
import html
import sys
import json  # Needed for safely embedding hash into JS onclick


# --- Configuration ---


def get_repo_path():
    """Detects if running inside a Git repo, otherwise prompts."""
    current_dir = os.getcwd()
    # Go up directories to find .git, useful if script is run from a subdirectory
    check_dir = current_dir
    while True:
        if os.path.isdir(os.path.join(check_dir, ".git")):
            print(f"Detected Git repository root at: {check_dir}")
            return check_dir
        parent_dir = os.path.dirname(check_dir)
        if parent_dir == check_dir:  # Reached root directory
            break
        check_dir = parent_dir

    # If not found by going up, check current dir one last time
    if os.path.isdir(os.path.join(current_dir, ".git")):
        print(f"Detected Git repository at: {current_dir}")
        return current_dir

    # If still not found, prompt
    print("Not running inside a Git repository directory or subdirectory.")
    repo_path = input("Enter the full path to the local Git repository: ")
    return repo_path


# Get repository path (auto-detect or prompt)
REPO_PATH = get_repo_path()

# Prompt user for other inputs
SEARCH_STRING = input("Enter the string/text to search for: ")
branch_choice = input(
    "Search all branches or a specific one? (Enter '--all' or branch name) [default: --all]: "
)
SEARCH_BRANCHES = (
    branch_choice if branch_choice else "--all"
)  # Default to --all if empty


# --- Helper Function ---


def run_git_command(command_list, cwd):
    """Runs a Git command using subprocess and returns stdout."""
    try:
        # Ensure Git is available
        subprocess.run(
            ["git", "--version"], check=True, capture_output=True, text=True, cwd=cwd
        )

        # Run the main command
        result = subprocess.run(
            ["git"] + command_list,
            check=True,  # Raise exception on non-zero exit code
            capture_output=True,  # Capture stdout/stderr
            text=True,  # Decode output as text (usually UTF-8)
            cwd=cwd,  # Run in the specified repository directory
            encoding="utf-8",  # Explicitly set encoding
            errors="replace",  # Handle potential encoding errors gracefully
        )
        return result.stdout.strip()
    except FileNotFoundError:
        print(
            "ERROR: 'git' command not found. Please ensure Git is installed and in your system's PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # Handle specific error: string not found in log -S search
        if e.returncode == 1 and not e.stdout and not e.stderr:
            return ""  # Common case for `git log -S` finding nothing.
        # Handle specific error: bad revision (e.g., branch doesn't exist)
        elif "unknown revision or path not in the working tree" in e.stderr:
            print(
                f"ERROR: Git command failed. Bad revision or path specified (e.g., branch '{SEARCH_BRANCHES}' not found?).",
                file=sys.stderr,
            )
            print(f"Stderr:\n{e.stderr}", file=sys.stderr)
            return None  # Indicate failure
        else:
            # General Git command failure
            print(
                f"ERROR: Git command failed (Exit Code {e.returncode}): {' '.join(e.cmd)}",
                file=sys.stderr,
            )
            print(f"Stderr:\n{e.stderr}", file=sys.stderr)
            return None  # Indicate failure
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


# --- Core Logic ---


def find_string_introduction(repo_path, search_string, branches_to_search):
    """
    Finds commits where the search string was introduced.
    Uses 'git log -S' which finds commits where the *count* of the string changes.
    We then filter the diff context for added lines ('+').
    """
    if not os.path.isdir(repo_path) or not os.path.isdir(
        os.path.join(repo_path, ".git")
    ):
        print(f"ERROR: Invalid Git repository path: {repo_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSearching for string: '{search_string}' in repository: {repo_path}")
    print(f"Searching branches: {branches_to_search}")

    # Use git log -S to find commits where the number of occurrences changed.
    commit_format = "COMMIT_MARKER%n%H%n%cI%n%an%n%s"
    log_command = [
        "log",
        branches_to_search,
        "--no-merges",
        f"-S{search_string}",
        # "--pickaxe-regex", # Uncomment if search_string is a regex
        "-p",  # Show patch
        f"--pretty=format:{commit_format}",
    ]

    full_log_output = run_git_command(log_command, repo_path)

    if full_log_output is None:
        print("Failed to retrieve Git log. Check previous errors.", file=sys.stderr)
        return []
    if not full_log_output:
        print("No commits found changing the occurrence of the specified string.")
        return []

    results = []
    # Split by marker, skip first empty element which occurs if the log starts with the marker
    commits_data = full_log_output.split("COMMIT_MARKER\n")
    if (
        commits_data and not commits_data[0].strip()
    ):  # Handle potential leading empty string
        commits_data = commits_data[1:]

    print(f"Found {len(commits_data)} potential commits. Analyzing diffs...")

    for commit_data in commits_data:
        if not commit_data.strip():  # Skip empty chunks if any exist
            continue
        try:
            # Split into header (hash, date, author, subject) and diff content
            parts = commit_data.strip().split("\n", 4)
            if len(parts) < 5:
                continue  # Skip if format is unexpected

            commit_hash = parts[0]
            commit_date_str = parts[1]
            author_name = parts[2]
            subject = parts[3]
            diff_content = parts[4]

            # Parse the date
            commit_date = None
            try:
                commit_date_str_parsed = commit_date_str.replace(" Z", "+00:00")
                if ":" == commit_date_str_parsed[-3:-2]:
                    commit_date_str_parsed = (
                        commit_date_str_parsed[:-3] + commit_date_str_parsed[-2:]
                    )
                commit_date = datetime.datetime.fromisoformat(commit_date_str_parsed)
            except ValueError as date_err:
                print(
                    f"WARN: Could not parse date '{commit_date_str}' for commit {commit_hash}. Error: {date_err}",
                    file=sys.stderr,
                )
                # Keep original string for display if parsing failed

            # Extract relevant context lines from the diff (lines added containing the string)
            context_lines = []
            current_file = "Unknown File"
            for line in diff_content.split("\n"):
                if line.startswith("+++ b/"):
                    current_file = line[6:]  # Get filename after '+++ b/'
                elif (
                    line.startswith("+")
                    and not line.startswith("+++")
                    and search_string in line
                ):
                    try:
                        line.encode("utf-8")  # Check if it's valid UTF-8
                        context_lines.append(
                            f"{html.escape(current_file)}: {html.escape(line)}"
                        )  # Escape for HTML
                    except UnicodeDecodeError:
                        context_lines.append(
                            f"{html.escape(current_file)}: [Binary content change]"
                        )

            # Only include commits where the string was actually ADDED in the diff context
            if context_lines:
                # Find branches containing this commit
                branch_command = [
                    "branch",
                    "--contains",
                    commit_hash,
                    "--all",
                    "--format=%(refname:short)",
                ]
                branches_output = run_git_command(branch_command, repo_path)
                branches = (
                    [
                        html.escape(b)
                        for b in branches_output.split("\n")
                        if b and "->" not in b
                    ]
                    if branches_output
                    else ["N/A"]
                )

                results.append(
                    {
                        "hash": commit_hash,  # Keep full hash
                        "date": commit_date,
                        "date_str": html.escape(commit_date_str),
                        "author": html.escape(author_name),
                        "subject": html.escape(subject),
                        "branches": branches,
                        "context": context_lines,
                    }
                )
        except Exception as parse_err:
            print(
                f"WARN: Error parsing commit data chunk. Error: {parse_err}\nChunk:\n{commit_data[:500]}...",
                file=sys.stderr,
            )
            continue

    # Sort results by date (oldest first)
    results.sort(key=lambda x: x["date"] or datetime.datetime.min)

    print(f"Analysis complete. Found {len(results)} commits introducing the string.")
    return results


# --- HTML Generation ---


def generate_html_report(search_string, results, filename):
    """Generates an HTML report from a template with copy-to-clipboard functionality."""
    template_filename = "git_search_template.html"  # Consistent template name
    try:
        with open(template_filename, "r", encoding="utf-8") as f:
            template_content = f.read()
    except IOError as e:
        print(
            f"ERROR: Could not read HTML template file: {template_filename}.  Error: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Escape the search string for HTML output
    escaped_search_string = html.escape(search_string)

    # Placeholder replacement in the template
    html_content = template_content.replace(
        "{{ SEARCH_STRING }}", escaped_search_string
    )

    # Generate the table rows
    table_rows_html = ""
    if not results:
        table_rows_html = '<p class="alert alert-warning mt-3">No commits found introducing this specific string based on the diff analysis.</p>'
    else:
        table_rows_html = f'<p class="text-muted">Found {len(results)} commit(s).</p>'
        table_rows_html += '<div class="table-responsive mt-3"><table class="table table-striped table-bordered table-hover"><thead class="table-dark"><tr><th scope="col" style="width: 15%;">Commit Date</th><th scope="col" style="width: 25%;">Commit Hash</th><th scope="col" style="width: 15%;">Branches</th><th scope="col" style="width: 10%;">Author</th><th scope="col" style="width: 15%;">Subject</th><th scope="col" style="width: 20%;">Context (Added Lines)</th></tr></thead><tbody>'
        for r in results:
            date_display = (
                r["date"].strftime("%Y-%m-%d %H:%M:%S %Z")
                if r["date"]
                else r["date_str"]
            )
            branches_html = (
                '<span class="branch-list">'
                + "".join(f"<span>{html.escape(b)}</span>" for b in r["branches"])
                + "</span>"
                if r["branches"]
                else "N/A"
            )
            context_html = (
                "<br>".join(
                    f'<code class="context-code">{line}</code>' for line in r["context"]
                )
                if r["context"]
                else '<span class="text-muted">N/A</span>'
            )
            full_hash = r["hash"]
            safe_hash_js = json.dumps(full_hash)  # Safely embed in JS
            commit_cell_content = f"""
                <span class='commit-hash'>{full_hash}</span>
                <button class="btn btn-outline-secondary btn-sm copy-btn"
                        onclick='copyToClipboard(this, {safe_hash_js})'
                        title="Copy hash to clipboard">
                    <i class="bi bi-clipboard"></i>
                    Copy
                </button>
            """
            table_rows_html += f"""
                <tr>
                    <td>{date_display}</td>
                    <td class='commit-hash-cell'>{commit_cell_content}</td>
                    <td>{branches_html}</td>
                    <td>{r['author']}</td>
                    <td>{r['subject']}</td>
                    <td>{context_html}</td>
                </tr>
            """
        table_rows_html += "</tbody></table></div>"  # Close table

    # Inject the table HTML into the template
    html_content = html_content.replace("{{ TABLE_ROWS }}", table_rows_html)

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nSuccessfully generated HTML report: {filename}")
    except IOError as e:
        print(
            f"ERROR: Could not write HTML report file: {filename}. Error: {e}",
            file=sys.stderr,
        )


# --- Main Execution ---

if __name__ == "__main__":
    # Basic validation for required inputs
    if not REPO_PATH or not SEARCH_STRING:
        print(
            "ERROR: Repository path and search string must be provided.",
            file=sys.stderr,
        )
        sys.exit(1)

    found_commits = find_string_introduction(REPO_PATH, SEARCH_STRING, SEARCH_BRANCHES)

    if found_commits is not None:  # Proceed only if search didn't fail critically
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_search_str = "".join(c if c.isalnum() else "_" for c in SEARCH_STRING[:20])
        output_filename = f"git_search_{safe_search_str}_{timestamp}.html"

        generate_html_report(SEARCH_STRING, found_commits, output_filename)

        # Try to open the report automatically
        try:
            # Use absolute path for os.startfile and cross-platform commands
            abs_output_filename = os.path.abspath(output_filename)
            if sys.platform == "win32":
                os.startfile(abs_output_filename)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", abs_output_filename], check=True)
            else:  # Linux, other Unix-like
                subprocess.run(["xdg-open", abs_output_filename], check=True)
        except FileNotFoundError:
            print(
                f"(Info) Could not automatically open the report: 'startfile', 'open' or 'xdg-open' command not found or failed."
            )
        except subprocess.CalledProcessError as open_err:
            print(f"(Info) Could not automatically open the report: {open_err}")
        except Exception as open_err:
            print(
                f"(Info) An unexpected error occurred while trying to open the report: {open_err}"
            )
