import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Farm = { level: number; xp: number; coins: number; diamonds: number; inventory: Record<string, number>; crops: { key: string; seed_cost: number; sell_price: number; unlock_level: number; unlocked: boolean }[]; plot: { crop: string | null; ready: boolean }; companion: { key: string; name: string; effect: string } | null; companions: { key: string; name: string; effect: string }[]; ledger: { type: string; coins_delta: number; xp_delta: number }[] };
type FarmOrders = { orders: { key: string; title: string; required: { wheat: number }; available: { wheat: number }; reward: { coins: number; xp: number }; claimed: boolean }[] };
type Pets = { pets: { tier: number; amount: number }[]; coins: number; production_per_minute: number; idle_coins_claimable: number; offline_cap_seconds: number; egg_cost: number };
type Cards = { materials: number; chapter: number; cards: { key: string; level: number }[]; tower?: { floor: number; points: number; ended: boolean; strength: number; is_elite_floor: boolean; max_floor: number } };
type Checkin = { played_today: boolean; claimed_today: boolean; streak: number; can_claim: boolean; collection_awarded?: number };
type Leaderboard = { period: string; metric: string; entries: { rank: number; name: string; level?: number; xp?: number; points?: number; is_me: boolean }[] };
type Profile = { name: string; avatar_url: string | null; age_confirmed: boolean; personalized_recommendations: boolean; honors: { farm_level: number; highest_pet_tier: number; crafted_cards: number }; privacy: { farm_public: boolean; collection_public: boolean }; visitor_history_enabled: boolean };
type Friend = { telegram_id: string; name: string; avatar_url: string | null; farm_public: boolean };
type FriendFarm = { owner: string; farm: { level: number; inventory: { wheat: number }; plot: { crop: string | null; ready: boolean } } };
type Visitors = { enabled: boolean; visitors: { name: string; avatar_url: string | null; visited_at: string }[] };
type Onboarding = { step: number; completed: boolean; next_action: string };
type Game = 'farm' | 'pets' | 'cards';
type Locale = 'en' | 'zh' | 'ru';
const getTelegram = () => (window as any).Telegram?.WebApp;
const headers = (): Record<string, string> => { const initData = getTelegram()?.initData as string | undefined; return initData ? { 'X-Telegram-Init-Data': initData } : {}; };
const text: Record<Locale, Record<string, string>> = {
  en: { farm: 'Memory Farm', pets: 'Pet Merge', cards: 'Card Arena', farmDesc: 'Plant, harvest and grow your little town.', petsDesc: 'Merge matching pixel pets into new companions.', cardsDesc: 'Craft your deck and advance through story chapters.', checkin: 'DAILY CHECK-IN', claim: 'Claim', claimed: 'Claimed', core: 'CORE GAMEPLAY', hall: 'Your game hall', allOpen: 'All games open', play: 'Play', playing: 'Playing', inventory: 'Farm inventory', wheat: 'Wheat', deliver: 'Deliver wheat', delivered: 'Delivered', petBoard: 'Pet board', forge: 'Crafting forge', leaderboard: 'Farm leaderboard', ranks: 'Leaderboard', friends: 'Friends', me: 'Me', beta: 'Beta is open', navHall: 'Hall', syncCheckin: 'Syncing daily reward...', unlockCheckin: 'Play any game to unlock today\'s reward.', readyCheckin: 'Play recorded. Claim your memory card.', streak: 'streak complete', plant: 'Plant wheat', harvest: 'Harvest', growing: 'Growing...', chapter: 'Play chapter', craft: 'Craft Clockwork Fox (30)', noCards: 'No cards crafted yet.', noRanks: 'No farm rankings yet.', auth: 'Open this Mini App from Telegram to authenticate.' },
  zh: { farm: '记忆农场', pets: '宠物合成', cards: '卡牌竞技场', farmDesc: '种植、收获，建设你的怀旧小镇。', petsDesc: '合成同阶像素宠物，发现新伙伴。', cardsDesc: '制作卡牌并推进主线章节。', checkin: '每日签到', claim: '领取', claimed: '已领取', core: '核心玩法', hall: '游戏大厅', allOpen: '三款游戏已开放', play: '开始', playing: '进行中', inventory: '农场库存', wheat: '小麦', deliver: '交付小麦', delivered: '已交付', petBoard: '宠物棋盘', forge: '卡牌工坊', leaderboard: '农场排行榜', ranks: '排行榜', friends: '好友', me: '我的', beta: '测试版已开放', navHall: '大厅', syncCheckin: '正在同步每日奖励…', unlockCheckin: '完成任意游戏操作后可领取今日奖励。', readyCheckin: '已记录游玩，可领取收藏卡。', streak: '天连续签到完成', plant: '种植小麦', harvest: '收获', growing: '生长中…', chapter: '挑战章节', craft: '制作发条狐狸（30）', noCards: '暂未制作卡牌。', noRanks: '暂时没有农场排名。', auth: '请从 Telegram 内打开此 Mini App 完成认证。' },
  ru: { farm: 'Ферма воспоминаний', pets: 'Слияние питомцев', cards: 'Карточная арена', farmDesc: 'Сажайте, собирайте урожай и развивайте городок.', petsDesc: 'Объединяйте одинаковых пиксельных питомцев.', cardsDesc: 'Создавайте карты и проходите главы.', checkin: 'ЕЖЕДНЕВНЫЙ ВХОД', claim: 'Получить', claimed: 'Получено', core: 'ОСНОВНАЯ ИГРА', hall: 'Игровой зал', allOpen: 'Все игры открыты', play: 'Играть', playing: 'Игра запущена', inventory: 'Склад фермы', wheat: 'Пшеница', deliver: 'Доставить пшеницу', delivered: 'Доставлено', petBoard: 'Поле питомцев', forge: 'Кузница карт', leaderboard: 'Рейтинг фермы', ranks: 'Рейтинг', friends: 'Друзья', me: 'Я', beta: 'Бета открыта', navHall: 'Зал', syncCheckin: 'Загрузка ежедневной награды...', unlockCheckin: 'Сыграйте в любую игру, чтобы получить награду.', readyCheckin: 'Игра учтена. Получите карту воспоминаний.', streak: 'дней подряд', plant: 'Посадить пшеницу', harvest: 'Собрать урожай', growing: 'Растет...', chapter: 'Играть главу', craft: 'Создать Заводную лису (30)', noCards: 'Карты еще не созданы.', noRanks: 'Рейтинга фермы пока нет.', auth: 'Откройте Mini App внутри Telegram для входа.' },
};
const resolveLocale = (): Locale => {
  const saved = window.localStorage.getItem('retrohub.locale');
  if (saved === 'en' || saved === 'zh' || saved === 'ru') return saved;
  const language = getTelegram()?.initDataUnsafe?.user?.language_code || navigator.language;
  return language.startsWith('zh') ? 'zh' : language.startsWith('ru') ? 'ru' : 'en';
};

