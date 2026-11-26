# Map Creator v3 — Harnais Rust, App Server JSON & Dashboard Svelte

> **Un agent décide quoi faire, un script sait comment le faire, du code vérifie le résultat, et l'humain tranche.**

Ce dossier autonome implémente le système complet décrit dans la spécification **Map Creator, système et pipeline (v3)** avec une architecture légère inspirée de l'application de bureau **Codex** :

1. **Cœur Rust (`core/`)** : boucle d'agent multi-provider (OpenAI-compatible / OpenRouter / Anthropic / `builtin_local`), outils cœur (fichiers, shell, état, plan, outbox, bibliothèque, validateurs, MCP) et **moteur de permissions strict** (`allow` / `ask` / `deny` + chemins protégés durs).
2. **Protocole App Server JSON-RPC 2.0 + WebSocket (`protocol/`)** : découple totalement le cœur Rust de ses clients (Dashboard Svelte, CLI, ou **IslandForge** plus tard).
3. **Interface Svelte 5 + Vite (`ui/`)** : ultra-légère (~46 Ko gzip), personnalisable à chaud par **variables CSS** et **`config/app.toml`** (thèmes, raccourcis clavier, modèles & prompts système par rôle, outils activés). Une fois compilée, elle est servie directement par le binaire Rust (zéro processus Node nécessaire à côté d'UEFN).
4. **Extensions MCP (`config/mcp_servers.toml`)** : branchez UEFN MCP, générateur d'images, générateur 3D (Meshy/Tripo) ou tout serveur MCP externe sans toucher au cœur Rust.

---

## Arborescence

```text
map-creator/
├── config/
│   ├── app.toml                  # Thème CSS, raccourcis, rôles/modèles/prompts, grille (512/384 uu)
│   ├── permissions.toml          # Politique allow/ask/deny, chemins protégés, garde-fous shell
│   ├── mcp_servers.toml          # Extensions MCP pluggables (UEFN, Images, 3D, custom)
│   └── circuit_breakers.json     # Coupe-circuit MCP relu à chaque appel
├── core/                         # Cœur Rust (`map-creator-core`) : App Server + CLI + Tests
├── ui/                           # Dashboard Svelte 5 + Vite (compilé dans ui/dist)
├── protocol/
│   ├── protocol.md               # Spécification complète JSON-RPC 2.0 + flux d'événements WS
│   └── schemas/                  # Schémas JSON des phases 0→9, outbox, bibliothèque, validation
├── validators/
│   ├── rules.json                # Seuils et règles protégés
│   └── MANIFEST.json             # Empreintes SHA-256 (verrouillage humain uniquement)
├── compat/                       # Pont « Agent PC (UEFN) ↔ Agent Git (Harnais) »
│   ├── README_AGENT_PC.md        # Checklist terrain pour l'Agent PC connecté à UEFN
│   ├── COMPAT_STATUS.md          # Matrice de compatibilité MCP en direct
│   └── fixtures/                 # Réponses JSON brutes capturées sur UEFN
└── workspace/
    ├── lessons.json              # Mémoire niveau 2 : leçons apprises (règle + incident)
    ├── library/index.json        # Mémoire niveau 3 : bibliothèque réutilisable (0 token)
    └── projects/neo-kyoto-slice/ # Projet vertical-slice complet pré-chargé
```

---

## Démarrage rapide

### 1. Compiler le Dashboard Svelte (1 seule fois, ou après modification UI)
```bash
cd map-creator/ui
npm install
npm run build
```

### 2. Verrouiller les validateurs (action humaine) et lancer les tests Rust
```bash
cd map-creator/core
cargo run -- lock-validators --by human
cargo test
```

### 3. Lancer le Cœur Rust + Dashboard Web (un seul binaire léger)
```bash
cd map-creator/core
cargo run -- serve
```
Le serveur démarre sur **`http://127.0.0.1:4310`** :
- Dashboard Svelte : `http://127.0.0.1:4310/`
- App Server JSON-RPC 2.0 : `POST http://127.0.0.1:4310/rpc`
- Flux temps réel WebSocket : `ws://127.0.0.1:4310/ws`
- Santé : `GET http://127.0.0.1:4310/api/health`

### Commandes CLI utiles (sans interface web)
```bash
cargo run -- validate --project neo-kyoto-slice     # MANIFEST SHA-256 -> 20 cas Golden -> Règles réelles
cargo run -- validate --golden-only                 # Auto-test anti-affaiblissement (20 cas)
cargo run -- plan-check --district district_plaza   # Contrôle plan 4 couches (collisions/flottants/raisons)
cargo run -- library-search verse                   # Recherche 0 token avant de produire
cargo run -- compat-status                          # État de compatibilité UEFN (Agent PC)
```

---

## Synchronisation « Agent PC ↔ Agent Git »

1. Sur votre PC Windows (avec UEFN ouvert), l'Agent PC suit `compat/README_AGENT_PC.md`.
2. Il capture les réponses JSON brutes dans `compat/fixtures/` et met à jour `compat/COMPAT_STATUS.md` — ou vous les collez directement dans l'onglet **Preuves & Compat PC** (`+ Ingérer fixture Agent PC`).
3. Pour basculer du **Mode Simulateur** au **Mode UEFN Live**, passez `mode = "live"` dans l'onglet **Config TOML & MCP** (ou dans `config/mcp_servers.toml`) et sélectionnez **Mode UEFN MCP Live** dans l'Outbox.
