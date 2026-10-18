<script setup lang="ts">
import { computed } from "vue";

/** 统一的内联图标：不引图表/图标库，描边跟随 currentColor。 */
const paths: Record<string, string[]> = {
  dashboard: [
    "M3 3h7v7H3z",
    "M14 3h7v11h-7z",
    "M3 14h7v7H3z",
    "M14 18h7v3h-7z",
  ],
  clipboard: ["M9 4H5v17h14V4h-4", "M9 2h6v5H9z", "M8 12h8", "M8 16h5"],
  layers: ["M12 3L2 8l10 5 10-5z", "M2 12l10 5 10-5", "M2 16l10 5 10-5"],
  scan: ["M8 3H3v5", "M16 3h5v5", "M21 16v5h-5", "M8 21H3v-5", "M9 9h6v6H9z"],
  search: ["M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z", "M16 16l5 5"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  logout: ["M9 4H4v16h5", "M9 12h12", "M16 7l5 5-5 5"],
  server: ["M4 4h16v6H4z", "M4 14h16v6H4z", "M7.5 7h.01", "M7.5 17h.01"],
  database: [
    "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3z",
    "M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6",
    "M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  ],
  storage: ["M3 6h18v5H3z", "M3 13h18v5H3z", "M7 8.5h.01", "M7 15.5h.01"],
  network: [
    "M5 12.55a11 11 0 0 1 14 0",
    "M8.5 16.1a6 6 0 0 1 7 0",
    "M12 20h.01",
    "M2 8.8a16 16 0 0 1 20 0",
  ],
  jobs: [
    "M8 6h13",
    "M8 12h13",
    "M8 18h13",
    "M3 6h.01",
    "M3 12h.01",
    "M3 18h.01",
  ],
  audit: [
    "M12 3l8 3v6c0 4.5-3.4 7.7-8 9-4.6-1.3-8-4.5-8-9V6z",
    "M9 12l2 2 4-4",
  ],
  pairing: [
    "M4 4h6v6H4z",
    "M14 4h6v6h-6z",
    "M4 14h6v6H4z",
    "M14 14h2v2h-2z",
    "M18 18h2v2h-2z",
  ],
  refresh: ["M20 11a8 8 0 1 0-2.3 6.3", "M20 4v7h-7"],
  device: [
    "M7 7h10v10H7z",
    "M4 10h3",
    "M4 14h3",
    "M17 10h3",
    "M17 14h3",
    "M10 4v3",
    "M14 4v3",
    "M10 17v3",
    "M14 17v3",
  ],
  chart: ["M4 20V10", "M10 20V4", "M16 20v-7", "M2 20h20"],
  camera: [
    "M14.5 4l1.5 3H21a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h5l1.5-3z",
    "M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  ],
  play: ["M8 5l11 7-11 7z"],
  pause: ["M8 4v16", "M16 4v16"],
  activity: ["M2 12h4l3-8 4 16 3-8h6"],
  alert: ["M12 3l9 16H3z", "M12 9v4", "M12 17h.01"],
  check: ["M20 6L9 17l-5-5"],
  clock: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 7v5l3 2"],
  users: [
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2",
    "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8",
    "M22 21v-2a4 4 0 0 0-3-3.87",
    "M16 3.13a4 4 0 0 1 0 7.75",
  ],
  download: ["M12 3v12", "M7 10l5 5 5-5", "M5 21h14"],
  external: [
    "M14 3h7v7",
    "M10 14L21 3",
    "M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5",
  ],
  gauge: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 12l4-4"],
  timer: ["M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "M12 9v4l2 2"],
};

const props = withDefaults(
  defineProps<{ name: string; size?: number; stroke?: number }>(),
  { size: 18, stroke: 1.7 },
);
const shape = computed(() => paths[props.name] ?? paths.device!);
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(d, index) in shape" :key="index" :d="d" />
  </svg>
</template>

<style scoped>
.icon {
  display: inline-block;
  flex: none;
  vertical-align: -0.18em;
}
</style>
