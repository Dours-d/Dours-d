"""Fetch the current Hijri date and update README.md between marker tags."""

import json
import sys
import urllib.request

API_URL = "http://api.aladhan.com/v1/gToH"
START_TAG = "[//]: # (HIJRI_START)"
END_TAG = "[//]: # (HIJRI_END)"


def fetch_hijri_date(url=API_URL):
    """Return the Hijri date dict from the Aladhan API."""
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
    return data["data"]["hijri"]


def format_date_string(hijri):
    """Build the Markdown date string from a Hijri date dict."""
    return (
        "### \ufdfd\n"
        f"### \U0001f319 {hijri['day']} {hijri['month']['en']} "
        f"{hijri['year']} | {hijri['month']['ar']} \ufdfa"
    )


def replace_date_in_lines(lines, date_str):
    """Replace content between HIJRI markers with *date_str*.

    Returns the new list of lines and a boolean indicating whether the
    markers were found.
    """
    new_lines = []
    skip = False
    tag_found = False

    for line in lines:
        if START_TAG in line:
            new_lines.append(line)
            new_lines.append(date_str + "\n")
            skip = True
            tag_found = True
        elif END_TAG in line:
            new_lines.append(line)
            skip = False
        elif not skip:
            new_lines.append(line)

    return new_lines, tag_found


def update_readme(readme_path="README.md", api_url=API_URL):
    """End-to-end: fetch date, read README, replace, write back."""
    hijri = fetch_hijri_date(api_url)
    date_str = format_date_string(hijri)

    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines, tag_found = replace_date_in_lines(lines, date_str)

    if not tag_found:
        print("Tags not found! Check your README.md markers.")
        sys.exit(1)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


if __name__ == "__main__":
    update_readme()
