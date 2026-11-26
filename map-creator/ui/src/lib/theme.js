// Hydrates CSS custom properties live from config/app.toml + provides curated architectural presets

export const THEME_PRESETS = {
  'atelier-clair': {
    label: 'Atelier Clair (Papier & Terre Cuite)',
    vars: {
      bg_canvas: '#F5F3EE',
      bg_surface: '#FFFFFF',
      bg_elevated: '#EFECE4',
      bg_sidebar: '#1A1C1E',
      text_primary: '#17191C',
      text_secondary: '#5B6068',
      text_sidebar: '#ECEAE4',
      text_sidebar_muted: '#9BA1A8',
      border_subtle: '#DDD8CC',
      border_strong: '#C5BEB0',
      accent: '#C84B28',
      accent_hover: '#A93B1D',
      accent_soft: '#FBECE7',
      status_pass: '#1D7F54',
      status_pass_bg: '#E5F5ED',
      status_warn: '#B77213',
      status_warn_bg: '#FDF3E2',
      status_fail: '#C23630',
      status_fail_bg: '#FCE9E8',
      layer_a: '#1E6091',
      layer_b: '#6C757D',
      layer_c: '#D97706',
      layer_d: '#0F766E'
    }
  },
  'ardoise-studio': {
    label: 'Ardoise Studio (Charbon & Ambre)',
    vars: {
      bg_canvas: '#141517',
      bg_surface: '#1C1E21',
      bg_elevated: '#24272B',
      bg_sidebar: '#0F1012',
      text_primary: '#F1EFEA',
      text_secondary: '#9CA3AF',
      text_sidebar: '#F1EFEA',
      text_sidebar_muted: '#858B94',
      border_subtle: '#2C3036',
      border_strong: '#3D424A',
      accent: '#E07A3B',
      accent_hover: '#C86529',
      accent_soft: '#332219',
      status_pass: '#34B37A',
      status_pass_bg: '#132B21',
      status_warn: '#E3A038',
      status_warn_bg: '#2E2312',
      status_fail: '#E05A52',
      status_fail_bg: '#321817',
      layer_a: '#5AA9E6',
      layer_b: '#9BA3AD',
      layer_c: '#F0A202',
      layer_d: '#2EC4B6'
    }
  },
  'blueprint-encre': {
    label: 'Blueprint Encre (Acier & Cobalt)',
    vars: {
      bg_canvas: '#EFF3F8',
      bg_surface: '#FFFFFF',
      bg_elevated: '#E3EAF2',
      bg_sidebar: '#132238',
      text_primary: '#102033',
      text_secondary: '#4B5D73',
      text_sidebar: '#EAF0F7',
      text_sidebar_muted: '#8DA4BE',
      border_subtle: '#D0DCE8',
      border_strong: '#AEC1D6',
      accent: '#1B5E9C',
      accent_hover: '#14497A',
      accent_soft: '#E1EEF9',
      status_pass: '#177A56',
      status_pass_bg: '#E1F5ED',
      status_warn: '#B56E11',
      status_warn_bg: '#FEF3E0',
      status_fail: '#BD3434',
      status_fail_bg: '#FCE8E8',
      layer_a: '#1B5E9C',
      layer_b: '#64748B',
      layer_c: '#C97A10',
      layer_d: '#0D7A6E'
    }
  }
};

export function applyThemeFromConfig(themeCfg) {
  if (!themeCfg || typeof document === 'undefined') return;
  const root = document.documentElement;
  if (themeCfg.font_sans) root.style.setProperty('--font-sans', themeCfg.font_sans);
  if (themeCfg.font_mono) root.style.setProperty('--font-mono', themeCfg.font_mono);
  if (themeCfg.radius_sm) root.style.setProperty('--radius-sm', themeCfg.radius_sm);
  if (themeCfg.radius_md) root.style.setProperty('--radius-md', themeCfg.radius_md);
  if (themeCfg.vars) {
    for (const [k, v] of Object.entries(themeCfg.vars)) {
      const cssName = `--${k.replace(/_/g, '-')}`;
      root.style.setProperty(cssName, v);
    }
  }
}
