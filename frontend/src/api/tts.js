/**
 * TTS API module
 * Provides functions for TTS-related operations including sentence merge preview
 */
import api from './index'

/**
 * Preview sentence merge results
 * @param {string} videoId - Video UUID
 * @param {string} [subtitlePath] - Optional subtitle path override
 * @returns {Promise<Object>} Merge preview result with original and merged entries
 */
export async function previewSentenceMerge(videoId, subtitlePath = null) {
  const { data } = await api.post('/tts/sentence-merge/preview', {
    video_id: videoId,
    subtitle_path: subtitlePath,
  })
  return data
}

/**
 * Adjust merged entries manually
 * @param {Array} entries - Current merged entries
 * @param {string} action - Action: merge, split, edit
 * @param {number} targetIndex - Index of target entry
 * @param {Object} options - Additional options based on action
 * @returns {Promise<Object>} Adjusted entries
 */
export async function adjustMergedEntries(entries, action, targetIndex, options = {}) {
  const { data } = await api.post('/tts/sentence-merge/adjust', {
    entries,
    action,
    target_index: targetIndex,
    merge_with_index: options.mergeWithIndex,
    new_text: options.newText,
    split_at_char: options.splitAtChar,
  })
  return data
}

export default {
  previewSentenceMerge,
  adjustMergedEntries,
}
