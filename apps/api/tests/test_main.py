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

def test_farm_order_consumes_inventory_and_rewards_player(monkeypatch):
    import asyncio
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from app.main import FarmStock, Player, Session, app
    monkeypatch.setenv('DEBUG', 'true')
    user_id = f'test-order-{uuid4()}'
    headers = {'X-Telegram-User': user_id}
    with TestClient(app) as client:
        order = client.get('/api/farm/orders', headers=headers)
        assert order.status_code == 200
        assert client.post('/api/farm/orders/wheat_delivery/claim', headers=headers).status_code == 409

        async def add_wheat() -> None:
            async with Session() as session:
                player = await session.scalar(select(Player).where(Player.telegram_id == user_id))
                session.add(FarmStock(player_id=player.id, item_key='wheat', amount=2))
                await session.commit()

        asyncio.run(add_wheat())
        claimed = client.post('/api/farm/orders/wheat_delivery/claim', headers=headers)
        assert claimed.status_code == 200
        assert claimed.json()['inventory']['wheat'] == 0
        assert claimed.json()['orders'][0]['claimed'] is True
        assert claimed.json()['coins'] == 1120

def test_farm_harvest_then_sell_writes_server_ledger(monkeypatch):
    import asyncio
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from app.main import Player, Session, app
    monkeypatch.setenv('DEBUG', 'true')
    user_id = f'test-sell-{uuid4()}'
    headers = {'X-Telegram-User': user_id}
    with TestClient(app) as client:
        assert client.post('/api/farm/plant', headers=headers, json={'crop': 'wheat'}).status_code == 200

        async def finish_crop() -> None:
            async with Session() as session:
                player = await session.scalar(select(Player).where(Player.telegram_id == user_id))
                player.wheat_ready_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await session.commit()

        asyncio.run(finish_crop())
        harvested = client.post('/api/farm/harvest', headers=headers)
        assert harvested.status_code == 200
        assert harvested.json()['inventory']['wheat'] == 1
        sold = client.post('/api/farm/sell/wheat', headers=headers)
        assert sold.status_code == 200
        assert sold.json()['inventory']['wheat'] == 0
        assert sold.json()['coins'] == 1025
        assert sold.json()['ledger'][0] == {'type': 'sell_wheat', 'coins_delta': 45, 'xp_delta': 0}

def test_profile_honors_and_privacy_controls(monkeypatch):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('DEBUG', 'true')
    headers = {'X-Telegram-User': f'test-profile-{uuid4()}'}
    with TestClient(app) as client:
        profile = client.get('/api/profile', headers=headers)
        assert profile.status_code == 200
        assert profile.json()['privacy'] == {'farm_public': False, 'collection_public': False}
        updated = client.put('/api/profile/privacy', headers=headers, json={'farm_public': True, 'collection_public': True})
        assert updated.status_code == 200
        assert updated.json()['privacy'] == {'farm_public': True, 'collection_public': True}

def test_friends_can_visit_and_water_public_farms(monkeypatch):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('DEBUG', 'true')
    owner_id, helper_id = f'owner-{uuid4()}', f'helper-{uuid4()}'
    owner_headers, helper_headers = {'X-Telegram-User': owner_id}, {'X-Telegram-User': helper_id}
    with TestClient(app) as client:
        client.get('/api/profile', headers=owner_headers)
        client.get('/api/profile', headers=helper_headers)
        assert client.put('/api/profile/privacy', headers=owner_headers, json={'farm_public': True, 'collection_public': False}).status_code == 200
        accepted = client.post(f'/api/friends/accept/{owner_id}', headers=helper_headers)
        assert accepted.status_code == 200
        friends = client.get('/api/friends', headers=helper_headers)
        assert friends.json()['friends'][0]['telegram_id'] == owner_id
        assert client.post('/api/farm/plant', headers=owner_headers, json={'crop': 'wheat'}).status_code == 200
        visit = client.get(f'/api/friends/{owner_id}/farm', headers=helper_headers)
        assert visit.status_code == 200
        watered = client.post(f'/api/friends/{owner_id}/help/water', headers=helper_headers)
        assert watered.status_code == 200
        assert watered.json()['relationship_progress'] == 1
        assert client.post(f'/api/friends/{owner_id}/help/water', headers=helper_headers).status_code == 409
