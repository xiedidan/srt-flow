<script setup>
/**
 * Pagination component
 */
import { computed } from 'vue'

const props = defineProps({
  page: {
    type: Number,
    default: 1
  },
  totalPages: {
    type: Number,
    default: 1
  },
  total: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['change'])

const pages = computed(() => {
  const result = []
  const current = props.page
  const total = props.totalPages
  
  if (total <= 7) {
    for (let i = 1; i <= total; i++) result.push(i)
  } else {
    result.push(1)
    if (current > 3) result.push('...')
    
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    
    for (let i = start; i <= end; i++) result.push(i)
    
    if (current < total - 2) result.push('...')
    result.push(total)
  }
  
  return result
})

function goToPage(p) {
  if (p !== '...' && p !== props.page && p >= 1 && p <= props.totalPages) {
    emit('change', p)
  }
}
</script>

<template>
  <div v-if="totalPages > 1" class="pagination">
    <button 
      class="page-btn" 
      :disabled="page <= 1"
      @click="goToPage(page - 1)"
    >
      ‹
    </button>
    
    <button
      v-for="(p, idx) in pages"
      :key="idx"
      class="page-btn"
      :class="{ active: p === page, ellipsis: p === '...' }"
      :disabled="p === '...'"
      @click="goToPage(p)"
    >
      {{ p }}
    </button>
    
    <button 
      class="page-btn" 
      :disabled="page >= totalPages"
      @click="goToPage(page + 1)"
    >
      ›
    </button>
    
    <span class="page-info">共 {{ total }} 条</span>
  </div>
</template>

<style lang="scss" scoped>
.pagination {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }
  
  &.active {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
  
  &.ellipsis {
    border: none;
    background: none;
    cursor: default;
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.page-info {
  margin-left: 12px;
  font-size: 13px;
  color: var(--text-muted);
}
</style>
