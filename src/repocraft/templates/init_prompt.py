from __future__ import annotations


def get_init_prompt() -> str:
    """Return the prompt for exploring a new repo and generating CLAUDE.md."""
    return """\
Explore this repository thoroughly and understand its structure, architecture, testing approach, build process, and code conventions.

Your task is to create a `CLAUDE.md` file in the project root directory that documents your findings. This file will be used by future activities to understand how to work with this codebase.

Include the following sections in CLAUDE.md:

## Project Overview
- What this project does
- Tech stack (languages, frameworks, libraries)
- Architecture overview (monolith, microservices, client-server, etc.)

## Development Setup
- How to install dependencies
- Environment variables or config files needed
- How to run the project locally

## Testing
- Test framework used
- How to run tests (command)
- How to run specific tests
- Test file locations and naming conventions

## Building & Deployment
- Build commands
- Output artifacts
- Deployment process (if documented)

## Code Conventions
- Linting/formatting tools (eslint, prettier, black, ruff, etc.)
- Import order conventions
- Naming conventions
- File organization patterns

## Key Files & Directories
- Entry points
- Configuration files
- Important modules or components

## Gotchas & Special Notes
- Known issues or workarounds
- Performance considerations
- Security considerations
- Anything unusual about this codebase

Write the CLAUDE.md file to the project root. Use clear, concise language. Focus on actionable information that will help future activities work effectively with this codebase.
"""
