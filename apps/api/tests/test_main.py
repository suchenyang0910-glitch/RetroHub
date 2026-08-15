def test_health():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response=client.get('/health'); assert response.status_code==200; assert response.json()['status']=='ok'
def test_hub_catalog():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response=client.get('/api/hub'); assert response.status_code==200; assert response.json()['games'][0]['id']=='farm'
def test_farm_loop():
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    headers = {'X-Telegram-User': f'test-farm-loop-{uuid4()}'}
    with TestClient(app) as client:
        before=client.get('/api/farm', headers=headers).json(); assert before['coins'] >= 20
        planted=client.post('/api/farm/plant', headers=headers, json={'crop':'wheat'}); assert planted.status_code == 200
        assert client.post('/api/farm/harvest', headers=headers).status_code == 409

def test_production_requires_signed_telegram_identity(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('DEBUG', 'false')
    with TestClient(app) as client:
        assert client.get('/api/hub').status_code == 401

def test_production_accepts_valid_telegram_signature(monkeypatch):
    import hashlib
    import hmac
    import json
    from datetime import datetime, timezone
    from urllib.parse import urlencode
    from fastapi.testclient import TestClient
    from app.main import app
    token = 'test-bot-token'
    values = {'auth_date': str(int(datetime.now(timezone.utc).timestamp())), 'user': json.dumps({'id': 987654, 'first_name': 'Test'}, separators=(',', ':'))}
    check = '\n'.join(f'{key}={value}' for key, value in sorted(values.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    values['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    monkeypatch.setenv('DEBUG', 'false')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', token)
    with TestClient(app) as client:
        response = client.get('/api/hub', headers={'X-Telegram-Init-Data': urlencode(values)})
        assert response.status_code == 200
        assert response.json()['player']['name'] == 'Test'

def test_pet_merge_and_card_crafting_loops(monkeypatch):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('DEBUG', 'true')
    headers = {'X-Telegram-User': f'test-arcade-{uuid4()}'}
    with TestClient(app) as client:
        assert client.get('/api/pets', headers=headers).json()['pets'][0]['amount'] == 6
        merged = client.post('/api/pets/merge/1', headers=headers)
        assert merged.status_code == 200
        assert any(pet['tier'] == 2 for pet in merged.json()['pets'])
        battle = client.post('/api/cards/battle', headers=headers)
        assert battle.status_code == 200
        crafted = client.post('/api/cards/craft/clockwork_fox', headers=headers)
        assert crafted.status_code == 200
        assert crafted.json()['cards'][0]['key'] == 'clockwork_fox'

def test_daily_checkin_requires_play_and_leaderboard(monkeypatch):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('DEBUG', 'true')
    headers = {'X-Telegram-User': f'test-checkin-{uuid4()}'}
    with TestClient(app) as client:
        assert client.post('/api/checkin/claim', headers=headers).status_code == 409
        assert client.post('/api/farm/plant', headers=headers, json={'crop': 'wheat'}).status_code == 200
        claimed = client.post('/api/checkin/claim', headers=headers)
        assert claimed.status_code == 200
        assert claimed.json()['claimed_today'] is True
        assert claimed.json()['collection_awarded'] == 1
        assert client.post('/api/checkin/claim', headers=headers).status_code == 409
        leaderboard = client.get('/api/leaderboards/farm', headers=headers)
        assert leaderboard.status_code == 200
        assert any(entry['is_me'] for entry in leaderboard.json()['entries'])
