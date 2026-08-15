import os
import hmac
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
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

class PetProfile(Base):
    __tablename__ = 'pet_profiles'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    coins: Mapped[int] = mapped_column(Integer, default=500)
    last_idle_claim_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Card(Base):
    __tablename__ = 'cards'
    __table_args__ = (UniqueConstraint('player_id', 'card_key', name='uq_player_card_key'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    card_key: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer, default=1)

class CardTowerRun(Base):
    __tablename__ = 'card_tower_runs'
    __table_args__ = (UniqueConstraint('player_id', 'week_key', name='uq_card_tower_week'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    week_key: Mapped[str] = mapped_column(String(16), index=True)
    floor: Mapped[int] = mapped_column(Integer, default=1)
    points: Mapped[int] = mapped_column(Integer, default=0)
    ended: Mapped[bool] = mapped_column(default=False)

class GameActivity(Base):
    __tablename__ = 'game_activities'
    __table_args__ = (UniqueConstraint('player_id', 'game', 'played_on', name='uq_daily_game_activity'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    game: Mapped[str] = mapped_column(String(32))
    played_on: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())

class BehaviorEvent(Base):
    __tablename__ = 'behavior_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    game: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class SupportTicket(Base):
    __tablename__ = 'support_tickets'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    game: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AdminAuditLog(Base):
    __tablename__ = 'admin_audit_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64))
    before_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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

class FarmPlot(Base):
    __tablename__ = 'farm_plots'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    crop: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class FarmCompanion(Base):
    __tablename__ = 'farm_companions'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    companion_key: Mapped[str] = mapped_column(String(24), unique=False)
    adopted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PlayerOnboarding(Base):
    __tablename__ = 'player_onboarding'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    step: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(default=False)

class FarmOrder(Base):
    __tablename__ = 'farm_orders'
    __table_args__ = (UniqueConstraint('player_id', 'order_key', name='uq_farm_order'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    order_key: Mapped[str] = mapped_column(String(40))
    claimed: Mapped[bool] = mapped_column(default=False)

class FarmDailyOrder(Base):
    __tablename__ = 'farm_daily_orders'
    __table_args__ = (UniqueConstraint('player_id', 'order_day', name='uq_daily_farm_order'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    order_day: Mapped[date] = mapped_column(Date, index=True)
    claimed: Mapped[bool] = mapped_column(default=False)

class FarmCompetitionScore(Base):
    __tablename__ = 'farm_competition_scores'
    __table_args__ = (UniqueConstraint('player_id', 'period', 'period_key', name='uq_farm_competition_period'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), index=True)
    period: Mapped[str] = mapped_column(String(12), index=True)
    period_key: Mapped[str] = mapped_column(String(16), index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)

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

class AgeConsent(Base):
    __tablename__ = 'age_consents'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class VisitorPreference(Base):
    __tablename__ = 'visitor_preferences'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)

class DataPreference(Base):
    __tablename__ = 'data_preferences'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    personalized_recommendations: Mapped[bool] = mapped_column(default=True)

class NotificationPreference(Base):
    __tablename__ = 'notification_preferences'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    crop_mature: Mapped[bool] = mapped_column(default=True)
    idle_full: Mapped[bool] = mapped_column(default=True)
    daily_checkin: Mapped[bool] = mapped_column(default=True)
    activities: Mapped[bool] = mapped_column(default=False)
    seasons: Mapped[bool] = mapped_column(default=False)

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

class FarmSocialState(Base):
    __tablename__ = 'farm_social_states'
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    friendship_energy: Mapped[int] = mapped_column(Integer, default=10)
    refreshed_on: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title='RetroHub Test API', version='0.2.0', lifespan=lifespan)
CROPS = {
    'wheat': {'seed_cost': 20, 'grow_seconds': 20, 'yield_amount': 1, 'sell_price': 45, 'xp': 10, 'unlock_level': 1},
    'carrot': {'seed_cost': 45, 'grow_seconds': 45, 'yield_amount': 2, 'sell_price': 40, 'xp': 18, 'unlock_level': 2},
    'strawberry': {'seed_cost': 100, 'grow_seconds': 120, 'yield_amount': 2, 'sell_price': 100, 'xp': 30, 'unlock_level': 3},
}
FARM_COMPANIONS = {
    'dog': {'name': 'Pip the Dog', 'effect': '10% shorter crop growth'},
    'cat': {'name': 'Momo the Cat', 'effect': '+1 crop at harvest'},
    'rabbit': {'name': 'Bun the Rabbit', 'effect': '+10% order coin rewards'},
}
FAQ = {
    'en': [
        {'question': 'How do I start farming?', 'answer': 'Plant a crop, wait for it to mature, then harvest and sell or deliver it.'},
        {'question': 'Can I reset game data myself?', 'answer': 'No. Submit a reset request and support will review it.'},
        {'question': 'How does friendship energy work?', 'answer': 'It refreshes daily and is used for gentle farm help such as watering.'},
    ],
    'zh': [
        {'question': '如何开始农场？', 'answer': '种植作物，等待成熟后收获，再出售或交付订单。'},
        {'question': '可以自行重置游戏数据吗？', 'answer': '不可以。请提交重置申请，由客服审核。'},
        {'question': '友情能量如何使用？', 'answer': '友情能量每日恢复，用于浇水等温和好友农场帮助。'},
    ],
    'ru': [
        {'question': 'Как начать ферму?', 'answer': 'Посадите культуру, дождитесь созревания, затем соберите и продайте или сдайте заказ.'},
        {'question': 'Можно самому сбросить данные?', 'answer': 'Нет. Отправьте заявку, и поддержка рассмотрит её.'},
        {'question': 'Как работает энергия дружбы?', 'answer': 'Она восстанавливается ежедневно и тратится на помощь друзьям на ферме.'},
    ],
}
class Health(BaseModel): status: str; service: str; timestamp: datetime
class FarmAction(BaseModel): crop: str = Field(default='wheat')
class PrivacyUpdate(BaseModel): farm_public: bool; collection_public: bool
class VisitorPreferenceUpdate(BaseModel): enabled: bool
class DataPreferenceUpdate(BaseModel): personalized_recommendations: bool
class ResetRequest(BaseModel): game: str = Field(pattern='^(farm|pets|cards|all)$')
class TicketStatusUpdate(BaseModel): status: str = Field(pattern='^(open|approved|rejected)$')
class NotificationPreferenceUpdate(BaseModel):
    crop_mature: bool
    idle_full: bool
    daily_checkin: bool
    activities: bool
    seasons: bool

async def db() -> AsyncIterator[AsyncSession]:
    async with Session() as session: yield session

async def admin_actor(x_admin_password: str | None = Header(default=None)) -> str:
    configured_password = os.getenv('ADMIN_PASSWORD')
    if not configured_password:
        raise HTTPException(503, 'Admin access is not configured')
    if not x_admin_password or not hmac.compare_digest(x_admin_password, configured_password):
        raise HTTPException(401, 'Invalid administrator password')
    return os.getenv('ADMIN_USERNAME', 'administrator')

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

async def eligible_player(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> Player:
    if not is_debug() and not await session.get(AgeConsent, player.id):
        raise HTTPException(403, 'Confirm that you are 18 or older before playing')
    return player

async def get_farm_plot(player: Player, session: AsyncSession) -> FarmPlot:
    plot = await session.get(FarmPlot, player.id)
    if plot:
        return plot
    plot = FarmPlot(player_id=player.id)
    # Preserve crops planted by the earlier one-crop beta implementation.
    if player.wheat_ready_at:
        plot.crop = 'wheat'
        plot.ready_at = player.wheat_ready_at
        player.wheat_ready_at = None
    session.add(plot)
    await session.commit()
    return plot

async def farm_companion_state(player: Player, session: AsyncSession) -> dict | None:
    companion = await session.get(FarmCompanion, player.id)
    if not companion:
        return None
    return {'key': companion.companion_key, **FARM_COMPANIONS[companion.companion_key]}

ONBOARDING_STEPS = ('Plant your first wheat crop', 'Harvest the ripe crop', 'Sell one wheat from your inventory', 'Welcome to RetroHub')

async def onboarding_state(player: Player, session: AsyncSession) -> dict:
    progress = await session.get(PlayerOnboarding, player.id)
    if not progress:
        progress = PlayerOnboarding(player_id=player.id, step=0, completed=False)
        session.add(progress)
        await session.commit()
    return {'step': progress.step, 'completed': progress.completed, 'next_action': ONBOARDING_STEPS[min(progress.step, len(ONBOARDING_STEPS) - 1)]}

async def advance_onboarding(player: Player, session: AsyncSession, action: str) -> None:
    progress = await session.get(PlayerOnboarding, player.id)
    if not progress:
        progress = PlayerOnboarding(player_id=player.id, step=0, completed=False)
        session.add(progress)
    expected = {0: 'plant', 1: 'harvest', 2: 'sell'}
    if expected.get(progress.step) == action:
        progress.step += 1
        if progress.step >= 3:
            progress.completed = True

async def farm_state(p: Player, session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    plot = await get_farm_plot(p, session)
    ready_at = plot.ready_at
    # SQLite does not round-trip timezone data, while PostgreSQL does. Normalize
    # both representations so the same gameplay rule works in every environment.
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    ready = bool(ready_at and ready_at <= now)
    stock = list((await session.scalars(select(FarmStock).where(FarmStock.player_id == p.id))).all())
    inventory = {crop: 0 for crop in CROPS}
    inventory.update({item.item_key: item.amount for item in stock})
    recent = list((await session.scalars(select(FarmLedger).where(FarmLedger.player_id == p.id).order_by(FarmLedger.id.desc()).limit(5))).all())
    return {'level':p.farm_level,'xp':p.farm_xp,'coins':p.farm_coins,'diamonds':p.farm_diamonds,'inventory': inventory, 'crops': [{'key': key, **details, 'unlocked': p.farm_level >= details['unlock_level']} for key, details in CROPS.items()], 'plot':{'crop': plot.crop,'ready_at':ready_at,'ready':ready}, 'companion': await farm_companion_state(p, session), 'companions': [{'key': key, **details} for key, details in FARM_COMPANIONS.items()], 'ledger': [{'type': entry.entry_type, 'coins_delta': entry.coins_delta, 'xp_delta': entry.xp_delta} for entry in recent]}

def record_farm_ledger(session: AsyncSession, player: Player, entry_type: str, coins_delta: int = 0, xp_delta: int = 0) -> None:
    session.add(FarmLedger(player_id=player.id, entry_type=entry_type, coins_delta=coins_delta, xp_delta=xp_delta))

async def farm_orders_state(player: Player, session: AsyncSession) -> dict:
    order = await session.scalar(select(FarmOrder).where(FarmOrder.player_id == player.id, FarmOrder.order_key == 'wheat_delivery'))
    if not order:
        order = FarmOrder(player_id=player.id, order_key='wheat_delivery')
        session.add(order)
        await session.commit()
    today = datetime.now(timezone.utc).date()
    daily = await session.scalar(select(FarmDailyOrder).where(FarmDailyOrder.player_id == player.id, FarmDailyOrder.order_day == today))
    if not daily:
        daily = FarmDailyOrder(player_id=player.id, order_day=today)
        session.add(daily)
        await session.commit()
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    available = {'wheat': wheat.amount if wheat else 0}
    companion = await session.get(FarmCompanion, player.id)
    reward_multiplier = 1.1 if companion and companion.companion_key == 'rabbit' else 1
    return {'orders': [
        {'key': 'wheat_delivery', 'title': 'Town Bakery Delivery', 'required': {'wheat': 2}, 'available': available, 'reward': {'coins': int(120 * reward_multiplier), 'xp': 40, 'competition_points': 10}, 'claimed': order.claimed, 'daily': False},
        {'key': 'daily_wheat_delivery', 'title': 'Daily Market Delivery', 'required': {'wheat': 3}, 'available': available, 'reward': {'coins': int(220 * reward_multiplier), 'xp': 60, 'competition_points': 30}, 'claimed': daily.claimed, 'daily': True},
    ]}

def competition_period_key(period: str, today: date) -> str:
    if period == 'week':
        year, week, _ = today.isocalendar()
        return f'{year}-W{week:02d}'
    return today.strftime('%Y-%m')

async def add_competition_points(player: Player, session: AsyncSession, points: int) -> None:
    today = datetime.now(timezone.utc).date()
    for period in ('week', 'month'):
        key = competition_period_key(period, today)
        score = await session.scalar(select(FarmCompetitionScore).where(FarmCompetitionScore.player_id == player.id, FarmCompetitionScore.period == period, FarmCompetitionScore.period_key == key))
        if not score:
            score = FarmCompetitionScore(player_id=player.id, period=period, period_key=key, points=0)
            session.add(score)
        score.points += points

async def pet_state(player: Player, session: AsyncSession) -> dict:
    profile = await session.get(PetProfile, player.id)
    if not profile:
        profile = PetProfile(player_id=player.id)
        session.add(profile)
        await session.commit()
    stacks = list((await session.scalars(select(PetStack).where(PetStack.player_id == player.id).order_by(PetStack.tier))).all())
    if not stacks:
        session.add(PetStack(player_id=player.id, tier=1, amount=6))
        await session.commit()
        stacks = list((await session.scalars(select(PetStack).where(PetStack.player_id == player.id).order_by(PetStack.tier))).all())
    now = datetime.now(timezone.utc)
    claimed_at = profile.last_idle_claim_at
    if claimed_at.tzinfo is None:
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)
    offline_seconds = min(86_400, max(0, int((now - claimed_at).total_seconds())))
    production_per_minute = max(1, sum(stack.amount * stack.tier for stack in stacks))
    claimable = (offline_seconds // 60) * production_per_minute
    return {'pets': [{'tier': stack.tier, 'amount': stack.amount} for stack in stacks if stack.amount > 0], 'merge_count': sum(stack.amount * stack.tier for stack in stacks), 'coins': profile.coins, 'production_per_minute': production_per_minute, 'offline_seconds': offline_seconds, 'offline_cap_seconds': 86_400, 'idle_coins_claimable': claimable, 'egg_cost': 100}

async def card_state(player: Player, session: AsyncSession) -> dict:
    cards = list((await session.scalars(select(Card).where(Card.player_id == player.id).order_by(Card.card_key))).all())
    return {'materials': player.card_materials, 'chapter': player.card_chapter, 'cards': [{'key': card.card_key, 'level': card.level} for card in cards]}

def current_week_key() -> str:
    year, week, _ = datetime.now(timezone.utc).date().isocalendar()
    return f'{year}-W{week:02d}'

async def card_tower_state(player: Player, session: AsyncSession) -> dict:
    week_key = current_week_key()
    run = await session.scalar(select(CardTowerRun).where(CardTowerRun.player_id == player.id, CardTowerRun.week_key == week_key))
    if not run:
        run = CardTowerRun(player_id=player.id, week_key=week_key)
        session.add(run)
        await session.commit()
    cards = list((await session.scalars(select(Card).where(Card.player_id == player.id))).all())
    strength = 1 + len(cards) + sum(max(0, card.level - 1) for card in cards)
    return {'week_key': week_key, 'floor': run.floor, 'points': run.points, 'ended': run.ended, 'strength': strength, 'is_elite_floor': run.floor >= 5, 'max_floor': 10}

async def record_play(player: Player, session: AsyncSession, game: str, action: str = 'play') -> None:
    today = datetime.now(timezone.utc).date()
    activity = await session.scalar(select(GameActivity).where(GameActivity.player_id == player.id, GameActivity.game == game, GameActivity.played_on == today))
    if not activity:
        session.add(GameActivity(player_id=player.id, game=game, played_on=today))
    session.add(BehaviorEvent(player_id=player.id, game=game, action=action))

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

async def get_or_create_data_preference(player: Player, session: AsyncSession) -> DataPreference:
    preference = await session.get(DataPreference, player.id)
    if not preference:
        preference = DataPreference(player_id=player.id, personalized_recommendations=True)
        session.add(preference)
        await session.commit()
    return preference

async def get_or_create_notification_preference(player: Player, session: AsyncSession) -> NotificationPreference:
    preference = await session.get(NotificationPreference, player.id)
    if not preference:
        preference = NotificationPreference(player_id=player.id, crop_mature=True, idle_full=True, daily_checkin=True, activities=False, seasons=False)
        session.add(preference)
        await session.commit()
    return preference

async def profile_state(player: Player, session: AsyncSession) -> dict:
    profile = await get_or_create_profile(player, session)
    identity = await session.get(TelegramIdentity, player.id)
    age_consent = await session.get(AgeConsent, player.id)
    visitor_preference = await get_or_create_visitor_preference(player, session)
    data_preference = await get_or_create_data_preference(player, session)
    pets = list((await session.scalars(select(PetStack).where(PetStack.player_id == player.id))).all())
    cards = list((await session.scalars(select(Card).where(Card.player_id == player.id))).all())
    return {
        'name': player.display_name,
        'avatar_url': identity.avatar_url if identity else None,
        'age_confirmed': bool(age_consent),
        'honors': {'farm_level': player.farm_level, 'highest_pet_tier': max((pet.tier for pet in pets if pet.amount > 0), default=0), 'crafted_cards': len(cards)},
        'privacy': {'farm_public': profile.farm_public, 'collection_public': profile.collection_public},
        'visitor_history_enabled': visitor_preference.enabled,
        'personalized_recommendations': data_preference.personalized_recommendations,
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

def friendship_energy_cap(player: Player) -> int:
    return 10 + max(0, player.farm_level - 1) * 2

async def social_state(player: Player, session: AsyncSession) -> FarmSocialState:
    state = await session.get(FarmSocialState, player.id)
    today = datetime.now(timezone.utc).date()
    cap = friendship_energy_cap(player)
    if not state:
        state = FarmSocialState(player_id=player.id, friendship_energy=cap, refreshed_on=today)
        session.add(state)
        await session.commit()
    elif state.refreshed_on != today:
        state.friendship_energy = cap
        state.refreshed_on = today
        await session.commit()
    return state

@app.get('/health', response_model=Health)
async def health() -> Health: return Health(status='ok', service='retrohub-api', timestamp=datetime.now(timezone.utc))

@app.get('/api/hub')
async def hub(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return {'title':'RetroHub Test','player':{'name':player.display_name}, 'checkin': await checkin_state(player, session), 'games':[{'id':'farm','state':'open'},{'id':'pet-merge','state':'open'},{'id':'card-arena','state':'open'}]}

@app.get('/api/checkin')
async def get_checkin(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    return await checkin_state(player, session)

@app.get('/api/onboarding')
async def get_onboarding(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    return await onboarding_state(player, session)

@app.get('/api/profile')
async def get_profile(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    return await profile_state(player, session)

@app.post('/api/profile/age-consent')
async def confirm_age_consent(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    if not await session.get(AgeConsent, player.id):
        session.add(AgeConsent(player_id=player.id))
        await session.commit()
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

@app.put('/api/profile/data-preferences')
async def update_data_preference(update: DataPreferenceUpdate, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    preference = await get_or_create_data_preference(player, session)
    preference.personalized_recommendations = update.personalized_recommendations
    await session.commit()
    return {'personalized_recommendations': preference.personalized_recommendations}

@app.get('/api/profile/notification-preferences')
async def get_notification_preference(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    preference = await get_or_create_notification_preference(player, session)
    return {'crop_mature': preference.crop_mature, 'idle_full': preference.idle_full, 'daily_checkin': preference.daily_checkin, 'activities': preference.activities, 'seasons': preference.seasons}

@app.put('/api/profile/notification-preferences')
async def update_notification_preference(update: NotificationPreferenceUpdate, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    preference = await get_or_create_notification_preference(player, session)
    preference.crop_mature = update.crop_mature
    preference.idle_full = update.idle_full
    preference.daily_checkin = update.daily_checkin
    preference.activities = update.activities
    preference.seasons = update.seasons
    await session.commit()
    return {'crop_mature': preference.crop_mature, 'idle_full': preference.idle_full, 'daily_checkin': preference.daily_checkin, 'activities': preference.activities, 'seasons': preference.seasons}

@app.get('/api/support/tickets/me')
async def get_my_support_tickets(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    tickets = list((await session.scalars(select(SupportTicket).where(SupportTicket.player_id == player.id).order_by(SupportTicket.created_at.desc()))).all())
    return {'tickets': [{'id': ticket.id, 'category': ticket.category, 'game': ticket.game, 'status': ticket.status, 'created_at': ticket.created_at} for ticket in tickets]}

@app.get('/api/support/faq')
async def get_support_faq(locale: str = Query(default='en')) -> dict:
    return {'locale': locale if locale in FAQ else 'en', 'entries': FAQ.get(locale, FAQ['en'])}

@app.post('/api/support/reset-request')
async def request_game_reset(request: ResetRequest, player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    existing = await session.scalar(select(SupportTicket).where(SupportTicket.player_id == player.id, SupportTicket.category == 'game_reset', SupportTicket.game == request.game, SupportTicket.status == 'open'))
    if existing:
        raise HTTPException(409, 'An open reset request already exists for this game')
    ticket = SupportTicket(player_id=player.id, category='game_reset', game=request.game, status='open')
    session.add(ticket)
    await session.commit()
    return {'id': ticket.id, 'category': ticket.category, 'game': ticket.game, 'status': ticket.status}

@app.get('/api/admin/support/tickets')
async def admin_list_support_tickets(actor: str = Depends(admin_actor), session: AsyncSession = Depends(db)) -> dict:
    tickets = list((await session.scalars(select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(100))).all())
    return {'actor': actor, 'tickets': [{'id': ticket.id, 'player_id': ticket.player_id, 'category': ticket.category, 'game': ticket.game, 'status': ticket.status, 'created_at': ticket.created_at} for ticket in tickets]}

@app.put('/api/admin/support/tickets/{ticket_id}')
async def admin_update_support_ticket(ticket_id: int, update: TicketStatusUpdate, actor: str = Depends(admin_actor), session: AsyncSession = Depends(db)) -> dict:
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, 'Support ticket not found')
    previous_status = ticket.status
    ticket.status = update.status
    session.add(AdminAuditLog(actor=actor, action='update_support_ticket', target_type='support_ticket', target_id=str(ticket.id), before_value=previous_status, after_value=update.status))
    await session.commit()
    return {'id': ticket.id, 'status': ticket.status}

@app.get('/api/friends/invite')
async def friend_invite(player: Player = Depends(eligible_player)) -> dict:
    return {'start_param': f'friend_{player.telegram_id}', 'url': f'https://t.me/GameCenterMini_bot?startapp=friend_{player.telegram_id}'}

@app.post('/api/friends/accept/{friend_telegram_id}')
async def accept_friend(friend_telegram_id: str, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    friend = await friend_target(friend_telegram_id, player, session)
    low, high = sorted((player.id, friend.id))
    if not await friendship_exists(player.id, friend.id, session):
        session.add(Friendship(player_low_id=low, player_high_id=high))
        await session.commit()
    return {'friend': {'telegram_id': friend.telegram_id, 'name': friend.display_name}, 'accepted': True}

@app.get('/api/friends')
async def get_friends(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    links = list((await session.scalars(select(Friendship).where((Friendship.player_low_id == player.id) | (Friendship.player_high_id == player.id)))).all())
    friend_ids = [link.player_high_id if link.player_low_id == player.id else link.player_low_id for link in links]
    friends = [await session.get(Player, friend_id) for friend_id in friend_ids]
    result = []
    for friend in friends:
        profile = await get_or_create_profile(friend, session)
        identity = await session.get(TelegramIdentity, friend.id)
        result.append({'telegram_id': friend.telegram_id, 'name': friend.display_name, 'avatar_url': identity.avatar_url if identity else None, 'farm_public': profile.farm_public})
    energy = await social_state(player, session)
    return {'friends': result, 'friendship_energy': energy.friendship_energy, 'friendship_energy_cap': friendship_energy_cap(player)}

@app.get('/api/friends/energy')
async def get_friendship_energy(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    energy = await social_state(player, session)
    return {'friendship_energy': energy.friendship_energy, 'friendship_energy_cap': friendship_energy_cap(player)}

@app.get('/api/friends/{friend_telegram_id}/farm')
async def visit_friend_farm(friend_telegram_id: str, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
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
async def water_friend_farm(friend_telegram_id: str, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
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
    energy = await social_state(player, session)
    if energy.friendship_energy < 1:
        raise HTTPException(409, 'Friendship energy is empty; it refreshes tomorrow')
    now = datetime.now(timezone.utc)
    plot = await get_farm_plot(friend, session)
    ready_at = plot.ready_at
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    seconds_saved = 0
    if ready_at and ready_at > now:
        boosted = ready_at - timedelta(seconds=5)
        plot.ready_at = max(boosted, now)
        seconds_saved = 5
    session.add(FarmHelp(helper_id=player.id, target_id=friend.id, help_type='water', helped_on=today))
    energy.friendship_energy -= 1
    await session.commit()
    return {'owner': friend.display_name, 'help': 'water', 'seconds_saved': seconds_saved, 'relationship_progress': 1, 'friendship_energy': energy.friendship_energy, 'friendship_energy_cap': friendship_energy_cap(player)}

@app.post('/api/checkin/claim')
async def claim_checkin(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
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
async def farm_leaderboard(period: str = Query(default='all_time'), scope: str = Query(default='global'), player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    if scope not in {'global', 'friends'}:
        raise HTTPException(422, 'Unsupported leaderboard scope')
    player_ids: list[int] | None = None
    if scope == 'friends':
        links = list((await session.scalars(select(Friendship).where((Friendship.player_low_id == player.id) | (Friendship.player_high_id == player.id)))).all())
        player_ids = [player.id, *[link.player_high_id if link.player_low_id == player.id else link.player_low_id for link in links]]
    if period == 'all_time':
        statement = select(Player)
        if player_ids is not None:
            statement = statement.where(Player.id.in_(player_ids))
        players = list((await session.scalars(statement.order_by(Player.farm_level.desc(), Player.farm_xp.desc(), Player.id.asc()).limit(20))).all())
        entries = [{'rank': index + 1, 'name': row.display_name, 'level': row.farm_level, 'xp': row.farm_xp, 'is_me': row.id == player.id} for index, row in enumerate(players)]
        return {'period': period, 'scope': scope, 'metric': 'farm_level', 'entries': entries}
    if period not in {'week', 'month'}:
        raise HTTPException(422, 'Unsupported leaderboard period')
    period_key = competition_period_key(period, datetime.now(timezone.utc).date())
    statement = select(FarmCompetitionScore, Player).join(Player, FarmCompetitionScore.player_id == Player.id).where(FarmCompetitionScore.period == period, FarmCompetitionScore.period_key == period_key)
    if player_ids is not None:
        statement = statement.where(FarmCompetitionScore.player_id.in_(player_ids))
    rows = (await session.execute(statement.order_by(FarmCompetitionScore.points.desc(), Player.id.asc()).limit(20))).all()
    entries = [{'rank': index + 1, 'name': row.Player.display_name, 'points': row.FarmCompetitionScore.points, 'is_me': row.Player.id == player.id} for index, row in enumerate(rows)]
    return {'period': period, 'scope': scope, 'period_key': period_key, 'metric': 'order_points', 'entries': entries}

@app.get('/api/farm')
async def get_farm(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    return await farm_state(player, session)

@app.get('/api/farm/orders')
async def get_farm_orders(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    return await farm_orders_state(player, session)

@app.post('/api/farm/companions/{companion_key}/adopt')
async def adopt_farm_companion(companion_key: str, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    if companion_key not in FARM_COMPANIONS:
        raise HTTPException(422, 'Unsupported companion')
    if await session.get(FarmCompanion, player.id):
        raise HTTPException(409, 'A farm companion has already been adopted')
    session.add(FarmCompanion(player_id=player.id, companion_key=companion_key))
    await record_play(player, session, 'farm', 'adopt_companion')
    await session.commit()
    return await farm_state(player, session)

@app.post('/api/farm/plant')
async def plant(action: FarmAction, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    now = datetime.now(timezone.utc)
    crop = CROPS.get(action.crop)
    if not crop: raise HTTPException(422, 'Unsupported crop')
    if player.farm_level < crop['unlock_level']: raise HTTPException(409, 'Raise your farm level to unlock this crop')
    plot = await get_farm_plot(player, session)
    if plot.crop: raise HTTPException(409, 'A crop is already growing')
    if player.farm_coins < crop['seed_cost']: raise HTTPException(409, 'Not enough coins')
    companion = await session.get(FarmCompanion, player.id)
    grow_seconds = crop['grow_seconds'] * 9 // 10 if companion and companion.companion_key == 'dog' else crop['grow_seconds']
    player.farm_coins -= crop['seed_cost']; plot.crop = action.crop; plot.ready_at = now + timedelta(seconds=grow_seconds)
    record_farm_ledger(session, player, f'plant_{action.crop}', coins_delta=-crop['seed_cost'])
    await advance_onboarding(player, session, 'plant')
    await record_play(player, session, 'farm', 'plant_crop')
    await session.commit(); await session.refresh(player); return await farm_state(player, session)

@app.post('/api/farm/harvest')
async def harvest(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    now = datetime.now(timezone.utc)
    plot = await get_farm_plot(player, session)
    ready_at = plot.ready_at
    if ready_at and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    if not ready_at or ready_at > now or not plot.crop: raise HTTPException(409, 'Crop is not ready')
    crop_key = plot.crop
    crop = CROPS[crop_key]
    plot.crop = None; plot.ready_at = None; player.farm_xp += crop['xp']
    stock = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == crop_key))
    if not stock:
        stock = FarmStock(player_id=player.id, item_key=crop_key, amount=0)
        session.add(stock)
    companion = await session.get(FarmCompanion, player.id)
    stock.amount += crop['yield_amount'] + (1 if companion and companion.companion_key == 'cat' else 0)
    record_farm_ledger(session, player, f'harvest_{crop_key}', xp_delta=crop['xp'])
    await advance_onboarding(player, session, 'harvest')
    await record_play(player, session, 'farm', 'harvest_crop')
    if player.farm_xp >= player.farm_level * 30: player.farm_level += 1; player.farm_xp = 0
    await session.commit(); await session.refresh(player); return await farm_state(player, session)

@app.post('/api/farm/sell/{crop_key}')
async def sell_crop(crop_key: str, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    crop = CROPS.get(crop_key)
    if not crop:
        raise HTTPException(422, 'Unsupported crop')
    stock = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == crop_key))
    if not stock or stock.amount < 1:
        raise HTTPException(409, f'Harvest {crop_key} before selling it')
    stock.amount -= 1
    player.farm_coins += crop['sell_price']
    record_farm_ledger(session, player, f'sell_{crop_key}', coins_delta=crop['sell_price'])
    await advance_onboarding(player, session, 'sell')
    await record_play(player, session, 'farm', 'sell_crop')
    await session.commit()
    return await farm_state(player, session)

@app.post('/api/farm/orders/wheat_delivery/claim')
async def claim_wheat_delivery(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    await farm_orders_state(player, session)
    order = await session.scalar(select(FarmOrder).where(FarmOrder.player_id == player.id, FarmOrder.order_key == 'wheat_delivery'))
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    if order.claimed:
        raise HTTPException(409, 'This order is already complete')
    if not wheat or wheat.amount < 2:
        raise HTTPException(409, 'Two wheat are required for this order')
    wheat.amount -= 2
    order.claimed = True
    companion = await session.get(FarmCompanion, player.id)
    coin_reward = 132 if companion and companion.companion_key == 'rabbit' else 120
    player.farm_coins += coin_reward
    player.farm_xp += 40
    record_farm_ledger(session, player, 'order_wheat_delivery', coins_delta=coin_reward, xp_delta=40)
    await add_competition_points(player, session, 10)
    await record_play(player, session, 'farm', 'claim_starter_order')
    await session.commit()
    return {**await farm_state(player, session), **await farm_orders_state(player, session)}

@app.post('/api/farm/orders/daily_wheat_delivery/claim')
async def claim_daily_wheat_delivery(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    today = datetime.now(timezone.utc).date()
    daily = await session.scalar(select(FarmDailyOrder).where(FarmDailyOrder.player_id == player.id, FarmDailyOrder.order_day == today))
    if not daily:
        await farm_orders_state(player, session)
        daily = await session.scalar(select(FarmDailyOrder).where(FarmDailyOrder.player_id == player.id, FarmDailyOrder.order_day == today))
    wheat = await session.scalar(select(FarmStock).where(FarmStock.player_id == player.id, FarmStock.item_key == 'wheat'))
    if daily.claimed:
        raise HTTPException(409, 'Today\'s market delivery is already complete')
    if not wheat or wheat.amount < 3:
        raise HTTPException(409, 'Three wheat are required for today\'s market delivery')
    wheat.amount -= 3
    daily.claimed = True
    companion = await session.get(FarmCompanion, player.id)
    coin_reward = 242 if companion and companion.companion_key == 'rabbit' else 220
    player.farm_coins += coin_reward
    player.farm_xp += 60
    record_farm_ledger(session, player, 'order_daily_wheat_delivery', coins_delta=coin_reward, xp_delta=60)
    await add_competition_points(player, session, 30)
    await record_play(player, session, 'farm', 'claim_daily_order')
    await session.commit()
    return {**await farm_state(player, session), **await farm_orders_state(player, session)}

@app.get('/api/pets')
async def get_pets(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    return await pet_state(player, session)

@app.post('/api/pets/idle/claim')
async def claim_pet_idle(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    state = await pet_state(player, session)
    profile = await session.get(PetProfile, player.id)
    profile.coins += state['idle_coins_claimable']
    profile.last_idle_claim_at = datetime.now(timezone.utc)
    await record_play(player, session, 'pet-merge', 'claim_idle_income')
    await session.commit()
    return await pet_state(player, session)

@app.post('/api/pets/eggs/basic')
async def buy_basic_pet_egg(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    await pet_state(player, session)
    profile = await session.get(PetProfile, player.id)
    if profile.coins < 100:
        raise HTTPException(409, 'Not enough pet coins for a basic egg')
    stack = await session.scalar(select(PetStack).where(PetStack.player_id == player.id, PetStack.tier == 1))
    profile.coins -= 100
    stack.amount += 1
    await record_play(player, session, 'pet-merge', 'buy_basic_egg')
    await session.commit()
    return await pet_state(player, session)

@app.post('/api/pets/merge/{tier}')
async def merge_pets(tier: int, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
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
    await record_play(player, session, 'pet-merge', 'merge_pet')
    await session.commit()
    return await pet_state(player, session)

@app.get('/api/cards')
async def get_cards(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    return {**await card_state(player, session), 'tower': await card_tower_state(player, session)}

@app.post('/api/cards/tower/challenge')
async def challenge_card_tower(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    tower = await card_tower_state(player, session)
    if tower['ended']:
        raise HTTPException(409, 'This week\'s tower run has ended')
    run = await session.scalar(select(CardTowerRun).where(CardTowerRun.player_id == player.id, CardTowerRun.week_key == tower['week_key']))
    required_strength = (run.floor + 1) // 2
    if tower['strength'] < required_strength:
        if run.floor >= 5:
            run.ended = True
            await session.commit()
            return {**await card_state(player, session), 'tower': await card_tower_state(player, session), 'result': 'elite_failed', 'reward_materials': 0}
        return {**await card_state(player, session), 'tower': tower, 'result': 'retry', 'reward_materials': 0}
    reward = 10 + run.floor * 5
    player.card_materials += reward
    run.points += run.floor * 10
    run.floor += 1
    if run.floor > 10:
        run.ended = True
    await record_play(player, session, 'card-arena', 'tower_victory')
    await session.commit()
    return {**await card_state(player, session), 'tower': await card_tower_state(player, session), 'result': 'victory', 'reward_materials': reward}

@app.get('/api/leaderboards/cards/tower')
async def card_tower_leaderboard(player: Player = Depends(current_player), session: AsyncSession = Depends(db)) -> dict:
    week_key = current_week_key()
    rows = (await session.execute(select(CardTowerRun, Player).join(Player, CardTowerRun.player_id == Player.id).where(CardTowerRun.week_key == week_key).order_by(CardTowerRun.points.desc(), CardTowerRun.floor.desc(), Player.id.asc()).limit(20))).all()
    entries = [{'rank': index + 1, 'name': row.Player.display_name, 'points': row.CardTowerRun.points, 'floor': row.CardTowerRun.floor, 'is_me': row.Player.id == player.id} for index, row in enumerate(rows)]
    return {'period': week_key, 'metric': 'tower_points', 'entries': entries}

@app.post('/api/cards/battle')
async def battle_cards(player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
    player.card_materials += 15
    if player.card_chapter < 12:
        player.card_chapter += 1
    await record_play(player, session, 'card-arena', 'pve_chapter')
    await session.commit()
    return {**await card_state(player, session), 'tower': await card_tower_state(player, session)}

@app.post('/api/cards/craft/{card_key}')
async def craft_card(card_key: str, player: Player = Depends(eligible_player), session: AsyncSession = Depends(db)) -> dict:
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
    await record_play(player, session, 'card-arena', 'craft_card')
    await session.commit()
    return {**await card_state(player, session), 'tower': await card_tower_state(player, session)}
