"""
Main entry point for 'python -m dhcp_manager'.
"""

import sys
from dhcp_manager.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
