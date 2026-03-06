#!/usr/bin/env python
import os
import sys

# In production environments you might want to copy this file next to you .env and run
# management commands from there. In case, uncomment these lines on the copy:
# from dotenv import load_dotenv
# load_dotenv()

if __name__ == "__main__":
    # Line commented (force settings file):
    # os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangosnippets.settings.development")

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)