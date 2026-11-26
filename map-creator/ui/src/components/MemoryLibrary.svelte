<script>
  import { onMount } from 'svelte';
  import { rpc } from '../lib/rpc.js';

  let { pipelineData, notify } = $props();

  let tab = $state('library');
  let query = $state('');
  let category = $state('all');
  let entries = $state([]);
  let lessons = $state([]);

  // Add library entry
  let showAddLib = $state(false);
  let libTitle = $state('');
  let libCat = $state('verse_module');
  let libSummary = $state('');
  let libTags = $state('');
  let libProv = $state('validator');
  let libLicense = $state('Studio Internal');
  let libUefn = $state('39.10');
  let libArtifact = $state('');

  // Add lesson
  let newRule = $state('');
  let newIncident = $state('');
  let newLessonProv = $state('human');

  async function searchLibrary() {
    try {
      const res = await rpc('memory.library_search', { query, category });
      entries = res.entries || [];
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function loadLessons() {
    try {
      const res = await rpc('memory.lessons_list');
      lessons = res.lessons || [];
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function checkStaleness() {
    try {
      const res = await rpc('memory.library_check_staleness');
      notify(`Audit version UEFN ${res.uefn_version} : ${res.flagged_suspect} entrée(s) marquée(s) suspecte(s).`);
      await searchLibrary();
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function addLibEntry(e) {
    e.preventDefault();
    try {
      await rpc('memory.library_add', {
        id: '',
        category: libCat,
        title: libTitle.trim(),
        summary: libSummary.trim(),
        tags: libTags.split(',').map((t) => t.trim()).filter(Boolean),
        provenance: libProv,
        proof_ref: 'dashboard-manual',
        source_project: pipelineData?.state?.project_slug || 'studio',
        created_at: '',
        uefn_version: libUefn.trim(),
        license: libLicense.trim(),
        memory_kb: null,
        status: 'verified',
        artifact_path: libArtifact.trim() || 'workspace/library/item'
      });
      showAddLib = false;
      libTitle = '';
      libSummary = '';
      notify('Entrée validée ajoutée à la bibliothèque réutilisable.');
      await searchLibrary();
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function addLesson(e) {
    e.preventDefault();
    try {
      await rpc('memory.lessons_add', {
        rule: newRule.trim(),
        incident: newIncident.trim(),
        provenance: newLessonProv
      });
      newRule = '';
      newIncident = '';
      notify('Leçon apprise ajoutée (injectée aux prochaines sessions).');
      await loadLessons();
    } catch (e) {
      notify(e.message, true);
    }
  }

  onMount(() => {
    searchLibrary();
    loadLessons();
  });
</script>

<div class="panel">
  <div class="panel-header">
    <div>
      <h2 class="panel-title">Mémoire 3 niveaux</h2>
      <p class="panel-subtitle">Seul ce qui est prouvé entre (jamais <code class="mono">agent_claim</code>). Avant de produire, on cherche ici à coût zéro.</p>
    </div>
    <div style="display:flex; gap:6px;">
      <button id="tab-mem-lib" class="btn btn-sm {tab === 'library' ? 'btn-primary' : ''}" onclick={() => (tab = 'library')}>
        3 · Bibliothèque ({entries.length})
      </button>
      <button id="tab-mem-lessons" class="btn btn-sm {tab === 'lessons' ? 'btn-primary' : ''}" onclick={() => (tab = 'lessons')}>
        2 · Leçons apprises ({lessons.length})
      </button>
      <button id="tab-mem-state" class="btn btn-sm {tab === 'state' ? 'btn-primary' : ''}" onclick={() => (tab = 'state')}>
        1 · État projet (&lt; 20 Ko)
      </button>
    </div>
  </div>

  {#if tab === 'library'}
    <div style="display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap;">
      <input
        id="lib-search-input"
        class="input"
        style="flex:1; min-width:220px;"
        bind:value={query}
        oninput={searchLibrary}
        placeholder="Rechercher avant de produire (ex: verse, monolith, skydome, esplanade)..."
      />
      <select id="lib-cat-select" class="select" style="width:auto;" bind:value={category} onchange={searchLibrary}>
        <option value="all">Toutes catégories</option>
        <option value="3d_asset">Modèles 3D</option>
        <option value="verse_module">Modules Verse</option>
        <option value="plan_snippet">Morceaux de plans</option>
        <option value="image_prompt">Prompts images validés</option>
        <option value="device_config">Configs appareils</option>
        <option value="model_benchmark">Tests d'entrée modèles</option>
      </select>
      <button id="btn-lib-stale" class="btn btn-sm" onclick={checkStaleness}>Vérifier obsolètes (MAJ UEFN)</button>
      <button id="btn-lib-add" class="btn btn-primary btn-sm" onclick={() => (showAddLib = !showAddLib)}>
        {showAddLib ? 'Fermer' : '+ Ajouter entrée prouvée'}
      </button>
    </div>

    {#if showAddLib}
      <form class="sub-box" onsubmit={addLibEntry}>
        <div class="grid-3">
          <div class="field"><label for="la-title">Titre</label><input id="la-title" class="input" bind:value={libTitle} required /></div>
          <div class="field">
            <label for="la-cat">Catégorie</label>
            <select id="la-cat" class="select" bind:value={libCat}>
              <option value="verse_module">verse_module</option>
              <option value="3d_asset">3d_asset</option>
              <option value="plan_snippet">plan_snippet</option>
              <option value="image_prompt">image_prompt</option>
              <option value="device_config">device_config</option>
            </select>
          </div>
          <div class="field">
            <label for="la-prov">Provenance (probante uniquement)</label>
            <select id="la-prov" class="select" bind:value={libProv}>
              <option value="validator">validator</option>
              <option value="editor_readback">editor_readback</option>
              <option value="human">human</option>
            </select>
          </div>
        </div>
        <div class="grid-3">
          <div class="field"><label for="la-tags">Tags (virgules)</label><input id="la-tags" class="input" bind:value={libTags} placeholder="verse, timer, hud" /></div>
          <div class="field"><label for="la-lic">Licence</label><input id="la-lic" class="input" bind:value={libLicense} required /></div>
          <div class="field"><label for="la-uefn">Version UEFN</label><input id="la-uefn" class="input mono" bind:value={libUefn} required /></div>
        </div>
        <div class="grid-2">
          <div class="field"><label for="la-sum">Résumé</label><input id="la-sum" class="input" bind:value={libSummary} required /></div>
          <div class="field"><label for="la-path">Chemin artefact</label><input id="la-path" class="input mono" bind:value={libArtifact} /></div>
        </div>
        <button type="submit" class="btn btn-primary btn-sm">Enregistrer dans la bibliothèque</button>
      </form>
    {/if}

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Entrée</th><th>Catégorie</th><th>Provenance</th><th>UEFN</th><th>Licence</th><th>Statut</th></tr>
        </thead>
        <tbody>
          {#each entries as e}
            <tr>
              <td>
                <strong>{e.title}</strong>
                <div style="font-size:12px; color:var(--text-secondary);">{e.summary}</div>
                <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
                  {#each e.tags as t}<span class="badge" style="font-size:10px;">{t}</span>{/each}
                </div>
              </td>
              <td class="mono" style="font-size:12px;">{e.category}</td>
              <td><span class="badge pass">{e.provenance}</span></td>
              <td class="mono">{e.uefn_version}</td>
              <td style="font-size:12px;">{e.license}</td>
              <td>
                <span class="badge {e.status === 'verified' ? 'pass' : e.status === 'suspect' ? 'warn' : 'fail'}">
                  {e.status.toUpperCase()}
                </span>
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" style="color:var(--text-secondary);">Aucun résultat dans la bibliothèque.</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if tab === 'lessons'}
    <form class="sub-box" onsubmit={addLesson}>
      <div class="grid-3">
        <div class="field"><label for="ls-rule">Nouvelle règle (1 ligne)</label><input id="ls-rule" class="input" bind:value={newRule} required /></div>
        <div class="field"><label for="ls-inc">Incident qui l'a fait naître</label><input id="ls-inc" class="input" bind:value={newIncident} required /></div>
        <div class="field">
          <label for="ls-prov">Provenance</label>
          <select id="ls-prov" class="select" bind:value={newLessonProv}>
            <option value="human">human</option>
            <option value="validator">validator</option>
            <option value="editor_readback">editor_readback</option>
          </select>
        </div>
      </div>
      <button id="btn-add-lesson" type="submit" class="btn btn-primary btn-sm">Ajouter la leçon</button>
    </form>

    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>ID</th><th>Règle active (injectée au démarrage)</th><th>Incident source</th><th>Provenance</th></tr></thead>
        <tbody>
          {#each lessons as l}
            <tr>
              <td class="mono">{l.id}</td>
              <td>{l.rule}</td>
              <td style="font-size:12px; color:var(--text-secondary);">{l.incident}</td>
              <td><span class="badge pass">{l.provenance}</span></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if pipelineData}
    {@const pct = Math.min(100, Math.round((pipelineData.state_bytes / pipelineData.max_state_bytes) * 100))}
    <div class="sub-box">
      <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
        <strong>Taille de state.json (plafond strict 20 Ko)</strong>
        <span class="mono">{pipelineData.state_bytes} / {pipelineData.max_state_bytes} octets ({pct}%)</span>
      </div>
      <div class="meter-track"><div class="meter-fill" style="width:{pct}%;"></div></div>
    </div>
    <pre class="code-box">{JSON.stringify(pipelineData.state, null, 2)}</pre>
  {/if}
</div>

<style>
  .sub-box {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 14px;
    margin-bottom: 14px;
  }
  .meter-track {
    height: 8px;
    background: var(--border-subtle);
    border-radius: 4px;
    overflow: hidden;
  }
  .meter-fill {
    height: 100%;
    background: var(--status-pass);
  }
</style>
