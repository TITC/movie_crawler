#!/usr/bin/env python3
import argparse
import toml
import re


def bump_version(version, bump_type):
    """
    Bump a version number based on the bump type.

    Args:
        version (str): Current version in format x.y.z
        bump_type (str): One of 'patch', 'minor', or 'major'

    Returns:
        str: The bumped version
    """
    # Remove any dev suffix if present
    version = re.sub(r'-dev\.\d+.*$', '', version)

    major, minor, patch = map(int, version.split('.'))

    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'patch':
        patch += 1

    return f"{major}.{minor}.{patch}"


def main():
    parser = argparse.ArgumentParser(description='Update version in pyproject.toml')
    parser.add_argument('--type', choices=['patch', 'minor', 'major'], default='patch',
                        help='Type of version bump to perform')
    args = parser.parse_args()

    # Read pyproject.toml
    with open('pyproject.toml', 'r') as f:
        data = toml.load(f)

    current_version = data['project']['version']
    new_version = bump_version(current_version, args.type)

    # Update version
    data['project']['version'] = new_version

    # Write updated pyproject.toml
    with open('pyproject.toml', 'w') as f:
        toml.dump(data, f)

    print(f"Version bumped from {current_version} to {new_version}")


if __name__ == '__main__':
    main()
