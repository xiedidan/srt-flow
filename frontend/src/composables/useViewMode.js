/**
 * Composable for persisting list view mode (card/list) to localStorage
 * Each page has its own independent view mode setting
 */
import { ref, watch } from 'vue'

const STORAGE_KEY_PREFIX = 'srtflow_viewmode_'

/**
 * @param {string} pageKey - Unique key for the page (e.g., 'videos', 'asr', 'translate')
 * @param {string} defaultMode - Default view mode ('card' or 'list' or 'grid')
 * @returns {{ viewMode: Ref<string> }}
 */
export function useViewMode(pageKey, defaultMode = 'card') {
  const storageKey = STORAGE_KEY_PREFIX + pageKey
  
  // Load from localStorage or use default
  const savedMode = localStorage.getItem(storageKey)
  const viewMode = ref(savedMode || defaultMode)
  
  // Persist to localStorage when changed
  watch(viewMode, (newMode) => {
    localStorage.setItem(storageKey, newMode)
  })
  
  return { viewMode }
}
