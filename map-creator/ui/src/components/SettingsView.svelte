<script>
  import { rpc } from '../lib/rpc.js';
  import { THEME_PRESETS, applyThemeFromConfig } from '../lib/theme.js';

  let { fullConfig, onConfigSaved, notify } = $props();

  let subtab = $state('theme');
  let appDraft = $state(null);
  let mcpDraft = $state(null);
  let permDraft = $state(null);
  let saving = $state(false);
  let pingResult = $state({});

  // Add new MCP extension form
  let newMcpId = $state('');
  let newMcpLabel = $state('');
  let newMcpEndpoint = $state('http://127.0.0.1:8030/mcp');

  $effect(() => {
    if (fullConfig && !appDraft) {
      appDraft = structuredClone(fullConfig.app);
      mcpDraft = structuredClone(fullConfig.mcp);
      permDraft = structuredClone(fullConfig.permissions);
    }
  });

  function applyPreset(presetId) {
    const preset = THEME_PRESETS[presetId];
    if (!preset || !appDraft) return;
    appDraft.theme.preset = presetId;
    appDraft.theme.vars = { ...preset.vars };
    applyThemeFromConfig(appDraft.theme);
  }

  function updateCssVar(key, val) {
    appDraft.theme.vars[key] = val;
    applyThemeFromConfig(appDraft.theme);
  }

  function toggleTool(toolName) {
    const set = new Set(appDraft.tools.enabled);
    if (set.has(toolName)) set.delete(toolName);
    else set.add(toolName);
    appDraft.tools.enabled = [...set];
  }

  async function saveApp() {
    saving = true;
    try {
      await rpc('config.update_app', appDraft);
      applyThemeFromConfig(appDraft.theme);
      notify('config/app.toml enregistré et appliqué à chaud.');
      await onConfigSaved();
    } catch (e) {
      notify(e.message, true);
    } finally {
      saving = false;
    }
  }

  async function saveMcp() {
    saving = true;
    try {
      await rpc('config.update_mcp', mcpDraft);
      notify('config/mcp_servers.toml enregistré.');
      await onConfigSaved();
    } catch (e) {
      notify(e.message, true);
    } finally {
      saving = false;
    }
  }

  async function pingServer(name) {
    try {
      const r = await rpc('mcp.ping', { server: name });
      pingResult = { ...pingResult, [name]: r };
    } catch (e) {
      notify(e.message, true);
    }
  }

  function addMcpExtension(e) {
    e.preventDefault();
    const id = newMcpId.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    if (!id) return;
    mcpDraft.servers[id] = {
      label: newMcpLabel.trim() || id,
      enabled: true,
      transport: 'http',
      endpoint: newMcpEndpoint.trim(),
      timeout_secs: 60,
      cooldown_secs: 0,
      max_retries: 3,
      mode: 'simulator',
      command: null,
      args: [],
      allowed_read_tools: [],
      allowed_write_tools: [],
      forbidden_tools: []
    };
    newMcpId = '';
    newMcpLabel = '';
  }

  const ALL_TOOLS = [
    'read_file', 'write_file', 'list_dir', 'run_shell', 'state_show',
    'state_event', 'outbox_submit', 'outbox_status', 'plan_check',
    'library_search', 'validator_run', 'mcp_call'
  ];
</script>

