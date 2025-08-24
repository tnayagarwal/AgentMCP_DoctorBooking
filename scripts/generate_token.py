import json
import argparse
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow, Flow

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send',
]

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Generate token.json for Gmail+Calendar using your client secret JSON.')
    p.add_argument('--client', required=True, help='Path to OAuth client secret JSON (downloaded from Google Cloud).')
    p.add_argument('--out', default='token.json', help='Path to write token.json (default: token.json)')
    p.add_argument('--port', type=int, default=8080, help='Local server port for OAuth callback (default: 8080)')
    return p.parse_args()


def load_client_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if 'installed' in data:
        return {'installed': data['installed']}
    if 'web' in data:
        return {'web': data['web']}
    raise RuntimeError('Invalid client secret JSON: expected top-level key "installed" or "web"')


def main():
    args = parse_args()
    cfg = load_client_config(args.client)

    if 'installed' in cfg:
        flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
        creds = flow.run_local_server(port=args.port)
    else:
        web_cfg = cfg['web']
        redirect_uris = web_cfg.get('redirect_uris', [])
        redirect_uri = f'http://localhost:{args.port}/'
        if not any((u or '').startswith('http://localhost') for u in redirect_uris):
            print('[ERROR] OAuth client type "web" needs a http://localhost redirect URI.')
            print(f'Add {redirect_uri} in Google Cloud Console, or create a "Desktop app" OAuth client, then re-run.')
            return
        flow = Flow.from_client_config(cfg, scopes=SCOPES, redirect_uri=redirect_uri)
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline', include_granted_scopes='true')
        print('Open this URL in your browser and authorize:')
        print(auth_url)
        response_url = input('Paste the full redirect URL here: ').strip()
        flow.fetch_token(authorization_response=response_url)
        creds = flow.credentials

    Path(args.out).write_text(creds.to_json(), encoding='utf-8')
    print(f'[OK] Wrote {Path(args.out).resolve()}')


if __name__ == '__main__':
    main()
