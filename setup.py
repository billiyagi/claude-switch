#!/usr/bin/env python3
"""claude-switch — Switch Claude Code API providers easily."""

from setuptools import setup, find_packages
from pathlib import Path

setup(
    name="claude-switch",
    version="1.2.0",
    description="CLI tool to manage and switch Claude Code API provider configurations (cross-platform)",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Billy Febryansyah",
    url="https://github.com/billiyagi/claude-switch",
    py_modules=["claude_switch"],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "claude-switch=claude_switch:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Tools",
    ],
)
