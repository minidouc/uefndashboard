<script>
  import { onMount } from 'svelte';
  import { rpc } from '../lib/rpc.js';

  let { appConfig, pendingApprovals, onResolveApproval, notify } = $props();

  let selectedRole = $state('orchestrateur');
  let prompt = $state('Vérifie l\'état du projet, cherche dans la bibliothèque et contrôle le plan 4 couches district_plaza.');
  let running = $state(false);
  let sessions = $state([]);
  let activeSession = $state(null);

  let rolesList = $derived(Object.entries(appConfig?.roles || {}));
  let currentRoleCfg = $derived(appConfig?.roles?.[selectedRole]);

  const QUICK_MISSIONS = [
    { label: 'Audit plan + bibliothèque', role: 'orchestrateur', prompt: 'Vérifie l\'état, cherche dans la bibliothèque et contrôle le plan district_plaza.' },
    { label: 'Lancer validateurs 20 cas', role: 'orchestrateur', prompt: 'Lance les validateurs protégés (golden + règles) sur le projet actif.' },
    { label: 'Test sécurité (tentative triche MANIFEST)', role: 'level_designer', prompt: 'Tente de modifier validators/MANIFEST.json pour tester la protection triche.' },
    { label: 'Test permission shell (git status)', role: 'programmeur_verse', prompt: 'Exécute une commande shell git status pour vérifier le dépôt.' },
    { label: 'Préparer lot Outbox depuis plan', role: 'level_designer', prompt: 'Prépare un nouveau lot dans l\'outbox à partir du plan validé.' }
  ];

  async function loadHistory() {
    try {
      const res = await rpc('agent.history');
      sessions = res.sessions || [];
      if (!activeSession && sessions.length > 0) {
        activeSession = sessions[0];
      }
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function runMission(e) {
    e?.preventDefault();
    if (!prompt.trim()) return;
    running = true;
    try {
      const session = await rpc('agent.run', { role: selectedRole, prompt: prompt.trim() });
      activeSession = session;
      sessions = [session, ...sessions.filter((s) => s.session_id !== session.session_id)];
      notify(`Mission '${selectedRole}' terminée (${session.steps.length} étapes).`);
    } catch (err) {
      notify(err.message, true);
    } finally {
      running = false;
    }
  }

  function applyQuick(q) {
    selectedRole = q.role;
    prompt = q.prompt;
  }

  onMount(loadHistory);
</script>

<div class="grid-2" style="align-items:start;">
  <div class="panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">Console Agent — Boucle Rust App Server</h2>
        <p class="panel-subtitle">Appel modèle → outil → moteur de permissions → exécution → résumé borné (5 lignes).</p>
      </div>
    </div>

    <div class="quick-bar">
      {#each QUICK_MISSIONS as q}
        <button class="btn btn-sm" onclick={() => applyQuick(q)}>{q.label}</button>
      {/each}
    </div>

    <form onsubmit={runMission}>
      <div class="field">
        <label for="agent-role-select">Rôle de l'équipe (1 Orchestrateur + 9 Spécialistes)</label>
        <select id="agent-role-select" class="select" bind:value={selectedRole}>
          {#each rolesList as [id, r]}
            <option value={id}>{r.label} ({r.tier}{r.readonly ? ' · lecture seule' : ''}) — {r.provider}</option>
          {/each}
        </select>
      </div>

      {#if currentRoleCfg}
        <div class="role-meta">
          <span>Modèle : <strong class="mono">{currentRoleCfg.model}</strong></span>
          <span>Niveau : <strong class="mono">{currentRoleCfg.tier}</strong></span>
          {#if currentRoleCfg.readonly}
            <span class="badge warn">LECTURE SEULE (JUGE)</span>
          {/if}
        </div>
      {/if}

      <div class="field">
        <label for="agent-prompt">Mission / Instruction</label>
        <textarea id="agent-prompt" class="textarea" bind:value={prompt} placeholder="Décrivez la mission bornée..."></textarea>
      </div>

      <button id="btn-agent-run" type="submit" class="btn btn-primary" disabled={running}>
        {running ? 'Boucle en cours...' : 'Lancer la mission'}
      </button>
    </form>

    {#if pendingApprovals && pendingApprovals.length > 0}
      <div class="pending-box">
        <strong>Approbations de permissions en attente</strong>
        {#each pendingApprovals as apr}
          <div class="apr-card">
            <div>
              <span class="badge warn">{apr.action}</span>
              <strong class="mono" style="font-size:12px;">{apr.target}</strong>
              <div style="font-size:12px; color:var(--text-secondary);">{apr.reason} (rôle: {apr.role})</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-pass btn-sm" onclick={() => onResolveApproval(apr.approval_id, true)}>Autoriser</button>
              <button class="btn btn-danger btn-sm" onclick={() => onResolveApproval(apr.approval_id, false)}>Refuser</button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <div class="panel">
    <div class="panel-header">
      <div>
        <h3 class="panel-title">Trace d'exécution &amp; Résumé borné</h3>
        <p class="panel-subtitle">
          {#if activeSession}
            Session <code class="mono">{activeSession.session_id}</code> · {activeSession.role} · {activeSession.status}
          {:else}
            Lancez une mission pour observer la boucle outil/permission en direct.
          {/if}
        </p>
      </div>
    </div>

    {#if activeSession}
      <div class="summary-card">
        <div style="font-size:11px; font-weight:700; color:var(--text-secondary); margin-bottom:4px;">RÉSUMÉ BORNÉ (5 LIGNES MAX — PROVENANCE: agent_claim)</div>
        <pre style="margin:0; font-family:var(--font-sans); white-space:pre-wrap; font-size:13px;">{activeSession.bounded_summary}</pre>
      </div>

      <div class="steps-list">
        {#each activeSession.steps as st}
          <div class="step-item">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="badge {st.tool_exec ? (st.tool_exec.ok ? 'pass' : 'fail') : ''}">
                #{st.step} · {st.kind}
              </span>
              <span class="mono" style="font-size:10px; color:var(--text-secondary);">{st.ts_utc.slice(11, 19)}</span>
            </div>
            <div style="margin-top:4px; font-size:13px;">{st.text}</div>
            {#if st.tool_exec}
              <details style="margin-top:6px;">
                <summary class="mono" style="font-size:11px; cursor:pointer; color:var(--text-secondary);">
                  {st.tool_exec.tool} → {st.tool_exec.ok ? 'OK' : 'BLOQUÉ / ERREUR'}
                </summary>
                <pre class="code-box" style="margin-top:6px; max-height:180px;">{JSON.stringify(st.tool_exec.ok ? st.tool_exec.output : st.tool_exec.error, null, 2)}</pre>
              </details>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .quick-bar {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }
  .role-meta {
    display: flex;
    gap: 12px;
    align-items: center;
    font-size: 12px;
    color: var(--text-secondary);
    padding: 8px 10px;
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    margin-bottom: 10px;
    flex-wrap: wrap;
  }
  .pending-box {
    margin-top: 16px;
    padding: 12px;
    border-radius: var(--radius-sm);
    background: var(--status-warn-bg);
    border: 1px solid var(--status-warn);
  }
  .apr-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-top: 8px;
    padding: 8px;
    background: var(--bg-surface);
    border-radius: 5px;
  }
  .summary-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
    margin-bottom: 12px;
  }
  .steps-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 460px;
    overflow-y: auto;
  }
  .step-item {
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 10px;
    background: var(--bg-surface);
  }
</style>
