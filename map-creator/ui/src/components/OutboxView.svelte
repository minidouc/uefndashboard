<script>
  import { onMount } from 'svelte';
  import { rpc } from '../lib/rpc.js';

  let { activeProject, notify } = $props();

  let jobs = $state([]);
  let dispatchMode = $state('simulator');
  let busyJob = $state(null);
  let inspectedRaw = $state(null);
  let inspectedPath = $state('');

  const COLUMNS = [
    { id: 'pending', label: 'En attente (pending)', badge: 'warn' },
    { id: 'sent', label: 'Envoyé (sent)', badge: 'accent' },
    { id: 'validated', label: 'Validé & Relu (validated)', badge: 'pass' },
    { id: 'failed', label: 'En échec (failed)', badge: 'fail' }
  ];

  async function loadJobs() {
    try {
      const res = await rpc('outbox.list');
      jobs = res.jobs || [];
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function dispatchJob(jobId) {
    busyJob = jobId;
    try {
      const rep = await rpc('outbox.dispatch', { job_id: jobId, mode: dispatchMode });
      notify(
        `Job '${jobId}' -> ${rep.job.status} (${rep.readback_actor_count} acteurs relus, save=${rep.save_verified}).`,
        rep.job.status !== 'validated'
      );
      await loadJobs();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busyJob = null;
    }
  }

  async function viewRaw(path) {
    try {
      inspectedPath = path;
      inspectedRaw = await rpc('outbox.get_raw_response', { path });
    } catch (e) {
      notify(e.message, true);
    }
  }

  onMount(loadJobs);

  $effect(() => {
    if (activeProject) {
      loadJobs();
    }
  });
</script>

<div class="panel">
  <div class="panel-header">
    <div>
      <h2 class="panel-title">Dossier d'envoi (Outbox asynchrone)</h2>
      <p class="panel-subtitle">
        Les agents n'écrivent que des fichiers. Le cœur Rust vérifie, envoie via MCP, enregistre la réponse brute et relit l'éditeur.
      </p>
    </div>
    <div style="display:flex; gap:8px; align-items:center;">
      <select id="outbox-mode-select" class="select" style="width:auto;" bind:value={dispatchMode}>
        <option value="simulator">Mode Simulateur (hors ligne / fixtures)</option>
        <option value="live">Mode UEFN MCP Live (http://127.0.0.1:8000)</option>
      </select>
      <button id="btn-outbox-refresh" class="btn btn-sm" onclick={loadJobs}>Actualiser</button>
    </div>
  </div>

  <div class="grid-4">
    {#each COLUMNS as col}
      {@const colJobs = jobs.filter((j) => j.status === col.id)}
      <div class="outbox-col">
        <div class="outbox-col-head">
          <span>{col.label}</span>
          <span class="badge {col.badge}">{colJobs.length}</span>
        </div>
        {#each colJobs as job}
          <div class="job-card">
            <div style="display:flex; justify-content:space-between; gap:6px; align-items:center;">
              <strong class="mono" style="font-size:12px;">{job.job_id}</strong>
              <span class="badge">{job.lot_id}</span>
            </div>
            <div class="job-meta">
              <span>{job.district_id} · {job.operations.length} ops</span>
              <span>Essais : {job.attempts}/{job.max_attempts}</span>
            </div>
            <div class="job-layers">
              {#each job.layers_included as l}
                <span class="badge" style="font-size:10px;">{l}</span>
              {/each}
            </div>
            {#if job.error_excerpt}
              <div class="error-excerpt">{job.error_excerpt}</div>
            {/if}
            <div style="display:flex; gap:6px; margin-top:8px; flex-wrap:wrap;">
              {#if job.status === 'pending' || job.status === 'failed'}
                <button
                  id="btn-dispatch-{job.job_id}"
                  class="btn btn-primary btn-sm"
                  onclick={() => dispatchJob(job.job_id)}
                  disabled={busyJob === job.job_id}
                >
                  {busyJob === job.job_id ? 'Envoi...' : 'Envoyer & Relire →'}
                </button>
              {/if}
              {#if job.raw_response_path}
                <button
                  id="btn-raw-{job.job_id}"
                  class="btn btn-sm"
                  onclick={() => viewRaw(job.raw_response_path)}
                >
                  Preuve brute
                </button>
              {/if}
            </div>
          </div>
        {:else}
          <div class="empty-col">Aucun fichier</div>
        {/each}
      </div>
    {/each}
  </div>
</div>

{#if inspectedRaw}
  <div class="panel">
    <div class="panel-header">
      <div>
        <h3 class="panel-title">Réponse brute immuable de l'éditeur</h3>
        <p class="panel-subtitle mono">{inspectedPath}</p>
      </div>
      <button class="btn btn-sm" onclick={() => (inspectedRaw = null)}>Fermer</button>
    </div>
    <pre class="code-box">{JSON.stringify(inspectedRaw, null, 2)}</pre>
  </div>
{/if}

<style>
  .outbox-col {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 10px;
    min-height: 220px;
  }
  .outbox-col-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 700;
    font-size: 12px;
    padding-bottom: 8px;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .job-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 10px;
    margin-bottom: 8px;
  }
  .job-meta {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-secondary);
    margin: 5px 0;
  }
  .job-layers {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .error-excerpt {
    margin-top: 6px;
    padding: 6px 8px;
    border-radius: 4px;
    background: var(--status-fail-bg);
    color: var(--status-fail);
    font-size: 11px;
  }
  .empty-col {
    text-align: center;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 24px 8px;
  }
</style>