{#if appDraft}
  <div class="panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">Configuration TOML, Thème CSS &amp; Extensions MCP</h2>
        <p class="panel-subtitle">Personnalisation complète persistée dans <code class="mono">config/app.toml</code> et <code class="mono">config/mcp_servers.toml</code>.</p>
      </div>
      <div style="display:flex; gap:6px; flex-wrap:wrap;">
        <button class="btn btn-sm {subtab === 'theme' ? 'btn-primary' : ''}" onclick={() => (subtab = 'theme')}>Thème &amp; Raccourcis</button>
        <button class="btn btn-sm {subtab === 'roles' ? 'btn-primary' : ''}" onclick={() => (subtab = 'roles')}>Rôles, Prompts &amp; Outils</button>
        <button class="btn btn-sm {subtab === 'mcp' ? 'btn-primary' : ''}" onclick={() => (subtab = 'mcp')}>Extensions MCP</button>
        <button class="btn btn-sm {subtab === 'perms' ? 'btn-primary' : ''}" onclick={() => (subtab = 'perms')}>Permissions (TOML)</button>
      </div>
    </div>

    {#if subtab === 'theme'}
      <div class="grid-2">
        <div>
          <h3 class="panel-title" style="margin-bottom:10px;">Thème &amp; Variables CSS</h3>
          <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
            {#each Object.entries(THEME_PRESETS) as [pid, preset]}
              <button
                id="btn-preset-{pid}"
                class="btn btn-sm {appDraft.theme.preset === pid ? 'btn-primary' : ''}"
                onclick={() => applyPreset(pid)}
              >{preset.label}</button>
            {/each}
          </div>

          <div class="color-grid">
            {#each ['bg_canvas', 'bg_surface', 'bg_sidebar', 'accent', 'status_pass', 'layer_a', 'layer_c', 'layer_d'] as k}
              <label class="color-item">
                <input
                  type="color"
                  value={appDraft.theme.vars[k]}
                  oninput={(e) => updateCssVar(k, e.target.value)}
                />
                <span class="mono" style="font-size:11px;">--{k.replace(/_/g, '-')}</span>
              </label>
            {/each}
          </div>
        </div>

        <div>
          <h3 class="panel-title" style="margin-bottom:10px;">Raccourcis clavier (<code class="mono">[shortcuts]</code>)</h3>
          <div class="grid-2">
            {#each Object.keys(appDraft.shortcuts) as sk}
              <div class="field">
                <label for="sc-{sk}">{sk}</label>
                <input id="sc-{sk}" class="input mono" bind:value={appDraft.shortcuts[sk]} />
              </div>
            {/each}
          </div>
        </div>
      </div>
      <div style="margin-top:14px;">
        <button id="btn-save-app-toml" class="btn btn-primary" onclick={saveApp} disabled={saving}>
          Enregistrer config/app.toml
        </button>
      </div>
    {:else if subtab === 'roles'}
      <div style="margin-bottom:16px;">
        <h3 class="panel-title" style="margin-bottom:8px;">Outils activés dans le cœur Rust</h3>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          {#each ALL_TOOLS as t}
            <label class="tool-toggle">
              <input type="checkbox" checked={appDraft.tools.enabled.includes(t)} onchange={() => toggleTool(t)} />
              <span class="mono">{t}</span>
            </label>
          {/each}
        </div>
      </div>

      <h3 class="panel-title" style="margin-bottom:8px;">Prompts système &amp; Modèles par rôle</h3>
      <div class="roles-grid">
        {#each Object.entries(appDraft.roles) as [rid, role]}
          <div class="role-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <strong>{role.label}</strong>
              <span class="badge">{role.tier}</span>
            </div>
            <div class="grid-2">
              <div class="field">
                <label for="rp-{rid}">Provider</label>
                <select id="rp-{rid}" class="select" bind:value={appDraft.roles[rid].provider}>
                  {#each Object.keys(appDraft.providers) as pk}
                    <option value={pk}>{pk}</option>
                  {/each}
                </select>
              </div>
              <div class="field">
                <label for="rm-{rid}">Modèle</label>
                <input id="rm-{rid}" class="input mono" bind:value={appDraft.roles[rid].model} />
              </div>
            </div>
            <div class="field">
              <label for="rs-{rid}">Prompt système</label>
              <textarea id="rs-{rid}" class="textarea" bind:value={appDraft.roles[rid].system_prompt}></textarea>
            </div>
          </div>
        {/each}
      </div>
      <div style="margin-top:14px;">
        <button class="btn btn-primary" onclick={saveApp} disabled={saving}>Enregistrer rôles &amp; outils</button>
      </div>
    {:else if subtab === 'mcp' && mcpDraft}
      <div class="table-wrap" style="margin-bottom:16px;">
        <table class="data-table">
          <thead><tr><th>Extension MCP</th><th>Transport &amp; Endpoint</th><th>Mode</th><th>Statut</th><th>Actions</th></tr></thead>
          <tbody>
            {#each Object.entries(mcpDraft.servers) as [sid, srv]}
              <tr>
                <td>
                  <strong>{srv.label}</strong>
                  <div class="mono" style="font-size:11px; color:var(--text-secondary);">{sid}</div>
                </td>
                <td class="mono" style="font-size:12px;">{srv.transport} · {srv.endpoint}</td>
                <td>
                  <select class="select" bind:value={mcpDraft.servers[sid].mode}>
                    <option value="simulator">simulator</option>
                    <option value="live">live</option>
                  </select>
                </td>
                <td>
                  <label style="display:flex; align-items:center; gap:6px;">
                    <input type="checkbox" bind:checked={mcpDraft.servers[sid].enabled} />
                    <span>{srv.enabled ? 'Actif' : 'Désactivé'}</span>
                  </label>
                </td>
                <td>
                  <button class="btn btn-sm" onclick={() => pingServer(sid)}>Ping</button>
                  {#if pingResult[sid]}
                    <span class="badge {pingResult[sid].online ? 'pass' : 'fail'}" style="margin-left:6px;">
                      {pingResult[sid].online ? 'ONLINE' : 'OFFLINE'}
                    </span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <form class="sub-box" onsubmit={addMcpExtension}>
        <strong>Brancher une nouvelle extension MCP (sans toucher au cœur Rust)</strong>
        <div class="grid-3" style="margin-top:8px;">
          <div class="field"><label for="nm-id">ID serveur</label><input id="nm-id" class="input mono" bind:value={newMcpId} placeholder="ex: blender_mcp" required /></div>
          <div class="field"><label for="nm-lbl">Nom affiché</label><input id="nm-lbl" class="input" bind:value={newMcpLabel} placeholder="Blender LOD Pipeline" required /></div>
          <div class="field"><label for="nm-ep">Endpoint HTTP MCP</label><input id="nm-ep" class="input mono" bind:value={newMcpEndpoint} required /></div>
        </div>
        <button type="submit" class="btn btn-sm">+ Ajouter à la liste</button>
      </form>

      <button id="btn-save-mcp" class="btn btn-primary" onclick={saveMcp} disabled={saving}>
        Enregistrer config/mcp_servers.toml
      </button>
    {:else if subtab === 'perms' && permDraft}
      <div class="grid-2">
        <div>
          <h3 class="panel-title" style="margin-bottom:8px;">Politique par défaut (allow / ask / deny)</h3>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Action</th><th>Décision</th></tr></thead>
              <tbody>
                {#each Object.entries(permDraft.defaults) as [act, dec]}
                  <tr>
                    <td class="mono">{act}</td>
                    <td><span class="badge {dec === 'allow' ? 'pass' : dec === 'ask' ? 'warn' : 'fail'}">{dec.toUpperCase()}</span></td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h3 class="panel-title" style="margin-bottom:8px;">Chemins protégés (DENY dur)</h3>
          <pre class="code-box">{JSON.stringify(permDraft.protected_paths, null, 2)}</pre>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .color-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .color-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 5px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
  }
  .tool-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 9px;
    border-radius: 5px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    font-size: 12px;
    cursor: pointer;
  }
  .roles-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .role-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
  }
  .sub-box {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
    margin-bottom: 12px;
  }
  @media (max-width: 980px) {
    .roles-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
