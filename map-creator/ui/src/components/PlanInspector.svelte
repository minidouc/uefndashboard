<script>
  import { onMount } from 'svelte';
  import { rpc } from '../lib/rpc.js';

  let { activeProject, notify } = $props();

  let plans = $state([]);
  let selectedDistrict = $state('');
  let planData = $state(null);
  let checkReport = $state(null);
  let svg2d = $state('');
  let svgSection = $state('');
  let showSection = $state(false);
  let zoom = $state(1);

  let visibleLayers = $state({
    a_scene: true,
    b_fonds: true,
    c_details: true,
    d_effets: true
  });

  let selectedItem = $state(null);
  let showAddForm = $state(false);

  // Add item form state
  let newLayer = $state('c_details');
  let newId = $state('PROP_NEW_01');
  let newLabel = $state('Borne Signalétique');
  let newKind = $state('prop');
  let newPass = $state('admirable');
  let newReason = $state('Pointe visuellement la direction de la terrasse nord dès la sortie du spawn.');
  let newTileX = $state(6);
  let newTileY = $state(9);
  let newFloorZ = $state(0);
  let newSizeX = $state(1);
  let newSizeY = $state(1);
  let newHeightF = $state(0.5);
  let newAsset = $state('GRAYBOX:CUBE');

  const LAYER_META = [
    { id: 'a_scene', label: 'a · Scène principale', color: 'var(--layer-a)', phase: 'Phase 3' },
    { id: 'b_fonds', label: 'b · Fonds / Horizon', color: 'var(--layer-b)', phase: 'Phase 3' },
    { id: 'c_details', label: 'c · Détails / Décor', color: 'var(--layer-c)', phase: 'Phase 5' },
    { id: 'd_effets', label: 'd · Effets / Son / Lumière', color: 'var(--layer-d)', phase: 'Phase 7' }
  ];

  async function loadPlans() {
    try {
      const res = await rpc('plan.list');
      plans = res.plans || [];
      if (plans.length > 0 && !plans.includes(selectedDistrict)) {
        selectedDistrict = plans[0];
      }
      if (selectedDistrict) {
        await loadDistrict(selectedDistrict);
      }
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function loadDistrict(did) {
    try {
      const res = await rpc('plan.get', { district_id: did });
      planData = res.plan;
      checkReport = res.check;
      await refreshSvg();
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function refreshSvg() {
    if (!selectedDistrict) return;
    const active = Object.entries(visibleLayers)
      .filter(([, v]) => v)
      .map(([k]) => k);
    const res = await rpc('plan.render_svg', {
      district_id: selectedDistrict,
      layers: active.length ? active : ['__none__']
    });
    svg2d = res.svg_2d;
    svgSection = res.svg_section;
  }

  async function toggleLayer(id) {
    visibleLayers[id] = !visibleLayers[id];
    await refreshSvg();
  }

  function handleCanvasClick(e) {
    const group = e.target.closest('g[data-item-id]');
    if (!group || !planData) return;
    const id = group.getAttribute('data-item-id');
    const layer = group.getAttribute('data-layer');
    const list = planData.layers[layer] || [];
    const found = list.find((it) => it.id === id);
    if (found) {
      selectedItem = { ...found, layer };
    }
  }

  async function addItem(e) {
    e.preventDefault();
    try {
      const res = await rpc('plan.upsert_item', {
        district_id: selectedDistrict,
        layer: newLayer,
        item: {
          id: newId.trim(),
          label: newLabel.trim(),
          kind: newKind,
          pass: newPass,
          reason: newReason.trim(),
          tile_x: Number(newTileX),
          tile_y: Number(newTileY),
          floor_z: Number(newFloorZ),
          size_tiles_x: Number(newSizeX),
          size_tiles_y: Number(newSizeY),
          height_floors: Number(newHeightF),
          yaw_deg: 0,
          asset_ref: newAsset.trim() || 'GRAYBOX:CUBE',
          estimated_memory_kb: 14,
          floating_exempt: ['light', 'vfx', 'audio_zone'].includes(newKind)
        }
      });
      planData = res.plan;
      checkReport = res.check;
      await refreshSvg();
      showAddForm = false;
      notify(`Objet '${newId}' ajouté au plan (${checkReport.verdict}).`);
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function sendToOutbox() {
    try {
      const active = Object.entries(visibleLayers)
        .filter(([, v]) => v)
        .map(([k]) => k);
      const lotId = `lot_${Math.floor(Date.now() / 1000) % 1000}`;
      const job = await rpc('outbox.submit_from_plan', {
        district_id: selectedDistrict,
        layers: active,
        lot_id: lotId
      });
      notify(`Lot '${job.job_id}' déposé dans outbox/pending/ (${job.operations.length} opérations).`);
    } catch (e) {
      notify(e.message, true);
    }
  }

  onMount(loadPlans);

  $effect(() => {
    if (activeProject) {
      loadPlans();
    }
  });
</script>

<div class="panel">
  <div class="panel-header">
    <div>
      <h2 class="panel-title">Inspecteur de plans 2D — 4 couches &amp; Coupe</h2>
      <p class="panel-subtitle">
        {#if planData}
          Grille : <strong class="mono">1 tuile = {planData.grid.tile_size_uu} uu</strong> ·
          <strong class="mono">1 étage = {planData.grid.floor_height_uu} uu</strong> ·
          Mémoire estimée : <strong class="mono">{checkReport?.estimated_memory_kb} / {planData.memory_budget_kb} Ko</strong>
        {:else}
          Sélectionnez un plan de quartier.
        {/if}
      </p>
    </div>
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
      <select
        id="plan-district-select"
        class="select"
        style="width:auto;"
        bind:value={selectedDistrict}
        onchange={() => loadDistrict(selectedDistrict)}
      >
        {#each plans as p}
          <option value={p}>{p}</option>
        {/each}
      </select>
      {#if checkReport}
        <span class="badge {checkReport.verdict === 'PASS' ? 'pass' : 'fail'}">
          CHECK PLAN : {checkReport.verdict}
        </span>
      {/if}
      <button id="btn-toggle-section" class="btn btn-sm" onclick={() => (showSection = !showSection)}>
        {showSection ? 'Masquer la coupe' : 'Afficher la coupe A-A\''}
      </button>
      <button id="btn-add-plan-item" class="btn btn-sm" onclick={() => (showAddForm = !showAddForm)}>
        {showAddForm ? 'Fermer' : '+ Ajouter objet'}
      </button>
      <button id="btn-plan-to-outbox" class="btn btn-primary btn-sm" onclick={sendToOutbox}>
        Générer lot Outbox →
      </button>
    </div>
  </div>

  <!-- Layer toggles -->
  <div class="layer-toolbar">
    {#each LAYER_META as lm}
      <label class="layer-chip" class:active={visibleLayers[lm.id]}>
        <input
          type="checkbox"
          checked={visibleLayers[lm.id]}
          onchange={() => toggleLayer(lm.id)}
        />
        <span class="layer-dot" style="background:{lm.color};"></span>
        <span>{lm.label}</span>
        <span class="mono" style="font-size:10px; opacity:0.7;">({lm.phase})</span>
      </label>
    {/each}

    <div style="margin-left:auto; display:flex; gap:6px; align-items:center;">
      <button class="btn btn-sm" onclick={() => (zoom = Math.max(0.6, +(zoom - 0.15).toFixed(2)))}>−</button>
      <span class="mono" style="font-size:12px;">{Math.round(zoom * 100)}%</span>
      <button class="btn btn-sm" onclick={() => (zoom = Math.min(1.9, +(zoom + 0.15).toFixed(2)))}>+</button>
    </div>
  </div>

  {#if showAddForm}
    <form class="add-item-box" onsubmit={addItem}>
      <div class="grid-4">
        <div class="field">
          <label for="ni-layer">Couche</label>
          <select id="ni-layer" class="select" bind:value={newLayer}>
            <option value="a_scene">a · Scène</option>
            <option value="b_fonds">b · Fonds</option>
            <option value="c_details">c · Détails</option>
            <option value="d_effets">d · Effets</option>
          </select>
        </div>
        <div class="field">
          <label for="ni-id">ID unique</label>
          <input id="ni-id" class="input mono" bind:value={newId} required />
        </div>
        <div class="field">
          <label for="ni-label">Libellé</label>
          <input id="ni-label" class="input" bind:value={newLabel} required />
        </div>
        <div class="field">
          <label for="ni-kind">Type / Passe</label>
          <div style="display:flex; gap:6px;">
            <select id="ni-kind" class="select" bind:value={newKind}>
              <option value="surface">surface</option>
              <option value="structure">structure</option>
              <option value="cover">cover</option>
              <option value="ramp">ramp</option>
              <option value="prop">prop</option>
              <option value="device">device</option>
              <option value="light">light</option>
              <option value="audio_zone">audio_zone</option>
            </select>
            <select class="select" bind:value={newPass}>
              <option value="reel">réel</option>
              <option value="jouable">jouable</option>
              <option value="admirable">admirable</option>
            </select>
          </div>
        </div>
      </div>
      <div class="grid-4">
        <div class="field"><label for="ni-x">Tuile X</label><input id="ni-x" type="number" step="0.5" class="input mono" bind:value={newTileX} /></div>
        <div class="field"><label for="ni-y">Tuile Y</label><input id="ni-y" type="number" step="0.5" class="input mono" bind:value={newTileY} /></div>
        <div class="field"><label for="ni-sx">Largeur X (tuiles)</label><input id="ni-sx" type="number" step="0.5" class="input mono" bind:value={newSizeX} /></div>
        <div class="field"><label for="ni-sy">Profondeur Y (tuiles)</label><input id="ni-sy" type="number" step="0.5" class="input mono" bind:value={newSizeY} /></div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="ni-reason">Raison d'être de l'objet (obligatoire)</label>
          <input id="ni-reason" class="input" bind:value={newReason} required />
        </div>
        <div class="field">
          <label for="ni-asset">Référence asset (GRAYBOX / ASSET: / DEVICE:)</label>
          <input id="ni-asset" class="input mono" bind:value={newAsset} />
        </div>
      </div>
      <button id="btn-save-plan-item" type="submit" class="btn btn-primary btn-sm">Enregistrer et re-vérifier le plan</button>
    </form>
  {/if}

  <div class="inspector-split">
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions, a11y_click_events_have_key_events -->
    <div
      class="blueprint-viewport"
      role="region"
      aria-label="Plan 2D interactif"
      onclick={handleCanvasClick}
    >
      <div class="svg-zoom-wrap" style="transform: scale({zoom}); transform-origin: top left;">
        {@html svg2d}
      </div>
      {#if showSection}
        <div class="section-wrap">
          <div class="panel-subtitle" style="margin-bottom:6px; font-weight:600;">Vue en coupe A-A' (élévation en étages de 384 uu)</div>
          {@html svgSection}
        </div>
      {/if}
    </div>

    <aside class="inspector-side">
      {#if selectedItem && planData}
        <div class="side-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong class="mono">{selectedItem.id}</strong>
            <span class="badge">{selectedItem.pass}</span>
          </div>
          <div style="font-size:15px; font-weight:700; margin:4px 0 10px;">{selectedItem.label}</div>
          <div class="kv"><span>Couche</span><span class="mono">{selectedItem.layer}</span></div>
          <div class="kv"><span>Type</span><span class="mono">{selectedItem.kind}</span></div>
          <div class="kv"><span>Grille</span><span class="mono">({selectedItem.tile_x}, {selectedItem.tile_y}) · {selectedItem.size_tiles_x}×{selectedItem.size_tiles_y}</span></div>
          <div class="kv">
            <span>Monde (cm/uu)</span>
            <span class="mono">
              X={Math.round(selectedItem.tile_x * planData.grid.tile_size_uu)} · Y={Math.round(selectedItem.tile_y * planData.grid.tile_size_uu)} · Z={Math.round(selectedItem.floor_z * planData.grid.floor_height_uu)}
            </span>
          </div>
          <div class="kv"><span>Asset</span><span class="mono" style="font-size:11px;">{selectedItem.asset_ref}</span></div>
          <div class="kv"><span>Mémoire est.</span><span class="mono">{selectedItem.estimated_memory_kb} Ko</span></div>
          <div class="reason-box">
            <div style="font-size:11px; color:var(--text-secondary); font-weight:600; margin-bottom:3px;">RAISON D'AUTEUR</div>
            {selectedItem.reason}
          </div>
        </div>
      {:else}
        <div class="side-card">
          <p style="margin:0; color:var(--text-secondary);">Cliquez sur un élément du plan 2D pour inspecter ses coordonnées grille/cm, sa passe (réel/jouable/admirable) et sa raison.</p>
        </div>
      {/if}

      {#if checkReport}
        <div class="side-card" style="margin-top:12px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong>Contrôle géométrique</strong>
            <span class="badge {checkReport.verdict === 'PASS' ? 'pass' : 'fail'}">{checkReport.verdict}</span>
          </div>
          {#if checkReport.issues.length === 0}
            <p style="margin:0; font-size:12px; color:var(--status-pass);">
              0 chevauchement · 0 flottant · 100 % des objets motivés · budget mémoire respecté.
            </p>
          {:else}
            <ul class="issue-list">
              {#each checkReport.issues as iss}
                <li>
                  <span class="badge {iss.severity === 'error' ? 'fail' : 'warn'}">{iss.rule}</span>
                  <span>{iss.detail}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </aside>
  </div>
</div>

<style>
  .layer-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
    padding: 8px 10px;
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
  }
  .layer-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 9px;
    border-radius: 5px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    font-size: 12px;
    cursor: pointer;
    user-select: none;
  }
  .layer-chip.active {
    border-color: var(--border-strong);
    font-weight: 600;
  }
  .layer-dot {
    width: 9px;
    height: 9px;
    border-radius: 2px;
  }
  .add-item-box {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 14px;
    margin-bottom: 14px;
  }
  .inspector-split {
    display: grid;
    grid-template-columns: 1fr 310px;
    gap: 16px;
    align-items: start;
  }
  .blueprint-viewport {
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-sm);
    background: #FAF8F4;
    overflow: auto;
    max-height: 620px;
    padding: 10px;
  }
  .blueprint-viewport :global(g[data-item-id]) {
    cursor: pointer;
  }
  .blueprint-viewport :global(g[data-item-id]:hover rect) {
    stroke-width: 2.8;
  }
  .section-wrap {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px dashed var(--border-strong);
  }
  .side-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 14px;
  }
  .kv {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 4px 0;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 12px;
  }
  .reason-box {
    margin-top: 10px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 5px;
    padding: 9px;
    font-size: 12px;
  }
  .issue-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
  }
  .issue-list li {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  @media (max-width: 980px) {
    .inspector-split {
      grid-template-columns: 1fr;
    }
  }
</style>