function App() {
  const [locale, setLocale] = React.useState<Locale>(resolveLocale);
  const t = text[locale];
  const gameMeta: Record<Game, { label: string; title: string; description: string; tone: string }> = {
    farm: { label: 'FARM', title: t.farm, description: t.farmDesc, tone: 'farm' },
    pets: { label: 'PET', title: t.pets, description: t.petsDesc, tone: 'pet' },
    cards: { label: 'CARD', title: t.cards, description: t.cardsDesc, tone: 'card' },
  };
  const [game, setGame] = React.useState<Game>('farm');
  const [farm, setFarm] = React.useState<Farm | null>(null);
  const [farmOrders, setFarmOrders] = React.useState<FarmOrders | null>(null);
  const [pets, setPets] = React.useState<Pets | null>(null);
  const [cards, setCards] = React.useState<Cards | null>(null);
  const [checkin, setCheckin] = React.useState<Checkin | null>(null);
  const [leaderboard, setLeaderboard] = React.useState<Leaderboard | null>(null);
  const [profile, setProfile] = React.useState<Profile | null>(null);
  const [friends, setFriends] = React.useState<Friend[] | null>(null);
  const [inviteUrl, setInviteUrl] = React.useState('');
  const [friendFarm, setFriendFarm] = React.useState<FriendFarm | null>(null);
  const [friendshipEnergy, setFriendshipEnergy] = React.useState<{ current: number; cap: number } | null>(null);
  const [visitors, setVisitors] = React.useState<Visitors | null>(null);
  const [onboarding, setOnboarding] = React.useState<Onboarding | null>(null);
  const [toast, setToast] = React.useState('');
  const [authError, setAuthError] = React.useState(false);
  const changeLocale = (next: Locale) => { window.localStorage.setItem('retrohub.locale', next); setLocale(next); };
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2200); };
  const request = React.useCallback(async (path: string, method = 'GET') => {
    const response = await fetch(path, { method, headers: { ...(method !== 'GET' ? { 'Content-Type': 'application/json' } : {}), ...headers() } });
    if (!response.ok) { const data = await response.json(); throw new Error(data.detail || 'Action unavailable'); }
    return response.json();
  }, []);
  const refresh = React.useCallback(async () => {
    const profileState = await request('/api/profile');
    setProfile(profileState);
    if (!profileState.age_confirmed) return;
    setCheckin(await request('/api/checkin'));
    setOnboarding(await request('/api/onboarding'));
    if (game === 'farm') { setFarm(await request('/api/farm')); setFarmOrders(await request('/api/farm/orders')); }
    if (game === 'pets') setPets(await request('/api/pets'));
    if (game === 'cards') setCards(await request('/api/cards'));
  }, [game, request]);
  React.useEffect(() => {
    let active = true;
    getTelegram()?.ready();
    getTelegram()?.expand();
    const load = async () => { try { await refresh(); if (active) setAuthError(false); } catch { if (active) setAuthError(true); } };
    void load();
    const timer = window.setInterval(() => { void load(); }, 15_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [refresh]);
  React.useEffect(() => {
    const startParam = getTelegram()?.initDataUnsafe?.start_param as string | undefined;
    if (!startParam?.startsWith('friend_')) return;
    void request(`/api/friends/accept/${encodeURIComponent(startParam.slice('friend_'.length))}`, 'POST').catch(() => undefined);
  }, [request]);
  const perform = async (path: string, success: string) => { try { const data = await request(path, 'POST'); if (game === 'farm') { setFarm(data); setFarmOrders(await request('/api/farm/orders')); setOnboarding(await request('/api/onboarding')); } if (game === 'pets') setPets(data); if (game === 'cards') setCards(data); setCheckin(await request('/api/checkin')); notify(success); } catch (error) { notify(error instanceof Error ? error.message : 'Action unavailable'); } };
  const claimCheckin = async () => { try { const data = await request('/api/checkin/claim', 'POST'); setCheckin(data); notify(`Check-in complete. +${data.collection_awarded} memory card${data.collection_awarded > 1 ? 's' : ''}.`); } catch (error) { notify(error instanceof Error ? error.message : 'Check-in unavailable'); } };
  const loadLeaderboard = async (period = 'all_time') => { try { setLeaderboard(await request(`/api/leaderboards/farm?period=${period}`)); } catch (error) { notify(error instanceof Error ? error.message : 'Leaderboard unavailable'); } };
  const loadProfile = async () => { try { const [profileState, visitorState] = await Promise.all([request('/api/profile'), request('/api/profile/visitors')]); setProfile(profileState); setVisitors(visitorState); } catch (error) { notify(error instanceof Error ? error.message : 'Profile unavailable'); } };
  const updatePrivacy = async (farmPublic: boolean, collectionPublic: boolean) => { try { const response = await fetch('/api/profile/privacy', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...headers() }, body: JSON.stringify({ farm_public: farmPublic, collection_public: collectionPublic }) }); if (!response.ok) throw new Error('Privacy update unavailable'); setProfile(await response.json()); } catch (error) { notify(error instanceof Error ? error.message : 'Privacy update unavailable'); } };
  const confirmAge = async () => { try { const response = await fetch('/api/profile/age-consent', { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() } }); if (!response.ok) throw new Error('Age confirmation unavailable'); setProfile(await response.json()); await refresh(); } catch (error) { notify(error instanceof Error ? error.message : 'Age confirmation unavailable'); } };
  const plantCrop = async (crop: string) => { try { const response = await fetch('/api/farm/plant', { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() }, body: JSON.stringify({ crop }) }); if (!response.ok) { const data = await response.json(); throw new Error(data.detail || 'Planting unavailable'); } setFarm(await response.json()); setFarmOrders(await request('/api/farm/orders')); setOnboarding(await request('/api/onboarding')); notify(`${crop} planted.`); } catch (error) { notify(error instanceof Error ? error.message : 'Planting unavailable'); } };
  const updateVisitorHistory = async (enabled: boolean) => { try { const response = await fetch('/api/profile/visitors', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...headers() }, body: JSON.stringify({ enabled }) }); if (!response.ok) throw new Error('Visitor preference unavailable'); const next = await response.json(); setVisitors({ enabled: next.enabled, visitors: next.enabled ? visitors?.visitors || [] : [] }); setProfile(profile ? { ...profile, visitor_history_enabled: next.enabled } : profile); } catch (error) { notify(error instanceof Error ? error.message : 'Visitor preference unavailable'); } };
  const updatePersonalization = async (enabled: boolean) => { try { const response = await fetch('/api/profile/data-preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...headers() }, body: JSON.stringify({ personalized_recommendations: enabled }) }); if (!response.ok) throw new Error('Preference update unavailable'); setProfile(profile ? { ...profile, personalized_recommendations: (await response.json()).personalized_recommendations } : profile); } catch (error) { notify(error instanceof Error ? error.message : 'Preference update unavailable'); } };
  const loadFriends = async () => { try { const [list, invite] = await Promise.all([request('/api/friends'), request('/api/friends/invite')]); setFriends(list.friends); setFriendshipEnergy({ current: list.friendship_energy, cap: list.friendship_energy_cap }); setInviteUrl(invite.url); } catch (error) { notify(error instanceof Error ? error.message : 'Friends unavailable'); } };
  const visitFriend = async (telegramId: string) => { try { setFriendFarm(await request(`/api/friends/${encodeURIComponent(telegramId)}/farm`)); } catch (error) { notify(error instanceof Error ? error.message : 'Farm visit unavailable'); } };
  const waterFriend = async (telegramId: string) => { try { const result = await request(`/api/friends/${encodeURIComponent(telegramId)}/help/water`, 'POST'); setFriendshipEnergy({ current: result.friendship_energy, cap: result.friendship_energy_cap }); notify(`${result.owner}'s farm was watered. ${result.seconds_saved}s saved.`); } catch (error) { notify(error instanceof Error ? error.message : 'Farm help unavailable'); } };
  const shareInvite = () => { if (!inviteUrl) return; const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(inviteUrl)}&text=${encodeURIComponent('Join me in RetroHub')}`; const telegram = getTelegram(); if (telegram?.openTelegramLink) telegram.openTelegramLink(shareUrl); else notify(inviteUrl); };
  const farmReady = farm?.plot.crop && farm.plot.ready;
  const petTier = pets?.pets.find((pet) => pet.amount >= 2)?.tier;
  const select = (next: Game) => { setGame(next); setToast('Loading ' + gameMeta[next].title + '...'); };
  const action = game === 'farm'
    ? { text: farm?.plot.crop ? (farmReady ? t.harvest : t.growing) : t.plant, run: () => farm?.plot.crop && !farmReady ? notify(t.growing) : void perform(farm?.plot.crop ? '/api/farm/harvest' : '/api/farm/plant', farm?.plot.crop ? 'Harvest complete. Sell wheat or deliver an order.' : 'Wheat planted. Return in 20 seconds.') }
    : game === 'pets'
      ? { text: petTier ? `Merge tier ${petTier}` : 'Need two pets', run: () => petTier ? void perform(`/api/pets/merge/${petTier}`, `Tier ${petTier + 1} pet discovered!`) : notify('Earn or merge more pets first') }
      : { text: t.chapter, run: () => void perform('/api/cards/battle', 'Victory! +15 crafting materials.') };
  const status = authError ? t.auth : game === 'farm' ? (farm ? `${farm.coins} coins · ${farm.diamonds} diamonds · ${farm.xp} XP` : 'Syncing farm...')
    : game === 'pets' ? (pets ? `${pets.pets.reduce((total, pet) => total + pet.amount, 0)} pets in your collection` : 'Syncing collection...')
      : (cards ? `Chapter ${cards.chapter} · ${cards.materials} materials` : 'Syncing card collection...');
  const checkinMessage = !checkin ? t.syncCheckin : checkin.claimed_today ? `${checkin.streak} ${t.streak}` : checkin.played_today ? t.readyCheckin : t.unlockCheckin;
  if (profile && !profile.age_confirmed) return <main className="app-shell"><header><div><p className="eyebrow">RETROHUB TEST</p><h1>Age confirmation</h1></div></header><section className="detail-panel"><b>18+ required</b><p>Confirm that you are 18 years of age or older to enter RetroHub and start playing.</p><button onClick={() => void confirmAge()}>I am 18 or older</button></section>{toast && <div role="status" className="toast">{toast}</div>}</main>;
  return <main className="app-shell"><header><div><p className="eyebrow">RETROHUB TEST</p><h1>{gameMeta[game].title}</h1></div><button className="avatar" aria-label="Telegram profile" onClick={() => changeLocale(locale === 'en' ? 'zh' : locale === 'zh' ? 'ru' : 'en')}>{locale.toUpperCase()}</button></header>
    <section className="daily"><div><span>{t.checkin}</span><strong>{checkinMessage}</strong></div><button disabled={!checkin?.can_claim} onClick={() => void claimCheckin()}>{checkin?.claimed_today ? t.claimed : t.claim}</button></section>
    {onboarding && !onboarding.completed && <section className="detail-panel"><b>First farm guide</b><p>Step {onboarding.step + 1}/3: {onboarding.next_action}</p></section>}
    <section className="game-status"><span>{t.core}</span><strong>{status}</strong><button onClick={action.run}>{action.text}</button></section>
    <section className="section-title"><h2>{t.hall}</h2><span>{t.allOpen}</span></section>
    <section className="cards">{(Object.keys(gameMeta) as Game[]).map((id) => <article className={`game-card ${gameMeta[id].tone} ${game === id ? 'selected' : ''}`} key={id}><div className="icon">{gameMeta[id].label}</div><div className="copy"><h3>{gameMeta[id].title}</h3><p>{gameMeta[id].description}</p></div><button className={game === id ? 'ghost' : ''} onClick={() => select(id)}>{game === id ? t.playing : t.play}</button></article>)}</section>
    {game === 'farm' && farm && farmOrders && <section className="detail-panel"><b>{t.inventory}</b><p>{t.wheat}: {farm.inventory.wheat}. Sell one wheat for 45 coins, or {farmOrders.orders[0].title}: {farmOrders.orders[0].required.wheat} {t.wheat} / {farmOrders.orders[0].reward.coins} coins.</p><button disabled={farm.inventory.wheat < 1} onClick={() => void perform('/api/farm/sell/wheat', 'Wheat sold. +45 coins.')}>Sell wheat</button><button disabled={farmOrders.orders[0].claimed || farmOrders.orders[0].available.wheat < farmOrders.orders[0].required.wheat} onClick={() => void perform('/api/farm/orders/wheat_delivery/claim', 'Bakery delivery complete!')}>{farmOrders.orders[0].claimed ? t.delivered : t.deliver}</button>{farm.ledger.length > 0 && <p>Latest: {farm.ledger[0].type.split('_').join(' ')} ({farm.ledger[0].coins_delta >= 0 ? '+' : ''}{farm.ledger[0].coins_delta} coins)</p>}</section>}
    {game === 'farm' && farm && <section className="detail-panel"><b>Farm companion</b><p>{farm.companion ? `${farm.companion.name}: ${farm.companion.effect}` : 'Choose one free companion for a light farming bonus.'}</p>{!farm.companion && farm.companions.map((companion) => <button key={companion.key} onClick={() => void perform(`/api/farm/companions/${companion.key}/adopt`, `${companion.name} joined your farm!`)}>Adopt {companion.name}</button>)}</section>}
    {game === 'farm' && farm && !farm.plot.crop && <section className="detail-panel"><b>Seed shelf</b><p>Choose an unlocked crop. Higher-level crops grow longer and sell for more.</p>{farm.crops.map((crop) => <button key={crop.key} disabled={!crop.unlocked || farm.coins < crop.seed_cost} onClick={() => void plantCrop(crop.key)}>{crop.unlocked ? `Plant ${crop.key} (${crop.seed_cost})` : `Unlock ${crop.key} at Lv.${crop.unlock_level}`}</button>)}</section>}
    {game === 'farm' && farm && <section className="detail-panel"><b>Crop inventory</b><p>{Object.entries(farm.inventory).map(([key, amount]) => `${key}: ${amount}`).join(' · ')}</p>{Object.entries(farm.inventory).filter(([, amount]) => amount > 0).map(([key]) => <button key={key} onClick={() => void perform(`/api/farm/sell/${key}`, `${key} sold.`)}>Sell {key}</button>)}</section>}
    {game === 'farm' && farmOrders?.orders[1] && <section className="detail-panel"><b>Daily market delivery</b><p>Deliver {farmOrders.orders[1].required.wheat} wheat for {farmOrders.orders[1].reward.coins} coins and weekly/monthly order points.</p><button disabled={farmOrders.orders[1].claimed || farmOrders.orders[1].available.wheat < farmOrders.orders[1].required.wheat} onClick={() => void perform('/api/farm/orders/daily_wheat_delivery/claim', 'Daily delivery complete!')}>{farmOrders.orders[1].claimed ? 'Completed today' : 'Deliver daily order'}</button></section>}
    {game === 'pets' && pets && <section className="detail-panel"><b>{t.petBoard}</b><p>{pets.pets.map((pet) => `Tier ${pet.tier}: ${pet.amount}`).join(' · ')} · {pets.coins} pet coins · {pets.production_per_minute}/min</p><button onClick={() => void perform('/api/pets/idle/claim', `Idle income collected: ${pets.idle_coins_claimable} coins.`)}>Collect idle ({pets.idle_coins_claimable})</button><button disabled={pets.coins < pets.egg_cost} onClick={() => void perform('/api/pets/eggs/basic', 'Basic pet egg hatched!')}>Buy basic egg ({pets.egg_cost})</button></section>}
    {game === 'cards' && cards && <section className="detail-panel"><b>{t.forge}</b><p>{cards.cards.length ? cards.cards.map((card) => `${card.key.replace('_', ' ')} Lv.${card.level}`).join(' · ') : t.noCards}</p><button onClick={() => void perform('/api/cards/craft/clockwork_fox', 'Clockwork Fox forged!')}>{t.craft}</button>{cards.tower && <p>Weekly tower: floor {cards.tower.floor}/{cards.tower.max_floor} · {cards.tower.points} points · strength {cards.tower.strength}{cards.tower.is_elite_floor ? ' · Elite floor' : ''}</p>}<button disabled={cards.tower?.ended} onClick={() => void perform('/api/cards/tower/challenge', 'Tower challenge resolved.')}>{cards.tower?.ended ? 'Tower run ended' : 'Challenge tower'}</button></section>}
    {leaderboard && <section className="detail-panel"><b>{t.leaderboard} · {leaderboard.period.replace('_', ' ')}</b><p>{leaderboard.entries.length ? leaderboard.entries.slice(0, 5).map((entry) => `#${entry.rank} ${entry.name} ${entry.points === undefined ? `Lv.${entry.level}` : `${entry.points} pts`}${entry.is_me ? ' (You)' : ''}`).join(' · ') : t.noRanks}</p><button onClick={() => void loadLeaderboard('all_time')}>All time</button><button onClick={() => void loadLeaderboard('week')}>Weekly orders</button><button onClick={() => void loadLeaderboard('month')}>Monthly orders</button></section>}
    {profile && <section className="detail-panel"><b>{profile.name}'s profile</b><p>Farm Lv.{profile.honors.farm_level} · Pet tier {profile.honors.highest_pet_tier || '-'} · {profile.honors.crafted_cards} crafted cards</p><button onClick={() => void updatePrivacy(!profile.privacy.farm_public, profile.privacy.collection_public)}>Farm: {profile.privacy.farm_public ? 'Public' : 'Private'}</button><button onClick={() => void updatePrivacy(profile.privacy.farm_public, !profile.privacy.collection_public)}>Collection: {profile.privacy.collection_public ? 'Public' : 'Private'}</button></section>}
    {profile && <section className="detail-panel"><b>Data preferences</b><p>Personalized recommendations can be turned off. Necessary attribution and security records remain active.</p><button onClick={() => void updatePersonalization(!profile.personalized_recommendations)}>{profile.personalized_recommendations ? 'Turn off personalized recommendations' : 'Turn on personalized recommendations'}</button></section>}
    {visitors && <section className="detail-panel"><b>Visitor history</b><p>{visitors.enabled ? (visitors.visitors.length ? visitors.visitors.slice(0, 5).map((visitor) => visitor.name).join(' · ') : 'No farm visits yet.') : 'Visitor history is hidden. Existing records are retained.'}</p><button onClick={() => void updateVisitorHistory(!visitors.enabled)}>{visitors.enabled ? 'Hide visitor history' : 'Show visitor history'}</button></section>}
    {friends && <section className="detail-panel"><b>Friends</b><p>{friendshipEnergy ? `Friendship energy: ${friendshipEnergy.current}/${friendshipEnergy.cap}. ` : ''}{friends.length ? `${friends.length} friend${friends.length === 1 ? '' : 's'} connected through Telegram.` : 'Invite a Telegram friend to visit their farm.'}</p><button onClick={shareInvite}>Invite friend</button>{friends.map((friend) => <p key={friend.telegram_id}>{friend.name} · Farm {friend.farm_public ? 'Public' : 'Private'} <button onClick={() => void visitFriend(friend.telegram_id)}>Visit</button>{friend.farm_public && <button disabled={friendshipEnergy?.current === 0} onClick={() => void waterFriend(friend.telegram_id)}>Water</button>}</p>)}{friendFarm && <p>Visiting {friendFarm.owner}: Lv.{friendFarm.farm.level} · {friendFarm.farm.inventory.wheat} wheat · {friendFarm.farm.plot.crop ? (friendFarm.farm.plot.ready ? 'Harvest ready' : 'Crop growing') : 'Empty plot'}</p>}</section>}
    <section className="status"><div><span className="pulse" /> {t.beta}</div><button onClick={() => void loadLeaderboard()}>{t.ranks}</button></section>
    <nav><button className="active">{t.navHall}</button><button onClick={() => void loadFriends()}>{t.friends}</button><button onClick={() => void loadLeaderboard()}>{t.ranks}</button><button onClick={() => void loadProfile()}>{t.me}</button></nav>{toast && <div role="status" className="toast">{toast}</div>}</main>;
}
createRoot(document.getElementById('root')!).render(<App />);
