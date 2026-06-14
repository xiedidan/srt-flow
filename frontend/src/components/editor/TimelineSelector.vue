<script setup>
/**
 * Timeline Selector Component
 * Visual timeline for selecting clip range or adding split points
 */
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  duration: {
    type: Number,
    required: true
  },
  currentTime: {
    type: Number,
    default: 0
  },
  // For clip mode
  startTime: {
    type: Number,
    default: 0
  },
  endTime: {
    type: Number,
    default: null
  },
  // For split mode
  splitPoints: {
    type: Array,
    default: () => []
  },
  mode: {
    type: String,
    default: 'clip' // 'clip' or 'split'
  },
  readonly: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:startTime', 'update:endTime', 'update:splitPoints', 'seek'])

const timelineRef = ref(null)
const isDragging = ref(null) // 'start', 'end', 'range', or split point index

// Local state for dragging
const localStart = ref(props.startTime)
const localEnd = ref(props.endTime ?? props.duration)

watch(() => props.startTime, (v) => { localStart.value = v })
watch(() => props.endTime, (v) => { localEnd.value = v ?? props.duration })
watch(() => props.duration, (v) => { 
  if (localEnd.value > v) localEnd.value = v 
})

// Computed positions (percentage)
const startPercent = computed(() => (localStart.value / props.duration) * 100)
const endPercent = computed(() => (localEnd.value / props.duration) * 100)
const currentPercent = computed(() => (props.currentTime / props.duration) * 100)
const rangeWidth = computed(() => endPercent.value - startPercent.value)

// Format time display
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }
  return `${m}:${s.toString().padStart(2, '0')}`
}

// Get time from mouse position
function getTimeFromEvent(e) {
  if (!timelineRef.value) return 0
  const rect = timelineRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const percent = Math.max(0, Math.min(1, x / rect.width))
  return percent * props.duration
}

// Handle timeline click
function onTimelineClick(e) {
  if (props.readonly) return
  if (isDragging.value) return
  
  const time = getTimeFromEvent(e)
  
  if (props.mode === 'split') {
    // Add split point
    const newPoints = [...props.splitPoints, time].sort((a, b) => a - b)
    emit('update:splitPoints', newPoints)
  } else {
    // Seek to position
    emit('seek', time)
  }
}

// Start dragging handle
function startDrag(type, e) {
  if (props.readonly) return
  e.stopPropagation()
  isDragging.value = type
  
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e) {
  if (!isDragging.value) return
  
  const time = getTimeFromEvent(e)
  
  if (isDragging.value === 'start') {
    localStart.value = Math.min(time, localEnd.value - 1)
    localStart.value = Math.max(0, localStart.value)
  } else if (isDragging.value === 'end') {
    localEnd.value = Math.max(time, localStart.value + 1)
    localEnd.value = Math.min(props.duration, localEnd.value)
  } else if (typeof isDragging.value === 'number') {
    // Dragging a split point
    const idx = isDragging.value
    const newPoints = [...props.splitPoints]
    const minTime = idx > 0 ? newPoints[idx - 1] + 1 : 1
    const maxTime = idx < newPoints.length - 1 ? newPoints[idx + 1] - 1 : props.duration - 1
    newPoints[idx] = Math.max(minTime, Math.min(maxTime, time))
    emit('update:splitPoints', newPoints)
  }
}

