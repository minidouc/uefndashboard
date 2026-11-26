<script>
  import { onMount } from 'svelte';
  import { rpc, connectEventStream, onServerEvent, onWsStatus } from './lib/rpc.js';
  import { applyThemeFromConfig, THEME_PRESETS } from './lib/theme.js';
  import { attachShortcuts } from './lib/shortcuts.js';

  import PipelineView from './components/PipelineView.svelte';
  import PlanInspector from './components/PlanInspector.svelte';
  import OutboxView from './components/OutboxView.svelte';
  import MemoryLibrary from './components/MemoryLibrary.svelte';
  import ProofsCompatView from './components/ProofsCompatView.svelte';
  import AgentConsole from './components/AgentConsole.svelte';
  import SettingsView from './components/SettingsView.svelte';

  let activeView = $state('pipeline');
  let wsStatus = $state('connecting');
  let health = $state(null);
  let fullConfig = $state(null);
  let projects = $state([]);
  let activeProject = $state('neo-kyoto-slice');
  let pipelineData = $state(null);
  let pendingApprovals = $state([]);
  let toast = $state(null);
  let toastTimer = null;

  const NAV = [
    { id: 'pipeline', label: 'Pipeline (0 → 9)', shortcutKey: 'nav_pipeline', group: 'Fabrication' },
    { id: 'plan', label: 'Plans 2D & Couches', shortcutKey: 'nav_plan', group: 'Fabrication' },
    { id: 'outbox', label: 'Dossier d\'envoi (Outbox)', shortcutKey: 'nav_outbox', group: 'Fabrication' },
    { id: 'memory', label: 'Mémoire & Bibliothèque', shortcutKey: 'nav_memory', group: 'Connaissance' },
    { id: 'proofs', label: 'Preuves & Compat PC', shortcutKey: 'nav_proofs', group: 'Connaissance' },
    { id: 'agent', label: 'Console Agent (Rust)', shortcutKey: 'nav_agent', group: 'Système' },
    { id: 'settings', label: 'Config TOML & MCP', shortcutKey: 'nav_settings', group: 'Système' }
  ];

  function notify(message, isError = false) {
    toast = { message, isError };
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast = null;
    }, 4200);
  }

  async function refreshAll() {
    try {
      const [h, cfg, prj, pipe, pend] = await Promise.all([
        rpc('system.health'),
        rpc('config.get'),
        rpc('project.list'),
        rpc('pipeline.state'),
        rpc('permissions.pending')
      ]);
      health = h;
      fullConfig = cfg;
      projects = prj.projects || [];
      activeProject = prj.active || h.active_project;
      pipelineData = pipe;
      pendingApprovals = pend.pending || [];
      if (cfg?.app?.theme) {
        applyThemeFromConfig(cfg.app.theme);
      }
    } catch (e) {
      notify(`Connexion au cœur Rust : ${e.message}`, true);
    }
  }

  async function switchProject(slug) {
    try {
      await rpc('project.select', { slug });
      activeProject = slug;
      notify(`Projet actif : ${slug}`);
      await refreshAll();
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function resolveApproval(approvalId, approved) {
    try {
      await rpc('permissions.resolve', { approval_id: approvalId, approved });
      pendingApprovals = pendingApprovals.filter((a) => a.approval_id !== approvalId);
      notify(approved ? 'Permission accordée.' : 'Permission refusée.');
    } catch (e) {
      notify(e.message, true);
    }
  }

  async function quickToggleTheme() {
    if (!fullConfig?.app) return;
    const nextPreset = fullConfig.app.theme.preset === 'ardoise-studio' ? 'atelier-clair' : 'ardoise-studio';
    const nextApp = structuredClone(fullConfig.app);
    nextApp.theme.preset = nextPreset;
    nextApp.theme.vars = { ...THEME_PRESETS[nextPreset].vars };
    applyThemeFromConfig(nextApp.theme);
    await rpc('config.update_app', nextApp);
    fullConfig = { ...fullConfig, app: nextApp };
  }

  onMount(() => {
    refreshAll();
    connectEventStream();

    const offStatus = onWsStatus((st) => {
      wsStatus = st;
    });

    const offEvents = onServerEvent((ev) => {
      if (ev.type === 'permission.requested' && ev.payload) {
        pendingApprovals = [...pendingApprovals, ev.payload];
        notify(`Approbation requise : ${ev.payload.action} (${ev.payload.target})`);
      } else if (ev.type === 'permission.resolved' && ev.payload) {
        pendingApprovals = pendingApprovals.filter((a) => a.approval_id !== ev.payload.approval_id);
      } else if (['state.changed', 'gate.approved', 'validation.completed', 'config.updated'].includes(ev.type)) {
        refreshAll();
      }
    });

    const offKeys = attachShortcuts(
      () => fullConfig?.app?.shortcuts,
      {
        nav_pipeline: () => (activeView = 'pipeline'),
        nav_plan: () => (activeView = 'plan'),
        nav_outbox: () => (activeView = 'outbox'),
        nav_memory: () => (activeView = 'memory'),
        nav_proofs: () => (activeView = 'proofs'),
        nav_agent: () => (activeView = 'agent'),
        nav_settings: () => (activeView = 'settings'),
        toggle_theme: () => quickToggleTheme(),
        run_validators: async () => {
          activeView = 'proofs';
          try {
            const r = await rpc('validators.run', { golden_only: false });
            notify(`Validateurs : ${r.verdict}`, r.verdict !== 'PASS');
            refreshAll();
          } catch (e) {
            notify(e.message, true);
          }
        }
      }
    );

    return () => {
      offStatus();
      offEvents();
      offKeys();
    };
  });

  let currentNavLabel = $derived(NAV.find((n) => n.id === activeView)?.label || 'Map Creator');
</script>

<div class="shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-title">
        <span>Map Creator</span>
        <span class="brand-tag">v3 · RUST</span>
      </div>
      <div class="brand-sub">Harnais &amp; Studio UEFN</div>
    </div>

    <div class="nav-group-label">Fabrication</div>
    {#each NAV.filter((n) => n.group === 'Fabrication') as item}
      <button
        id="nav-{item.id}"
        class="nav-btn"
        class:active={activeView === item.id}
        onclick={() => (activeView = item.id)}
      >
        <span>{item.label}</span>
        <span class="nav-kbd">{fullConfig?.app?.shortcuts?.[item.shortcutKey] || ''}</span>
      </button>
    {/each}

    <div class="nav-group-label">Connaissance &amp; Preuves</div>
    {#each NAV.filter((n) => n.group === 'Connaissance') as item}
      <button
        id="nav-{item.id}"
        class="nav-btn"
        class:active={activeView === item.id}
        onclick={() => (activeView = item.id)}
      >
        <span>{item.label}</span>
        <span class="nav-kbd">{fullConfig?.app?.shortcuts?.[item.shortcutKey] || ''}</span>
      </button>
    {/each}

    <div class="nav-group-label">Cœur &amp; Extensions</div>
    {#each NAV.filter((n) => n.group === 'Système') as item}
      <button
        id="nav-{item.id}"
        class="nav-btn"
        class:active={activeView === item.id}
        onclick={() => (activeView = item.id)}
      >
        <span>{item.label}</span>
        <span class="nav-kbd">{fullConfig?.app?.shortcuts?.[item.shortcutKey] || ''}</span>
      </button>
    {/each}

    <div class="sidebar-footer">
      <label for="sidebar-project-select" style="font-size:11px; text-transform:uppercase; letter-spacing:0.06em;">
        Projet actif
      </label>
      <select
        id="sidebar-project-select"
        class="project-select mono"
        value={activeProject}
        onchange={(e) => switchProject(e.target.value)}
      >
        {#each projects as slug}
          <option value={slug}>{slug}</option>
        {/each}
      </select>
      <div style="margin-top:10px; display:flex; justify-content:space-between; align-items:center;">
        <span>App Server WS</span>
        <span class="badge {wsStatus === 'connected' ? 'pass' : 'warn'}">{wsStatus}</span>
      </div>
    </div>
  </aside>

  <div class="main-area">
    <header class="topbar">
      <div class="topbar-left">
        <h1>{currentNavLabel}</h1>
        {#if pipelineData?.state}
          <span class="badge accent">{pipelineData.state.phase}</span>
        {/if}
      </div>
      <div class="topbar-meta">
        {#if health}
          <span class="badge {health.manifest_integrity === 'OK' ? 'pass' : 'fail'}">
            MANIFEST: {health.manifest_integrity}
          </span>
          <span class="badge">UEFN {health.uefn_version}</span>
          <span class="badge">MCP: {health.mcp_mode}</span>
          <span class="badge">State: {health.state_bytes} o</span>
        {/if}
        <button id="btn-theme-toggle" class="btn btn-sm" onclick={quickToggleTheme}>
          Thème
        </button>
      </div>
    </header>

    {#if pendingApprovals.length > 0}
      <div class="approval-bar" role="alert">
        <div>
          <strong>{pendingApprovals.length} permission(s) en attente d'approbation humaine :</strong>
          <span class="mono">{pendingApprovals[0].action}</span> sur <span class="mono">{pendingApprovals[0].target}</span>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-pass btn-sm" onclick={() => resolveApproval(pendingApprovals[0].approval_id, true)}>
            Autoriser
          </button>
          <button class="btn btn-danger btn-sm" onclick={() => resolveApproval(pendingApprovals[0].approval_id, false)}>
            Refuser
          </button>
        </div>
      </div>
    {/if}

    <main class="content">
      {#if activeView === 'pipeline'}
        <PipelineView {pipelineData} onRefresh={refreshAll} {notify} />
      {:else if activeView === 'plan'}
        <PlanInspector {activeProject} {notify} />
      {:else if activeView === 'outbox'}
        <OutboxView {activeProject} {notify} />
      {:else if activeView === 'memory'}
        <MemoryLibrary {pipelineData} {notify} />
      {:else if activeView === 'proofs'}
        <ProofsCompatView {activeProject} {notify} />
      {:else if activeView === 'agent'}
        <AgentConsole
          appConfig={fullConfig?.app}
          {pendingApprovals}
          onResolveApproval={resolveApproval}
          {notify}
        />
      {:else if activeView === 'settings'}
        <SettingsView {fullConfig} onConfigSaved={refreshAll} {notify} />
      {/if}
    </main>
  </div>
</div>

{#if toast}
  <div class="toast" class:error={toast.isError} role="status">{toast.message}</div>
{/if}
