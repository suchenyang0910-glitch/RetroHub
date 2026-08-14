"""Register RetroHub as the default menu button for @GameCenterMini_bot.

Run on the Linux host after the HTTPS domain is reachable, with
TELEGRAM_BOT_TOKEN and PUBLIC_APP_URL loaded from the server .env file. The
token is never printed.
"""

import json
import os
import sys
from urllib.request import Request, urlopen


def main() -> int:
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    url = os.environ.get('PUBLIC_APP_URL')
    if not token or not url or not url.startswith('https://'):
        print('TELEGRAM_BOT_TOKEN and an HTTPS PUBLIC_APP_URL are required.', file=sys.stderr)
        return 2
    payload = json.dumps({
        'menu_button': {'type': 'web_app', 'text': 'Play RetroHub', 'web_app': {'url': url}},
    }).encode()
    request = Request(
        f'https://api.telegram.org/bot{token}/setChatMenuButton',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urlopen(request, timeout=15) as response:
        result = json.loads(response.read())
    if not result.get('ok'):
        print(f"Telegram rejected menu-button registration: {result.get('description', 'unknown error')}", file=sys.stderr)
        return 1
    print('Telegram menu button registered successfully.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
