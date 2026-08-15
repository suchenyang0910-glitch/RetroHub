import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .telegram_auth import is_debug, validate_init_data

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./retrohub.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+asyncpg://', 1)
engine = create_async_engine(DATABASE_URL, future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass
class Player(Base):
    __tablename__ = 'players'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default='Player')
    farm_level: Mapped[int] = mapped_column(Integer, default=1)
    farm_xp: Mapped[int] = mapped_column(Integer, default=0)
    farm_coins: Mapped[int] = mapped_column(Integer, default=1000)
    farm_diamonds: Mapped[int] = mapped_column(Integer, default=50)
    wheat_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    card_materials: Mapped[int] = mapped_column(Integer, default=60)
    card_chapter: Mapped[int] = mapped_column(Integer, default=1)

class PetStack(Base):
    __tablename__ = 'pet_stacks'
    __table_args__ = (UniqueConstraint('player_id', 'tier', name='uq_pet_stack_tier'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    tier: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer, default=0)

class Card(Base):
    __tablename__ = 'cards'
    __table_args__ = (UniqueConstraint('player_id', 'card_key', name='uq_player_card_key'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    card_key: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer, default=1)

class GameActivity(Base):
    __tablename__ = 'game_activities'
    __table_args__ = (UniqueConstraint('player_id', 'game', 'played_on', name='uq_daily_game_activity'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    game: Mapped[str] = mapped_column(String(32))
    played_on: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())

class DailyCheckin(Base):
    __tablename__ = 'daily_checkins'
    __table_args__ = (UniqueConstraint('player_id', 'claimed_on', name='uq_daily_checkin'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    claimed_on: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())
    collection_awarded: Mapped[int] = mapped_column(Integer, default=1)

class FarmStock(Base):
    __tablename__ = 'farm_stock'
    __table_args__ = (UniqueConstraint('player_id', 'item_key', name='uq_farm_stock_item'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    item_key: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(Integer, default=0)

class FarmOrder(Base):
    __tablename__ = 'farm_orders'
    __table_args__ = (UniqueConstraint('player_id', 'order_key', name='uq_farm_order'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    order_key: Mapped[str] = mapped_column(String(40))
    claimed: Mapped[bool] = mapped_column(default=False)

class FarmLedger(Base):
    __tablename__ = 'farm_ledger'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    entry_type: Mapped[str] = mapped_column(String(40), index=True)
    coins_delta: Mapped[int] = mapped_column(Integer, default=0)
    xp_delta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PlayerProfile(Base):
    __tablename__ = 'player_profiles'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    farm_public: Mapped[bool] = mapped_column(default=False)
    collection_public: Mapped[bool] = mapped_column(default=False)

class TelegramIdentity(Base):
    __tablename__ = 'telegram_identities'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class VisitorPreference(Base):
    __tablename__ = 'visitor_preferences'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)

class ProfileVisit(Base):
    __tablename__ = 'profile_visits'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class Friendship(Base):
    __tablename__ = 'friendships'
    __table_args__ = (UniqueConstraint('player_low_id', 'player_high_id', name='uq_friend_pair'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_low_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    player_high_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)

class FarmHelp(Base):
    __tablename__ = 'farm_helps'
    __table_args__ = (UniqueConstraint('helper_id', 'target_id', 'help_type', 'helped_on', name='uq_daily_farm_help'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    helper_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    help_type: Mapped[str] = mapped_column(String(20))
    helped_on: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title='RetroHub Test API', version='0.2.0', lifespan=lifespan)
class Health(BaseModel): status: str; service: str; timestamp: datetime
class FarmAction(BaseModel): crop: str = Field(default='wheat', pattern='^wheat$')
class PrivacyUpdate(BaseModel): farm_public: bool; collection_public: bool
class VisitorPreferenceUpdate(BaseModel): enabled: bool

async def db() -> AsyncIterator[AsyncSession]:
    async with Session() as session: yield session

async def current_player(
    x_telegram_init_data: str | None = Header(default=None),
    x_telegram_user: str | None = Header(default=None),
    session: AsyncSession = Depends(db),
) -> Player:
    # X-Telegram-User only exists for local test/dev convenience. Production only
    # accepts Telegram-signed initData.
    if x_telegram_init_data:
        telegram_user = validate_init_data(x_telegram_init_data)
        telegram_id = str(telegram_user["id"])
        display_name = telegram_user.get("first_name") or telegram_user.get("username") or "Player"
        avatar_url = telegram_user.get("photo_url")
    elif is_debug():
        telegram_id = x_telegram_user or 'demo-player'
        display_name = 'Demo Player'
    else:
        raise HTTPException(401, 'Telegram Mini App authentication is required')
    player = (await session.scalar(select(Player).where(Player.telegram_id == telegram_id)))
    if not player:
        player = Player(telegram_id=telegram_id, display_name=display_name)
        session.add(player); await session.commit(); await session.refresh(player)
    if x_telegram_init_data:
        player.display_name = display_name
        identity = await session.get(TelegramIdentity, player.id)
        if not identity:
            identity = TelegramIdentity(player_id=player.id)
            session.add(identity)
        identity.avatar_url = avatar_url
        identity.synced_at = datetime.now(timezone.utc)
        await session.commit()
    return player

async def farm_state(p: Player, session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    ready_at = p.wheat_ready_at
    # SQLite does not round-trip timezone data, while PostgreSQL does. Normalize
    # both representations so the same gameplay rule works in every environment.
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    ready = bool(ready_at and ready_at <= now)
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == p.id, FarmStock.item_key == 'wheat'))
    recent = list((await session.scalars(select(FarmLedger).where(FarmLedger.player_id == p.id).order_by(FarmLedger.id.desc()).limit(5))).all())
    return {'level':p.farm_level,'xp':p.farm_xp,'coins':p.farm_coins,'diamonds':p.farm_diamonds,'inventory': {'wheat': wheat.amount if wheat else 0}, 'plot':{'crop':'wheat' if ready_at else None,'ready_at':ready_at,'ready':ready}, 'ledger': [{'type': entry.entry_type, 'coins_delta': entry.coins_delta, 'xp_delta': entry.xp_delta} for entry in recent]}

def record_farm_ledger(session: AsyncSession, player: Player, entry_type: str, coins_delta: int = 0, xp_delta: int = 0) -> None:
    session.add(FarmLedger(player_id=player.id, entry_type=entry_type, coins_delta=coins_delta, xp_delta=xp_delta))

async def farm_orders_state(player: Player, session: AsyncSession) -> dict:
    order = await session.scalar(select(FarmOrder).where(FarmOrder.player_id == player.id, FarmOrder.order_key == 'wheat_delivery'))
    if not order:
        order = FarmOrder(player_id=player.id, order_key='wheat_delivery')
        session.add(order)
        await session.commit()
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    return {'orders': [{'key': 'wheat_delivery', 'title': 'Town Bakery Delivery', 'required': {'wheat': 2}, 'available': {'wheat': wheat.amount if wheat else 0}, 'reward': {'coins': 120, 'xp': 40}, 'claimed': order.claimed}]}

async def pet_state(player: Player, session: AsyncSession) -> dict:
    stacks = list((await session.scalars(select(PetStack).where(PetStack.player_id == player.id).order_by(PetStack.tier))).all())
    if not stacks:
        session.add(PetStack(player_id=player.id, tier=1, amount=6))
        await session.commit()
        stacks = list((await session.scalars(select(PetStack).where(PetStack.player_id == player.id).order_by(PetStack.tier))).all())
    return {'pets': [{'tier': stack.tier, 'amount': stack.amount} for stack in stacks if stack.amount > 0], 'merge_count': sum(stack.amount * stack.tier for stack in stacks)}

async def card_state(player: Player, session: AsyncSession) -> dict:
    cards = list((await session.scalars(select(Card).where(Card.player_id == player.id).order_by(Card.card_key))).all())
    return {'materials': player.card_materials, 'chapter': player.card_chapter, 'cards': [{'key': card.card_key, 'level': card.level} for card in cards]}

async def record_play(player: Player, session: AsyncSession, game: str) -> None:
    today = datetime.now(timezone.utc).date()
    activity = await session.scalar(select(GameActivity).where(GameActivity.player_id == player.id, GameActivity.game == game, GameActivity.played_on == today))
    if not activity:
        session.add(GameActivity(player_id=player.id, game=game, played_on=today))

async def checkin_state(player: Player, session: AsyncSession) -> dict:
    today = datetime.now(timezone.utc).date()
    played_today = bool(await session.scalar(select(GameActivity.id).where(GameActivity.player_id == player.id, GameActivity.played_on == today)))
    claimed_days = set((await session.scalars(select(DailyCheckin.claimed_on).where(DailyCheckin.player_id == player.id))).all())
    streak = 0
    cursor = today
    while cursor in claimed_days:
        streak += 1
        cursor -= timedelta(days=1)
    return {'played_today': played_today, 'claimed_today': today in claimed_days, 'streak': streak, 'can_claim': played_today and today not in claimed_days}

async def get_or_create_profile(player: Player, session: AsyncSession) -> PlayerProfile:
    profile = await session.get(PlayerProfile, player.id)
    if not profile:
        profile = PlayerProfile(player_id=player.id)
        session.add(profile)
        await session.commit()
    return profile

async def get_or_create_visitor_preference(player: Player, session: AsyncSession) -> VisitorPreference:
    preference = await session.get(VisitorPreference, player.id)
    if not preference:
        preference = VisitorPreference(player_id=player.id, enabled=True)
        session.add(preference)
        await session.commit()
    return preference

async def profile_state(player: Player, session: AsyncSession) -> dict:
    profile = await get_or_create_profile(player, session)
    identity = await session.get(TelegramIdentity, player.id)
    visitor_preference = await get_or_create_visitor_preference(player, session)
    pets = list((await session.scalars(select(PetStack).where(PetStack.player_id == player.id))).all())
    cards = list((await session.scalars(select(Card).where(Card.player_id == player.id))).all())
    return {
        'name': player.display_name,
        'avatar_url': identity.avatar_url if identity else None,
        'honors': {'farm_level': player.farm_level, 'highest_pet_tier': max((pet.tier for pet in pets if pet.amount > 0), default=0), 'crafted_cards': len(cards)},
        'privacy': {'farm_public': profile.farm_public, 'collection_public': profile.collection_public},
        'visitor_history_enabled': visitor_preference.enabled,
        'checkin': await checkin_state(player, session),
    }

async def friendship_exists(player_a: int, player_b: int, session: AsyncSession) -> bool:
    low, high = sorted((player_a, player_b))
    return bool(await session.scalar(select(Friendship.id).where(Friendship.player_low_id == low, Friendship.player_high_id == high)))

async def friend_target(friend_telegram_id: str, player: Player, session: AsyncSession) -> Player:
    friend = await session.scalar(select(Player).where(Player.telegram_id == friend_telegram_id))
    if not friend:
        raise HTTPException(404, 'Friend has not opened RetroHub yet')
    if friend.id == player.id:
        raise HTTPException(422, 'You cannot add yourself as a friend')
    return friend

@app.get('/health', response_model=Health)
async def health() -> Health: return Health(status='ok', service='retrohub-api', timestamp=datetime.now(timezone.utc))

@app.get('/api/hub')
async def hub(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return {'title':'RetroHub Test','player':{'name':player.display_name}, 'checkin': await checkin_state(player, session), 'games':[{'id':'farm','state':'open'},{'id':'pet-merge','state':'open'},{'id':'card-arena','state':'open'}]}

@app.get('/api/checkin')
async def get_checkin(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await checkin_state(player, session)

@app.get('/api/profile')
async def get_profile(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await profile_state(player, session)

@app.put('/api/profile/privacy')
async def update_profile_privacy(update: PrivacyUpdate, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    profile = await get_or_create_profile(player, session)
    profile.farm_public = update.farm_public
    profile.collection_public = update.collection_public
    await session.commit()
    return await profile_state(player, session)

@app.get('/api/profile/visitors')
async def get_profile_visitors(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    preference = await get_or_create_visitor_preference(player, session)
    if not preference.enabled:
        return {'enabled': False, 'visitors': []}
    visits = list((await session.scalars(select(ProfileVisit).where(ProfileVisit.owner_id == player.id).order_by(ProfileVisit.visited_at.desc()))).all())
    visitors = []
    for visit in visits:
        visitor = await session.get(Player, visit.visitor_id)
        identity = await session.get(TelegramIdentity, visitor.id)
        visitors.append({'name': visitor.display_name, 'avatar_url': identity.avatar_url if identity else None, 'visited_at': visit.visited_at})
    return {'enabled': True, 'visitors': visitors}

@app.put('/api/profile/visitors')
async def update_visitor_preference(update: VisitorPreferenceUpdate, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    preference = await get_or_create_visitor_preference(player, session)
    preference.enabled = update.enabled
    await session.commit()
    return {'enabled': preference.enabled}

@app.get('/api/friends/invite')
async def friend_invite(player: Player = Depends(current_player)) -> dict:
    return {'start_param': f'friend_{player.telegram_id}', 'url': f'https://t.me/GameCenterMini_bot?startapp=friend_{player.telegram_id}'}

@app.post('/api/friends/accept/{friend_telegram_id}')
async def accept_friend(friend_telegram_id: str, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    friend = await friend_target(friend_telegram_id, player, session)
    low, high = sorted((player.id, friend.id))
    if not await friendship_exists(player.id, friend.id, session):
        session.add(Friendship(player_low_id=low, player_high_id=high))
        await session.commit()
    return {'friend': {'telegram_id': friend.telegram_id, 'name': friend.display_name}, 'accepted': True}

@app.get('/api/friends')
async def get_friends(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    links = list((await session.scalars(select(Friendship).where((Friendship.player_low_id == player.id) | (Friendship.player_high_id == player.id)))).all())
    friend_ids = [link.player_high_id if link.player_low_id == player.id else link.player_low_id for link in links]
    friends = [await session.get(Player, friend_id) for friend_id in friend_ids]
    result = []
    for friend in friends:
        profile = await get_or_create_profile(friend, session)
        identity = await session.get(TelegramIdentity, friend.id)
        result.append({'telegram_id': friend.telegram_id, 'name': friend.display_name, 'avatar_url': identity.avatar_url if identity else None, 'farm_public': profile.farm_public})
    return {'friends': result}

@app.get('/api/friends/{friend_telegram_id}/farm')
async def visit_friend_farm(friend_telegram_id: str, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    friend = await friend_target(friend_telegram_id, player, session)
    if not await friendship_exists(player.id, friend.id, session):
        raise HTTPException(403, 'Add this player as a friend first')
    profile = await get_or_create_profile(friend, session)
    if not profile.farm_public:
        raise HTTPException(403, 'This friend keeps their farm private')
    preference = await get_or_create_visitor_preference(friend, session)
    if preference.enabled:
        session.add(ProfileVisit(owner_id=friend.id, visitor_id=player.id))
        await session.commit()
    state = await farm_state(friend, session)
    return {'owner': friend.display_name, 'farm': {'level': state['level'], 'inventory': state['inventory'], 'plot': state['plot']}}

@app.post('/api/friends/{friend_telegram_id}/help/water')
async def water_friend_farm(friend_telegram_id: str, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    friend = await friend_target(friend_telegram_id, player, session)
    if not await friendship_exists(player.id, friend.id, session):
        raise HTTPException(403, 'Add this player as a friend first')
    profile = await get_or_create_profile(friend, session)
    if not profile.farm_public:
        raise HTTPException(403, 'This friend keeps their farm private')
    today = datetime.now(timezone.utc).date()
    helped = await session.scalar(select(FarmHelp).where(FarmHelp.helper_id == player.id, FarmHelp.target_id == friend.id, FarmHelp.help_type == 'water', FarmHelp.helped_on == today))
    if helped:
        raise HTTPException(409, 'You already watered this friend today')
    now = datetime.now(timezone.utc)
    ready_at = friend.wheat_ready_at
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    seconds_saved = 0
    if ready_at and ready_at > now:
        boosted = ready_at - timedelta(seconds=5)
        friend.wheat_ready_at = max(boosted, now)
        seconds_saved = 5
    session.add(FarmHelp(helper_id=player.id, target_id=friend.id, help_type='water', helped_on=today))
    await session.commit()
    return {'owner': friend.display_name, 'help': 'water', 'seconds_saved': seconds_saved, 'relationship_progress': 1}

@app.post('/api/checkin/claim')
async def claim_checkin(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    state = await checkin_state(player, session)
    if not state['played_today']:
        raise HTTPException(409, 'Play any game before claiming today\'s reward')
    if state['claimed_today']:
        raise HTTPException(409, 'Today\'s check-in is already claimed')
    reward = 5 if state['streak'] == 6 else 1
    session.add(DailyCheckin(player_id=player.id, claimed_on=datetime.now(timezone.utc).date(), collection_awarded=reward))
    await session.commit()
    return {**await checkin_state(player, session), 'collection_awarded': reward}

@app.get('/api/leaderboards/farm')
async def farm_leaderboard(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    players = list((await session.scalars(select(Player).order_by(Player.farm_level.desc(), Player.farm_xp.desc(), Player.id.asc()).limit(20))).all())
    entries = [{'rank': index + 1, 'name': row.display_name, 'level': row.farm_level, 'xp': row.farm_xp, 'is_me': row.id == player.id} for index, row in enumerate(players)]
    return {'period': 'all_time', 'metric': 'farm_level', 'entries': entries}

@app.get('/api/farm')
async def get_farm(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await farm_state(player, session)

@app.get('/api/farm/orders')
async def get_farm_orders(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await farm_orders_state(player, session)

@app.post('/api/farm/plant')
async def plant(_: FarmAction, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    now = datetime.now(timezone.utc)
    if player.wheat_ready_at: raise HTTPException(409, 'A crop is already growing')
    if player.farm_coins < 20: raise HTTPException(409, 'Not enough coins')
    from datetime import timedelta
    player.farm_coins -= 20; player.wheat_ready_at = now + timedelta(seconds=20)
    record_farm_ledger(session, player, 'plant_wheat', coins_delta=-20)
    await record_play(player, session, 'farm')
    await session.commit(); await session.refresh(player); return await farm_state(player, session)

@app.post('/api/farm/harvest')
async def harvest(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    now = datetime.now(timezone.utc)
    ready_at = player.wheat_ready_at
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    if not ready_at or ready_at > now: raise HTTPException(409, 'Crop is not ready')
    player.wheat_ready_at = None; player.farm_xp += 10
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    if not wheat:
        wheat = FarmStock(player_id=player.id, item_key='wheat', amount=0)
        session.add(wheat)
    wheat.amount += 1
    record_farm_ledger(session, player, 'harvest_wheat', xp_delta=10)
    await record_play(player, session, 'farm')
    if player.farm_xp >= player.farm_level * 30: player.farm_level += 1; player.farm_xp = 0
    await session.commit(); await session.refresh(player); return await farm_state(player, session)

@app.post('/api/farm/sell/wheat')
async def sell_wheat(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    if not wheat or wheat.amount < 1:
        raise HTTPException(409, 'Harvest wheat before selling it')
    wheat.amount -= 1
    player.farm_coins += 45
    record_farm_ledger(session, player, 'sell_wheat', coins_delta=45)
    await record_play(player, session, 'farm')
    await session.commit()
    return await farm_state(player, session)

@app.post('/api/farm/orders/wheat_delivery/claim')
async def claim_wheat_delivery(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    await farm_orders_state(player, session)
    order = await session.scalar(select(FarmOrder).where(FarmOrder.player_id == player.id, FarmOrder.order_key == 'wheat_delivery'))
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    if order.claimed:
        raise HTTPException(409, 'This order is already complete')
    if not wheat or wheat.amount < 2:
        raise HTTPException(409, 'Two wheat are required for this order')
    wheat.amount -= 2
    order.claimed = True
    player.farm_coins += 120
    player.farm_xp += 40
    record_farm_ledger(session, player, 'order_wheat_delivery', coins_delta=120, xp_delta=40)
    await record_play(player, session, 'farm')
    await session.commit()
    return {**await farm_state(player, session), **await farm_orders_state(player, session)}

@app.get('/api/pets')
async def get_pets(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await pet_state(player, session)

@app.post('/api/pets/merge/{tier}')
async def merge_pets(tier: int, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    if tier < 1 or tier > 9:
        raise HTTPException(422, 'Unsupported pet tier')
    await pet_state(player, session)
    source = await session.scalar(select(PetStack).where(PetStack.player_id == player.id, PetStack.tier == tier))
    if not source or source.amount < 2:
        raise HTTPException(409, 'Two matching pets are required')
    target = await session.scalar(select(PetStack).where(PetStack.player_id == player.id, PetStack.tier == tier + 1))
    if not target:
        target = PetStack(player_id=player.id, tier=tier + 1, amount=0)
        session.add(target)
    source.amount -= 2
    target.amount += 1
    await record_play(player, session, 'pet-merge')
    await session.commit()
    return await pet_state(player, session)

@app.get('/api/cards')
async def get_cards(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await card_state(player, session)

@app.post('/api/cards/battle')
async def battle_cards(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    player.card_materials += 15
    if player.card_chapter < 12:
        player.card_chapter += 1
    await record_play(player, session, 'card-arena')
    await session.commit()
    return await card_state(player, session)

@app.post('/api/cards/craft/{card_key}')
async def craft_card(card_key: str, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    allowed_cards = {'clockwork_fox', 'river_knight', 'arcade_mage'}
    if card_key not in allowed_cards:
        raise HTTPException(422, 'This card cannot be crafted')
    cost = 30
    if player.card_materials < cost:
        raise HTTPException(409, 'Not enough crafting materials')
    card = await session.scalar(select(Card).where(Card.player_id == player.id, Card.card_key == card_key))
    player.card_materials -= cost
    if card:
        card.level += 1
    else:
        session.add(Card(player_id=player.id, card_key=card_key, level=1))
    await record_play(player, session, 'card-arena')
    await session.commit()
    return await card_state(player, session)
