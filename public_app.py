"""Cloud entry point: public research only, with isolated market storage."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from twetf.ui.public_navigation import main

main()
