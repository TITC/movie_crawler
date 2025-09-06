#!/usr/bin/env python3
import toml
import datetime
import subprocess


def get_short_commit_hash():
    """Get the short commit hash of the current commit."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def main():
    # Read pyproject.toml
    with open('pyproject.toml', 'r') as f:
        data = toml.load(f)

    current_version = data['project']['version']

    # Get today's date in YYYYMMDD format
    today = datetime.datetime.now().strftime("%Y%m%d")

    # Get short commit hash
    commit_hash = get_short_commit_hash()

    # Create dev version: X.Y.Z-dev.date+hash format (PEP 440 compliant)
    dev_version = f"{current_version}-dev.{today}+{commit_hash}"

    # Update version
    data['project']['version'] = dev_version

    # Write updated pyproject.toml
    with open('pyproject.toml', 'w') as f:
        toml.dump(data, f)

    print(f"Updated to development version: {dev_version}")


if __name__ == '__main__':
    main()
