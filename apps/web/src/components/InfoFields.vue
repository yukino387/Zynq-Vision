<script setup lang="ts">
import { computed } from "vue";
import { chinese, displayName, fieldLabel } from "@vision/shared";
const props = defineProps<{ value: unknown; fields?: string[] }>();
const entries = computed(() => {
  const object =
    props.value && typeof props.value === "object"
      ? (props.value as Record<string, unknown>)
      : {};
  return (props.fields ?? Object.keys(object))
    .filter((key) => !props.fields || key in object)
    .map((key) => [key, object[key]] as const);
});
function format(value: unknown) {
  if (value === null || value === undefined) return "未上报";
  if (Array.isArray(value)) return value.length ? `${value.length} 项` : "暂无";
  if (typeof value === "object") return "已记录";
  return displayName(chinese(value));
}
</script>
<template>
  <dl class="key-values detail-fields">
    <template v-for="[key, item] in entries" :key="key"
      ><dt>{{ fieldLabel(key) }}</dt>
      <dd>{{ format(item) }}</dd></template
    >
  </dl>
</template>
