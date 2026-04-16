#!/usr/bin/env python3
"""Flet Claude Code GUI - Desktop application entry point."""

import flet as ft
from app.app import create_app


def main():
    ft.run(create_app)


if __name__ == "__main__":
    main()
