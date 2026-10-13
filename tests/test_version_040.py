from adultcam import __version__
from adultcam.app import create_app
import os


def test_package_version_matches_release():
    assert __version__ == '0.4.0'
