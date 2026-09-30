"""Allow ``python -m idp``."""

import sys

from idp.cli import main

if __name__ == "__main__":
    sys.exit(main())