import sys
import os
from pathlib import Path

def get_base_path():
    """
    Returns the base path for the application.
    When running as a bundle (PyInstaller), it returns the folder containing the EXE.
    Otherwise, returns the project root.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

def get_bundle_path():
    """
    Returns the internal bundle path (where internal assets are extracted).
    For PyInstaller, this is sys._MEIPASS.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent

def get_templates_path():
    """Returns the absolute path to the templates directory."""
    # Templates are usually bundled inside the EXE
    return get_bundle_path() / "app" / "dashboard" / "templates"

def get_static_path():
    """Returns the absolute path to the static directory."""
    # Static files are usually bundled inside the EXE
    return get_bundle_path() / "app" / "dashboard" / "static"

def get_plugins_path():
    """
    Returns the absolute path to the plugins directory.
    We prefer plugins next to the EXE so users can add them at runtime.
    """
    return get_base_path() / "plugins"
