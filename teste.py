import asyncio
import management.commands.utils.arguments as arguments
import management.commands.utils.main as main
import sys, os, django


sys.path.append('/usr/local/webchat')

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      arguments.parser.settings[0] or "webchat.settings")

django.setup()
asyncio.run(main.main(arguments.args.bind[0]))
