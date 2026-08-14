import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Farm = { level: number; xp: number; coins: number; diamonds: number; plot: { crop: string | null; ready: boolean } };
type Pets = { pets: { tier: number; amount: number }[] };
type Cards = { materials: number; chapter: number; cards: { key: string; level: number }[] };
type Game = 'farm' | 'pets' | 'cards';
const telegram = (window as any).Telegram?.WebApp;
const headers = (): Record<string, string> => { const initData = telegram?.initData as string | undefined; return initData ? { 'X-Telegram-Init-Data': initData } : {}; };
const gameMeta: Record<Game, { label: string; title: string; description: string; tone: string }> = {
  farm: { label: 'FARM', title: 'Memory Farm', description: 'Plant, harvest and grow your little town.', tone: 'farm' },
  pets: { label: 'PET', title: 'Pet Merge', description: 'Merge matching pixel pets into new companions.', tone: 'pet' },
  cards: { label: 'CARD', title: 'Card Arena', description: 'Craft your deck and advance through story chapters.', tone: 'card' },
};

function App() {
  const [game, setGame] = React.useState<Game>('farm');
  const [farm, setFarm] = React.useState<Farm | null>(null);
  const [pets, setPets] = React.useState<Pets | null>(null);
  const [cards, setCards] = React.useState<Cards | null>(null);
  const [toast, setToast] = React.useState('Loading...');
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2200); };
  const request = React.useCallback(async (path: string, method = 'GET') => {
    const response = await fetch(path, { method, headers: { ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}), ...headers() } });
    if (!response.ok) { const data = await response.json(); throw new Error(data.detail || 'Action unavailable'); }
    return response.json();
  }, []);
  const refresh = React.useCallback(async () => {
    try {
      if (game === 'farm') setFarm(await request('/api/farm'));
      if (game === 'pets') setPets(await request('/api/pets'));
      if (game === 'cards') setCards(await request('/api/cards'));
      setToast('');
    } catch { notify('Open from Telegram to start playing'); }
  }, [game, request]);
  React.useEffect(() => { telegram?.ready(); void refresh(); }, [refresh]);
  React.useEffect(() => { const timer = window.setInterval(() => void refresh(), 1000); return () => window.clearInterval(timer); }, [refresh]);
  const perform = async (path: string, success: string) => { try { const data = await request(path, 'POST'); if (game === 'farm') setFarm(data); if (game === 'pets') setPets(data); if (game === 'cards') setCards(data); notify(success); } catch (error) { notify(error instanceof Error ? error.message : 'Action unavailable'); } };
  const farmReady = farm?.plot.crop && farm.plot.ready;
  const petTier = pets?.pets.find((pet) => pet.amount >= 2)?.tier;
  const select = (next: Game) => { setGame(next); setToast('Loading ' + gameMeta[next].title + '...'); };
  const action = game === 'farm'
    ? { text: farm?.plot.crop ? (farmReady ? 'Harvest' : 'Growing...') : 'Plant wheat', run: () => farm?.plot.crop && !farmReady ? notify('Your wheat is still growing') : void perform(farm?.plot.crop ? '/api/farm/harvest' : '/api/farm/plant', farm?.plot.crop ? 'Harvest complete. +45 coins, +10 XP.' : 'Wheat planted. Return in 20 seconds.') }
    : game === 'pets'
      ? { text: petTier ? `Merge tier ${petTier}` : 'Need two pets', run: () => petTier ? void perform(`/api/pets/merge/${petTier}`, `Tier ${petTier + 1} pet discovered!`) : notify('Earn or merge more pets first') }
      : { text: 'Play chapter', run: () => void perform('/api/cards/battle', 'Victory! +15 crafting materials.') };
  const status = game === 'farm' ? (farm ? `${farm.coins} coins · ${farm.diamonds} diamonds · ${farm.xp} XP` : 'Syncing farm...')
    : game === 'pets' ? (pets ? `${pets.pets.reduce((total, pet) => total + pet.amount, 0)} pets in your collection` : 'Syncing collection...')
      : (cards ? `Chapter ${cards.chapter} · ${cards.materials} materials` : 'Syncing card collection...');
  return <main className="app-shell"><header><div><p className="eyebrow">RETROHUB TEST</p><h1>{gameMeta[game].title}</h1></div><button className="avatar" aria-label="Telegram profile">@</button></header>
    <section className="daily"><div><span>CORE GAMEPLAY</span><strong>{status}</strong></div><button onClick={action.run}>{action.text}</button></section>
    <section className="section-title"><h2>Your game hall</h2><span>All games open</span></section>
    <section className="cards">{(Object.keys(gameMeta) as Game[]).map((id) => <article className={`game-card ${gameMeta[id].tone} ${game === id ? 'selected' : ''}`} key={id}><div className="icon">{gameMeta[id].label}</div><div className="copy"><h3>{gameMeta[id].title}</h3><p>{gameMeta[id].description}</p></div><button className={game === id ? 'ghost' : ''} onClick={() => select(id)}>{game === id ? 'Playing' : 'Play'}</button></article>)}</section>
    {game === 'pets' && pets && <section className="detail-panel"><b>Pet board</b><p>{pets.pets.map((pet) => `Tier ${pet.tier}: ${pet.amount}`).join(' · ')}</p></section>}
    {game === 'cards' && cards && <section className="detail-panel"><b>Crafting forge</b><p>{cards.cards.length ? cards.cards.map((card) => `${card.key.replace('_', ' ')} Lv.${card.level}`).join(' · ') : 'No cards crafted yet.'}</p><button onClick={() => void perform('/api/cards/craft/clockwork_fox', 'Clockwork Fox forged!')}>Craft Clockwork Fox (30)</button></section>}
    <section className="status"><div><span className="pulse" /> Beta is open</div><button onClick={() => notify('Rankings launch with Season 1')}>Leaderboard</button></section>
    <nav><button className="active">Hall</button><button>Friends</button><button>Ranks</button><button>Me</button></nav>{toast && <div role="status" className="toast">{toast}</div>}</main>;
}
createRoot(document.getElementById('root')!).render(<App />);
