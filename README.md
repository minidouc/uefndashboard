# uefndashboard

# 🏝️ IslandForge — Harnais d'automatisation & Gestion de projet UEFN

> ⚠️ **Projet en développement actif.** Rien n'est figé : je construis, je casse,
> je mesure, je corrige — et j'enrichis ce dépôt au fil des découvertes.

---

## 📖 L'histoire & Le pivot

À l'origine, IslandForge devait simplement être une **interface web / dashboard pour organiser et gérer ses projets UEFN**. 

Mais en avançant, le projet a pris un virage à 180° : avoir une vue de gestion sans pouvoir agir directement et massivement dans le moteur limitait son impact. J'ai donc voulu concevoir un véritable harnais d'automatisation capable de manipuler l'éditeur.

Le déclic technique est venu de la découverte d'un benchmark public : **« MCP vs Python Bridge » (août 2026)** https://claude.ai/code/artifact/cf462219-b7d2-4d9c-baa8-c856734d81dd . Les chiffres y prouvent qu'un script Python complet injecté dans l'éditeur est **53× plus rapide** et consomme **35× moins de tokens** qu'un enchaînement d'appels d'outils un par un (671 requêtes MCP). 

IslandForge a donc fusionné ces deux visions :
1. **Un moteur d'exécution (Script Bridge)** pour piloter UEFN en direct via du code Python embarqué.
2. **Un dashboard de gestion de projet** pour superviser, organiser les specs et piloter les assets.

**Ordre de marche choisi :** construire et fiabiliser d'abord le **Script Bridge** (le moteur sous le capot), pour ensuite développer l'**interface web / dashboard** qui viendra se brancher dessus.

---

## ⚙️ Comment ça marche

- **Bridge Python in-editor** : serveur HTTP local (`127.0.0.1:8790`) tournant dans le Python embarqué d'UEFN, exécuté de façon sécurisée sur le thread principal de l'éditeur.
- **Règle de routage** : ≤ ~30 opérations éditeur → appels directs légers ; au-delà (boucles, bulk spawn, câblage complexe) → **un seul script batché** envoyé au bridge.
- **Catalogue d'assets local** : les **201 843 assets** de l'éditeur indexés dans une base SQLite, interrogeables en quelques millisecondes sans saturer la mémoire de l'agent.
- **Contrat de positionnement** : calcul précis des boîtes englobantes (*bounds*), alignement sur grille de hauteurs et audit anti-flottement (*anti-floaters*).
- **Audit Valkyrie** : vérification en amont de la conformité des assets pour éviter les rejets lors de la validation finale de l'île.

---

## 🚧 Feuille de route (Roadmap)

Mon avencement :

- [x] Serveur HTTP local fonctionnel dans UEFN (~1 500 ops/s mesurées).
- [x] Indexation SQLite des 201 843 assets du catalogue UEFN.

Prevu/en cour :
- Interface web locale de gestion et de monitoring.
- Templates prêts à l'emploi.
- Skill / pipeline d'architecture spatiale (Spécification → Script → Injection).
- 
- 
---

## 🙏 Crédits & inspirations

- **L'auteur du benchmark « MCP vs Python Bridge » (août 2026)** : dont les données et la démonstration technique ont fixé l'architecture de ce projet. *https://x.com/GhostUEP*
- **Antigravity (Google)** : pour l'assistance dans les sessions d'exécution et d'exploration de l'API.
- **Epic Games / UEFN** : pour l'environnement de création.

---

*Ce README évoluera avec le projet. Si tu lis ceci plus tard, sache qu'ici, chaque ligne a été apprise en faisant — souvent en cassant d'abord.*