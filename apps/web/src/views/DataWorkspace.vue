<script setup lang="ts">
import { useRoute } from "vue-router";
import Data from "./Data.vue";
import Models from "./Models.vue";
const route = useRoute();
</script>

<template>
  <Models
    v-if="route.params.tab === 'training' || route.params.tab === 'registry'"
  />
  <Data v-else />
</template>
