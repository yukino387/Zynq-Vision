<script setup lang="ts">
defineProps<{
  field: string;
  label: string;
  active: string;
  order: "asc" | "desc";
}>();
defineEmits<{ sort: [field: string] }>();
</script>
<template>
  <th
    :aria-sort="
      active === field ? (order === 'asc' ? 'ascending' : 'descending') : 'none'
    "
  >
    <button type="button" class="sort" @click="$emit('sort', field)">
      {{ label
      }}<span class="mark" :class="{ on: active === field }">{{
        active === field ? (order === "asc" ? "↑" : "↓") : "↕"
      }}</span>
    </button>
  </th>
</template>