function stopDrag() {
  if (isDragging.value === 'start' || isDragging.value === 'end') {
    emit('update:startTime', localStart.value)
    emit('update:endTime', localEnd.value)
  }
  isDragging.value = null
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// Remove split point
function removeSplitPoint(idx, e) {
  e.stopPropagation()
  const newPoints = props.splitPoints.filter((_, i) => i !== idx)
  emit('update:splitPoints', newPoints)
}

// Generate time markers
const timeMarkers = computed(() => {
  const markers = []
  const interval = props.duration > 600 ? 60 : props.duration > 120 ? 30 : 10
  for (let t = 0; t <= props.duration; t += interval) {
    markers.push({
      time: t,
      percent: (t / props.duration) * 100,
      label: formatTime(t)
    })
  }
  return markers
})
</script>

<template>
  <div class="timeline-selector" :class="{ readonly }">
    <!-- Time markers -->
    <div class="time-markers">
      <span 
        v-for="marker in timeMarkers" 
        :key="marker.time"
        class="marker"
        :style="{ left: marker.percent + '%' }"
      >
        {{ marker.label }}
      </span>
    </div>
    
    <!-- Timeline track -->
    <div 
      ref="timelineRef"
      class="timeline-track"
      @click="onTimelineClick"
    >
      <!-- Selected range (clip mode) -->
      <div 
        v-if="mode === 'clip'"
        class="selected-range"
        :style="{ 
          left: startPercent + '%', 
          width: rangeWidth + '%' 
        }"
      />
      
      <!-- Split points (split mode) -->
      <template v-if="mode === 'split'">
        <div 
          v-for="(point, idx) in splitPoints"
          :key="idx"
          class="split-point"
          :style="{ left: (point / duration) * 100 + '%' }"
          @mousedown="startDrag(idx, $event)"
        >
          <div class="split-line" />
          <button 
            v-if="!readonly"
            class="split-remove" 
            @click="removeSplitPoint(idx, $event)"
            title="移除切分点"
          >✕</button>
          <span class="split-label">{{ formatTime(point) }}</span>
        </div>
      </template>
      
      <!-- Current time indicator -->
      <div 
        class="current-indicator"
        :style="{ left: currentPercent + '%' }"
      />
      
      <!-- Drag handles (clip mode) -->
      <template v-if="mode === 'clip' && !readonly">
        <div 
          class="handle handle-start"
          :style="{ left: startPercent + '%' }"
          @mousedown="startDrag('start', $event)"
        >
          <span class="handle-time">{{ formatTime(localStart) }}</span>
        </div>
        <div 
          class="handle handle-end"
          :style="{ left: endPercent + '%' }"
          @mousedown="startDrag('end', $event)"
        >
          <span class="handle-time">{{ formatTime(localEnd) }}</span>
        </div>
      </template>
    </div>
    
    <!-- Info bar -->
    <div class="info-bar">
      <template v-if="mode === 'clip'">
        <span class="info-item">
          <span class="info-label">选中范围:</span>
          <span class="info-value">{{ formatTime(localStart) }} - {{ formatTime(localEnd) }}</span>
        </span>
        <span class="info-item">
          <span class="info-label">时长:</span>
          <span class="info-value">{{ formatTime(localEnd - localStart) }}</span>
        </span>
      </template>
      <template v-else>
        <span class="info-item">
          <span class="info-label">切分点:</span>
          <span class="info-value">{{ splitPoints.length }} 个</span>
        </span>
        <span class="info-item">
          <span class="info-label">片段数:</span>
          <span class="info-value">{{ splitPoints.length + 1 }} 段</span>
        </span>
      </template>
      <span class="info-item">
        <span class="info-label">总时长:</span>
        <span class="info-value">{{ formatTime(duration) }}</span>
      </span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.timeline-selector {
  user-select: none;
  
  &.readonly {
    pointer-events: none;
    opacity: 0.7;
  }
}

.time-markers {
  position: relative;
  height: 20px;
  margin-bottom: 4px;
  
  .marker {
    position: absolute;
    transform: translateX(-50%);
    font-size: 10px;
    color: var(--text-muted);
  }
}

.timeline-track {
  position: relative;
  height: 40px;
  background-color: var(--bg-primary);
  border-radius: 4px;
  cursor: pointer;
  overflow: visible;
}

.selected-range {
  position: absolute;
  top: 0;
  height: 100%;
  background-color: rgba(59, 130, 246, 0.3);
  border-left: 2px solid var(--accent-color);
  border-right: 2px solid var(--accent-color);
}

.current-indicator {
  position: absolute;
  top: 0;
  width: 2px;
  height: 100%;
  background-color: #ef4444;
  transform: translateX(-50%);
  pointer-events: none;
  z-index: 5;
}

.handle {
  position: absolute;
  top: -4px;
  width: 12px;
  height: 48px;
  background-color: var(--accent-color);
  border-radius: 3px;
  cursor: ew-resize;
  transform: translateX(-50%);
  z-index: 10;
  
  &:hover {
    background-color: var(--accent-hover);
  }
  
  .handle-time {
    position: absolute;
    top: -20px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 11px;
    color: var(--text-primary);
    white-space: nowrap;
    background-color: var(--bg-secondary);
    padding: 2px 6px;
    border-radius: 3px;
  }
}

.split-point {
  position: absolute;
  top: 0;
  height: 100%;
  transform: translateX(-50%);
  z-index: 8;
  cursor: ew-resize;
  
  .split-line {
    width: 3px;
    height: 100%;
    background-color: #f59e0b;
  }
  
  .split-remove {
    position: absolute;
    top: -18px;
    left: 50%;
    transform: translateX(-50%);
    width: 16px;
    height: 16px;
    background-color: #ef4444;
    color: white;
    border: none;
    border-radius: 50%;
    font-size: 10px;
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    line-height: 1;
  }
  
  .split-label {
    position: absolute;
    bottom: -18px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 10px;
    color: #f59e0b;
    white-space: nowrap;
  }
  
  &:hover .split-remove {
    display: flex;
  }
}

.info-bar {
  display: flex;
  gap: 24px;
  margin-top: 12px;
  padding: 8px 12px;
  background-color: var(--bg-primary);
  border-radius: 6px;
}

.info-item {
  display: flex;
  gap: 6px;
  font-size: 13px;
}

.info-label {
  color: var(--text-secondary);
}

.info-value {
  color: var(--text-primary);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
</style>
