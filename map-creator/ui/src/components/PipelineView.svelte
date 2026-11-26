<script>
  import { rpc } from '../lib/rpc.js';

  let { pipelineData, onRefresh, notify } = $props();

  let gateName = $state('gameplay');
  let gateCitation = $state('');
  let gateScope = $state('');
  let busy = $state(false);

  let newProjSlug = $state('');
  let newProjTitle = $state('');
  let newProjMode = $state('production');
  let showCreate = $state(false);

  let crTarget = $state('deliverables/brief.json');
  let crReason = $state('');
  let crCitation = $state('');

  const GATES_INFO = [
    { id: 'brief', label: 'Verrou Brief (Phase 1)' },
    { id: 'salle_grise', label: 'Test Salle grise 10 min (Phase 2A)' },
    { id: 'texte', label: 'Verrou Texte & Plans (Phase 2A)' },
    { id: 'conception', label: 'Verrou Conception Images (Phase 2B)' },
    { id: 'ecriture_uefn', label: 'Autorisation Écriture UEFN (Phase 3)' },
    { id: 'gameplay', label: 'Verrou Gameplay Playtest (Phase 4)' },
    { id: 'planches', label: 'Validation Planches 2B+ (Phase 2B+)' },
    { id: 'verification', label: 'Validation 16 critères (Phase 6)' },
    { id: 'publication', label: 'Feu vert Publication (Phase 9)' }
  ];

  const STAGES = [
    { id: 'sur_papier', title: 'Sur papier', desc: 'Rien posé en éditeur (sauf courte salle grise 2A)' },
    { id: 'en_gris', title: 'En gris (3 ⇄ 4)', desc: 'Boucle graybox & playtest jusqu\'au verrou gameplay' },
    { id: 'en_vrai', title: 'En vrai', desc: 'Planches 2B+, vrais objets, finitions, optimisation, publication' }
  ];

  let state = $derived(pipelineData?.state);
  let phases = $derived(pipelineData?.phases || []);

  async function advanceTo(phaseId) {
    busy = true;
    try {
      await rpc('pipeline.advance', { target_phase: phaseId });
      notify(`Phase basculée vers ${phaseId}`);
      await onRefresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }

  async function submitGate(e) {
    e.preventDefault();
    if (gateCitation.trim().length < 3) {
      notify('La citation exacte de l\'auteur est obligatoire.', true);
      return;
    }
    busy = true;
    try {
      await rpc('pipeline.approve_gate', {
        gate: gateName,
        citation: gateCitation.trim(),
        scope: gateScope.trim() || null
      });
      gateCitation = '';
      gateScope = '';
      notify(`Porte '${gateName}' validée et journalisée (provenance: human).`);
      await onRefresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }

  async function toggleMode(mode) {
    busy = true;
    try {
      await rpc('pipeline.set_mode', { mode });
      notify(`Mode basculé sur ${mode} (validateurs & preuves inchangés).`);
      await onRefresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }

  async function createProject(e) {
    e.preventDefault();
    busy = true;
    try {
      await rpc('project.create', {
        slug: newProjSlug.trim().toLowerCase(),
        title: newProjTitle.trim() || newProjSlug.trim(),
        mode: newProjMode
      });
      showCreate = false;
      newProjSlug = '';
      newProjTitle = '';
      notify('Nouveau projet créé et sélectionné.');
      await onRefresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }

  async function submitChangeRequest(e) {
    e.preventDefault();
    busy = true;
    try {
      await rpc('pipeline.change_request', {
        target: crTarget,
        reason: crReason.trim(),
        citation: crCitation.trim() || null
      });
      crReason = '';
      crCitation = '';
      notify('Demande de changement enregistrée.');
      await onRefresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }
</script>

{#if state}
  <div class="panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">{state.title}</h2>
        <p class="panel-subtitle">
          Phase active : <strong class="mono">{state.phase}</strong> · Prochaine action : {state.next_action || '—'}
        </p>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <div class="mode-switch">
          <button
            id="btn-mode-production"
            class="btn btn-sm {state.mode === 'production' ? 'btn-primary' : ''}"
            onclick={() => toggleMode('production')}
            disabled={busy}
          >Mode Production</button>
          <button
            id="btn-mode-prototype"
            class="btn btn-sm {state.mode === 'prototype' ? 'btn-primary' : ''}"
            onclick={() => toggleMode('prototype')}
            disabled={busy}
          >Mode Prototype / Jam</button>
        </div>
        <button id="btn-new-project" class="btn btn-sm" onclick={() => (showCreate = !showCreate)}>
          {showCreate ? 'Fermer' : '+ Nouveau projet'}
        </button>
      </div>
    </div>

    {#if showCreate}
      <form class="create-box" onsubmit={createProject}>
        <div class="grid-3">
          <div class="field">
            <label for="new-slug">Slug (minuscules + tirets)</label>
            <input id="new-slug" class="input mono" bind:value={newProjSlug} placeholder="ex: cyber-market" required />
          </div>
          <div class="field">
            <label for="new-title">Titre du projet</label>
            <input id="new-title" class="input" bind:value={newProjTitle} placeholder="Cyber Market — Map UEFN" required />
          </div>
          <div class="field">
            <label for="new-mode">Mode initial</label>
            <select id="new-mode" class="select" bind:value={newProjMode}>
              <option value="production">Production (Phases 0 → 9 complètes)</option>
              <option value="prototype">Prototype / Jam (portes 2B/2B+ groupées)</option>
            </select>
          </div>
        </div>
        <button id="btn-create-project-submit" type="submit" class="btn btn-primary btn-sm" disabled={busy}>
          Initialiser en Phase 0
        </button>
      </form>
    {/if}

    <div class="stages-grid">
      {#each STAGES as stage}
        <div class="stage-col">
          <div class="stage-head">
            <strong>{stage.title}</strong>
            <span>{stage.desc}</span>
          </div>
          <div class="phase-list">
            {#each phases.filter((p) => p.stage === stage.id) as ph}
              {@const isCurrent = state.phase === ph.id}
              {@const curIdx = phases.findIndex((x) => x.id === state.phase)}
              {@const phIdx = phases.findIndex((x) => x.id === ph.id)}
              {@const isDone = phIdx < curIdx}
              <div class="phase-card" class:current={isCurrent} class:done={isDone}>
                <div class="phase-top">
                  <span class="phase-code mono">{ph.code}</span>
                  <span class="phase-name">{ph.label}</span>
                  {#if isCurrent}
                    <span class="badge accent">EN COURS</span>
                  {:else if isDone}
                    <span class="badge pass">PASSÉ</span>
                  {/if}
                </div>
                {#if ph.required_gates.length > 0}
                  <div class="phase-gates">
                    {#each ph.required_gates as g}
                      <span class="badge {state.gates[g] ? 'pass' : 'warn'}">
                        {state.gates[g] ? '✓' : '○'} {g}
                      </span>
                    {/each}
                  </div>
                {/if}
                {#if !isCurrent}
                  <div style="margin-top:8px;">
                    <button
                      id="btn-phase-{ph.id}"
                      class="btn btn-sm"
                      onclick={() => advanceTo(ph.id)}
                      disabled={busy}
                    >
                      {phIdx < curIdx ? 'Revenir à cette phase' : 'Passer à cette phase →'}
                    </button>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>

  <div class="grid-2" style="margin-top:16px;">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h3 class="panel-title">Validation des portes humaines</h3>
          <p class="panel-subtitle">Toute porte exige votre citation exacte (journalisée en provenance <code class="mono">human</code>).</p>
        </div>
      </div>

      <form onsubmit={submitGate}>
        <div class="field">
          <label for="gate-select">Porte à valider</label>
          <select id="gate-select" class="select" bind:value={gateName}>
            {#each GATES_INFO as g}
              <option value={g.id}>{g.label} {state.gates[g.id] ? '✓' : ''}</option>
            {/each}
          </select>
        </div>
        <div class="field">
          <label for="gate-citation">Citation exacte de décision</label>
          <input
            id="gate-citation"
            class="input"
            bind:value={gateCitation}
            placeholder="Ex: Playtest OK, le saut et la balise fonctionnent, on verrouille le gameplay."
            required
          />
        </div>
        <div class="field">
          <label for="gate-scope">Périmètre (optionnel)</label>
          <input id="gate-scope" class="input" bind:value={gateScope} placeholder="Ex: Quartier Esplanade" />
        </div>
        <button id="btn-approve-gate" type="submit" class="btn btn-primary" disabled={busy}>
          Signer et valider la porte
        </button>
      </form>

      <div style="margin-top:16px;">
        <div class="panel-subtitle" style="margin-bottom:8px; font-weight:600;">Portes déjà signées ({Object.keys(state.gates).length})</div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Porte</th><th>Citation humaine</th><th>Date</th></tr>
            </thead>
            <tbody>
              {#each Object.entries(state.gates) as [k, rec]}
                <tr>
                  <td><span class="badge pass">{k}</span></td>
                  <td>« {rec.citation} »</td>
                  <td class="mono" style="font-size:11px; white-space:nowrap;">{rec.ts_utc.slice(0, 16).replace('T', ' ')}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <h3 class="panel-title">Livrables verrouillés &amp; Demandes de changement</h3>
          <p class="panel-subtitle">Un livrable verrouillé ne change plus sans demande acceptée par l'auteur.</p>
        </div>
      </div>

      <div class="table-wrap" style="margin-bottom:16px;">
        <table class="data-table">
          <thead>
            <tr><th>Fichier verrouillé</th><th>Empreinte</th><th>Citation</th></tr>
          </thead>
          <tbody>
            {#each Object.entries(state.locks || {}) as [path, lk]}
              <tr>
                <td class="mono" style="font-size:12px;">{path}</td>
                <td class="mono" style="font-size:11px;">{lk.sha256.slice(0, 12)}</td>
                <td>{lk.human_citation}</td>
              </tr>
            {:else}
              <tr><td colspan="3" style="color:var(--text-secondary);">Aucun livrable verrouillé pour le moment.</td></tr>
            {/each}
          </tbody>
        </table>
      </div>

      <form onsubmit={submitChangeRequest}>
        <div class="field">
          <label for="cr-target">Livrable ciblé</label>
          <input id="cr-target" class="input mono" bind:value={crTarget} required />
        </div>
        <div class="field">
          <label for="cr-reason">Raison de la demande de changement</label>
          <input id="cr-reason" class="input" bind:value={crReason} placeholder="Ex: Ajuster la largeur de la rampe nord après playtest" required />
        </div>
        <div class="field">
          <label for="cr-citation">Citation d'approbation humaine (laisser vide pour ouvrir sans déverrouiller)</label>
          <input id="cr-citation" class="input" bind:value={crCitation} placeholder="Ex: Approuvé, déverrouiller pour correction" />
        </div>
        <button id="btn-submit-cr" type="submit" class="btn" disabled={busy}>
          Enregistrer la demande de changement
        </button>
      </form>
    </div>
  </div>
{/if}

<style>
  .mode-switch {
    display: inline-flex;
    gap: 4px;
    background: var(--bg-elevated);
    padding: 3px;
    border-radius: var(--radius-sm);
  }
  .create-box {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 14px;
    margin-bottom: 16px;
  }
  .stages-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
  }
  .stage-col {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
  }
  .stage-head {
    display: flex;
    flex-direction: column;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .stage-head span {
    font-size: 11px;
    color: var(--text-secondary);
  }
  .phase-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .phase-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 10px;
  }
  .phase-card.current {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .phase-card.done {
    opacity: 0.88;
  }
  .phase-top {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .phase-code {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--bg-elevated);
  }
  .phase-name {
    font-weight: 600;
    font-size: 13px;
    flex: 1;
  }
  .phase-gates {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    margin-top: 7px;
  }
  @media (max-width: 980px) {
    .stages-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
