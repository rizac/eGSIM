#!/usr/bin/env python
import os
import sys

# Django management command customized for eGSIM. In  production,
# you can copy this file next to your .env location, providing you execute this
# script with python venv activated and this repo installed. Also remember to
# chmod 640 .env AND chown root:<egsim_user> .env)

if __name__ == "__main__":
    # Line commented (force settings file):
    # os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangosnippets.settings.development")

    # Simple .env read (no dotenv package), we need control to implement the same
    # systemd logic (which is stricter, e.g., no spaces)
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.isfile(dotenv_path):
        with open(dotenv_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                print(f'{key}={value}')
                os.environ.setdefault(key, value)

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)