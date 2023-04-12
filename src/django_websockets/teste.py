import asyncio
from django_websockets.server import arguments, main, parser
import sys, os, django


sys.path.append('/usr/local/webchat')

args = parser.parse_args()

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      arguments.parser.settings[0] or "webchat.settings")

django.setup()
asyncio.run(main.main(args.bind[0]))
