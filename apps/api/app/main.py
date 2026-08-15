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

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title='RetroHub Test API', version='0.2.0', lifespan=lifespan)
class Health(BaseModel): status: str; service: str; timestamp: datetime
class FarmAction(BaseModel): crop: str = Field(default='wheat', pattern='^wheat$')

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
    elif is_debug():
        telegram_id = x_telegram_user or 'demo-player'
        display_name = 'Demo Player'
    else:
        raise HTTPException(401, 'Telegram Mini App authentication is required')
    player = (await session.scalar(select(Player).where(Player.telegram_id == telegram_id)))
    if not player:
        player = Player(telegram_id=telegram_id, display_name=display_name)
        session.add(player); await session.commit(); await session.refresh(player)
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
    return {'level':p.farm_level,'xp':p.farm_xp,'coins':p.farm_coins,'diamonds':p.farm_diamonds,'inventory': {'wheat': wheat.amount if wheat else 0}, 'plot':{'crop':'wheat' if ready_at else None,'ready_at':ready_at,'ready':ready}}

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

@app.get('/health', response_model=Health)
async def health() -> Health: return Health(status='ok', service='retrohub-api', timestamp=datetime.now(timezone.utc))

@app.get('/api/hub')
async def hub(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return {'title':'RetroHub Test','player':{'name':player.display_name}, 'checkin': await checkin_state(player, session), 'games':[{'id':'farm','state':'open'},{'id':'pet-merge','state':'open'},{'id':'card-arena','state':'open'}]}

@app.get('/api/checkin')
async def get_checkin(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await checkin_state(player, session)

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
    await record_play(player, session, 'farm')
    await session.commit(); await session.refresh(player); return await farm_state(player, session)

@app.post('/api/farm/harvest')
async def harvest(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    now = datetime.now(timezone.utc)
    ready_at = player.wheat_ready_at
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    if not ready_at or ready_at > now: raise HTTPException(409, 'Crop is not ready')
    player.wheat_ready_at = None; player.farm_coins += 45; player.farm_xp += 10
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    if not wheat:
        wheat = FarmStock(player_id=player.id, item_key='wheat', amount=0)
        session.add(wheat)
    wheat.amount += 1
    await record_play(player, session, 'farm')
    if player.farm_xp >= player.farm_level * 30: player.farm_level += 1; player.farm_xp = 0
    await session.commit(); await session.refresh(player); return await farm_state(player, session)

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
