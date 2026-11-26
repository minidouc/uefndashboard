<script>
  import { onMount } from 'svelte';
  import { rpc } from '../lib/rpc.js';

  let { activeProject, notify } = $props();

  let valStatus = $state(null);
  let lastReport = $state(null);
  let events = $state([]);
  let provFilter = $state('all');
  let compat = $state(null);
  let circuitBreakers = $state({ writes_halted: false, blocked_tools: [], reason: '' });
  let runningVal = $state(false);

  // PC Agent fixture ingestion form
  let showIngest = $state(false);
  let ingTool = $state('SceneTools.add_to_scene_from_asset');
  let ingStatus = $state('OK');
  let ingUefn = $state('39.10');
  let ingNotes = $state('Testé par l\'Agent PC sur UEFN 39.10 : format inchangé.');
  let ingPayload = $state('{\n  "returnValue": { "actorPath": "/Game/Test/Main.MC_Prop01" }\n}');
  let newBlockedTool = $state('');

  async function loadAll() {
    try {
      const [vs, ev, cm, cfg] = await Promise.all([
        rpc('validators.status'),
        rpc('pipeline.events', { limit: 40, provenance: provFilter }),
        rpc('compat.status'),
        rpc('config.get')
      ]);
      valStatus = vs;
      lastReport = vs.latest_report;
      events = ev.events || [];
      compat = cm;
      circuitBreakers = cfg.circuit_breakers || { writes_halted: false, blocked_tools: [], reason: '' };
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function runValidators(goldenOnly = false) {
    runningVal = true;
    try {
      const rep = await rpc('validators.run', { golden_only: goldenOnly });
      lastReport = rep;
      notify(
        `Validateurs : ${rep.verdict} (MANIFEST=${rep.manifest_integrity}, Golden=${rep.golden_results.filter((g) => g.passed).length}/${rep.golden_total})`,
        rep.verdict !== 'PASS'
      );
      await loadAll();
    } catch (e) {
      notify(e.message, true);
    } finally {
      runningVal = false;
    }
  }

  async function toggleWritesHalted() {
    const next = {
      ...circuitBreakers,
      writes_halted: !circuitBreakers.writes_halted,
      reason: !circuitBreakers.writes_halted ? 'Coupure d\'urgence activée depuis le Dashboard' : null
    };
    try {
      await rpc('config.update_circuit_breakers', next);
      circuitBreakers = next;
      notify(next.writes_halted ? 'COUPE-CIRCUIT ACTIVÉ : toutes écritures MCP bloquées.' : 'Coupe-circuit levé.');
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function addBlockedTool() {
    if (!newBlockedTool.trim()) return;
    const next = {
      ...circuitBreakers,
      blocked_tools: [...new Set([...(circuitBreakers.blocked_tools || []), newBlockedTool.trim()])]
    };
    await rpc('config.update_circuit_breakers', next);
    circuitBreakers = next;
    newBlockedTool = '';
    notify('Outil ajouté au coupe-circuit MCP.');
  }

  async function removeBlockedTool(tool) {
    const next = {
      ...circuitBreakers,
      blocked_tools: (circuitBreakers.blocked_tools || []).filter((t) => t !== tool)
    };
    await rpc('config.update_circuit_breakers', next);
    circuitBreakers = next;
  }

  async function ingestFixture(e) {
    e.preventDefault();
    try {
      const parsed = JSON.parse(ingPayload);
      compat = await rpc('compat.ingest_fixture', {
        tool: ingTool.trim(),
        status: ingStatus,
        uefn_version: ingUefn.trim(),
        notes: ingNotes.trim(),
        payload: parsed
      });
      showIngest = false;
      notify(`Fixture Agent PC ingérée pour ${ingTool} (${ingStatus}).`);
    } catch (err) {
      notify(`JSON ou ingestion invalide : ${err.message}`, true);
    }
  }

  onMount(loadAll);

  $effect(() => {
    if (activeProject) {
      loadAll();
    }
  });
</script>

<!-- 1. Protected Validators + 20-Case Golden Set -->
<div class="panel">
  <div class="panel-header">
    <div>
      <h2 class="panel-title">Validateurs protégés (SHA-256 MANIFEST + 20 cas Golden Set)</h2>
      <p class="panel-subtitle">
        Ordre immuable : 1) Empreinte SHA-256 → 2) Auto-test 20 cas (18 pièges) → 3) Règles réelles sur preuves brutes.
      </p>
    </div>
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
      {#if valStatus}
        <span class="badge {valStatus.manifest_integrity === 'OK' ? 'pass' : 'fail'}">
          MANIFEST : {valStatus.manifest_integrity}
        </span>
      {/if}
      <button id="btn-run-golden" class="btn btn-sm" onclick={() => runValidators(true)} disabled={runningVal}>
        Auto-test Golden (20 cas)
      </button>
      <button id="btn-run-validators" class="btn btn-primary btn-sm" onclick={() => runValidators(false)} disabled={runningVal}>
        {runningVal ? 'Validation...' : 'Lancer validation complète'}
      </button>
    </div>
  </div>

  {#if lastReport}
    <div class="grid-3" style="margin-bottom:14px;">
      <div class="kpi">
        <span>Verdict global</span>
        <strong class={lastReport.verdict === 'PASS' ? 'txt-pass' : 'txt-fail'}>{lastReport.verdict}</strong>
      </div>
      <div class="kpi">
        <span>Golden Set (anti-affaiblissement)</span>
        <strong class={lastReport.golden_set_passed ? 'txt-pass' : 'txt-fail'}>
          {lastReport.golden_results?.filter((g) => g.passed).length || 0} / {lastReport.golden_total} PASS
        </strong>
      </div>
      <div class="kpi">
        <span>Règles projet vérifiées</span>
        <strong>{lastReport.rules?.length || 0} règles</strong>
      </div>
    </div>

    {#if lastReport.rules && lastReport.rules.length > 0}
      <div class="table-wrap" style="margin-bottom:14px;">
        <table class="data-table">
          <thead><tr><th>Règle</th><th>Verdict</th><th>Éléments vérifiés</th><th>Violations</th></tr></thead>
          <tbody>
            {#each lastReport.rules as r}
              <tr>
                <td class="mono">{r.rule}</td>
                <td><span class="badge {r.verdict === 'PASS' ? 'pass' : 'fail'}">{r.verdict}</span></td>
                <td class="mono">{r.checked_count}</td>
                <td>
                  {#if r.violations.length === 0}
                    <span style="color:var(--status-pass); font-size:12px;">Aucune violation</span>
                  {:else}
                    {#each r.violations as v}
                      <div style="font-size:12px; color:var(--status-fail);">{v.detail}</div>
                    {/each}
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if lastReport.golden_results && lastReport.golden_results.length > 0}
      <details>
        <summary style="cursor:pointer; font-weight:600; font-size:13px;">
          Détail des {lastReport.golden_results.length} cas Golden Set (2 sains + 18 pièges)
        </summary>
        <div class="golden-grid" style="margin-top:10px;">
          {#each lastReport.golden_results as g}
            <div class="golden-chip" class:fail={!g.passed}>
              <span class="mono" style="font-size:11px;">{g.case_id}</span>
              <span class="badge {g.passed ? 'pass' : 'fail'}">{g.passed ? 'PASS' : 'FAIL'}</span>
            </div>
          {/each}
        </div>
      </details>
    {/if}
  {:else}
    <p style="color:var(--text-secondary); margin:0;">Cliquez sur « Lancer validation complète » pour auditer le projet actif et les 20 cas pièges.</p>
  {/if}
</div>

<!-- 2. Agent PC Compatibility Matrix + MCP Circuit Breakers -->
<div class="grid-2" style="margin-top:16px;">
  <div class="panel">
    <div class="panel-header">
      <div>
        <h3 class="panel-title">Compatibilité UEFN (Agent PC ↔ Harnais)</h3>
        <p class="panel-subtitle">
          {#if compat}
            Cible UEFN <strong class="mono">{compat.uefn_version_target}</strong> ·
            OK: {compat.counts.ok} · À tester: {compat.counts.untested} · Cassés: {compat.counts.broken}
          {/if}
        </p>
      </div>
      <button id="btn-ingest-fixture" class="btn btn-sm" onclick={() => (showIngest = !showIngest)}>
        {showIngest ? 'Fermer' : '+ Ingérer fixture Agent PC'}
      </button>
    </div>

    {#if showIngest}
      <form class="sub-box" onsubmit={ingestFixture}>
        <div class="grid-3">
          <div class="field"><label for="ing-tool">Outil MCP</label><input id="ing-tool" class="input mono" bind:value={ingTool} required /></div>
          <div class="field">
            <label for="ing-st">Statut</label>
            <select id="ing-st" class="select" bind:value={ingStatus}>
              <option value="OK">OK</option>
              <option value="FORMAT_CHANGED">FORMAT_CHANGED</option>
              <option value="BROKEN">BROKEN</option>
              <option value="UNTESTED">UNTESTED</option>
            </select>
          </div>
          <div class="field"><label for="ing-v">Version UEFN</label><input id="ing-v" class="input mono" bind:value={ingUefn} /></div>
        </div>
        <div class="field"><label for="ing-notes">Notes terrain</label><input id="ing-notes" class="input" bind:value={ingNotes} /></div>
        <div class="field"><label for="ing-json">Réponse JSON brute capturée sur PC</label><textarea id="ing-json" class="textarea mono" bind:value={ingPayload}></textarea></div>
        <button type="submit" class="btn btn-primary btn-sm">Enregistrer fixture &amp; mettre à jour COMPAT_STATUS.md</button>
      </form>
    {/if}

    {#if compat}
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Outil MCP</th><th>Statut</th><th>Notes</th></tr></thead>
          <tbody>
            {#each compat.rows as row}
              <tr>
                <td class="mono" style="font-size:12px;">{row.tool}</td>
                <td>
                  <span class="badge {row.status === 'OK' ? 'pass' : row.status === 'UNTESTED' ? 'warn' : 'fail'}">
                    {row.status}
                  </span>
                </td>
                <td style="font-size:12px; color:var(--text-secondary);">{row.notes}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>

  <!-- Provenance Ledger + Circuit Breakers -->
  <div style="display:flex; flex-direction:column; gap:16px;">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h3 class="panel-title">Coupe-circuit MCP d'urgence</h3>
          <p class="panel-subtitle">Relu à CHAQUE appel par le cœur Rust (`config/circuit_breakers.json`).</p>
        </div>
        <button
          id="btn-toggle-killswitch"
          class="btn btn-sm {circuitBreakers.writes_halted ? 'btn-pass' : 'btn-danger'}"
          onclick={toggleWritesHalted}
        >
          {circuitBreakers.writes_halted ? 'Réactiver écritures MCP' : 'COUPER TOUTES ÉCRITURES'}
        </button>
      </div>
      <div style="display:flex; gap:6px; margin-bottom:10px;">
        <input class="input mono" bind:value={newBlockedTool} placeholder="Ex: SceneTools.set_actor_folder" />
        <button class="btn btn-sm" onclick={addBlockedTool}>Couper outil</button>
      </div>
      <div style="display:flex; gap:6px; flex-wrap:wrap;">
        {#each circuitBreakers.blocked_tools || [] as bt}
          <span class="badge fail">
            {bt}
            <button style="border:none;background:none;color:inherit;cursor:pointer;padding:0 2px;" onclick={() => removeBlockedTool(bt)}>×</button>
          </span>
        {:else}
          <span style="font-size:12px; color:var(--text-secondary);">Aucun outil individuellement coupé.</span>
        {/each}
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <h3 class="panel-title">Journal de provenance (events.jsonl)</h3>
          <p class="panel-subtitle">Seules les provenances <code class="mono">validator</code>, <code class="mono">editor_readback</code> et <code class="mono">human</code> font preuve.</p>
        </div>
        <select class="select" style="width:auto;" bind:value={provFilter} onchange={loadAll}>
          <option value="all">Toutes provenances</option>
          <option value="validator">validator</option>
          <option value="editor_readback">editor_readback</option>
          <option value="human">human</option>
          <option value="script">script</option>
          <option value="agent_claim">agent_claim (non probant)</option>
        </select>
      </div>
      <div class="events-scroll">
        {#each events as ev}
          <div class="evt-row">
            <span class="badge {ev.provenance === 'agent_claim' ? 'warn' : ev.provenance === 'script' ? '' : 'pass'}">
              {ev.provenance}
            </span>
            <div style="flex:1; font-size:12px;">
              <div>{ev.message}</div>
              {#if ev.proof}<div class="mono" style="font-size:11px; color:var(--text-secondary);">{ev.proof}</div>{/if}
            </div>
            <span class="mono" style="font-size:10px; color:var(--text-secondary);">{ev.ts_utc.slice(11, 19)}</span>
          </div>
        {/each}
      </div>
    </div>
  </div>
</div>

<style>
  .kpi {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .kpi span {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .kpi strong {
    font-size: 18px;
  }
  .txt-pass { color: var(--status-pass); }
  .txt-fail { color: var(--status-fail); }
  .golden-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 6px;
  }
  .golden-chip {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    border-radius: 5px;
    border: 1px solid var(--border-subtle);
    background: var(--bg-elevated);
  }
  .golden-chip.fail {
    border-color: var(--status-fail);
  }
  .sub-box {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
    margin-bottom: 12px;
  }
  .events-scroll {
    max-height: 300px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .evt-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
  }
</style>
