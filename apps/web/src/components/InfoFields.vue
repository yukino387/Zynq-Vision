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
function format(value: unknown, key: string) {
  if (value === null || value === undefined || value === "")
    return key === "error" ? "无错误" : "未提供";
  if (Array.isArray(value))
    return value.length
      ? value.every((item) => item === null || typeof item !== "object")
        ? value.map(chinese).join("、")
        : `共 ${value.length} 项`
      : "无";
  if (typeof value === "object") return "已记录";
  return displayName(chinese(value));
}
</script>
<template>
  <dl class="key-values detail-fields">
    <template v-for="[key, item] in entries" :key="key"
      ><dt>{{ fieldLabel(key) }}</dt>
      <dd>
        <details
          v-if="item && typeof item === 'object' && !Array.isArray(item)"
        >
          <summary>查看参数</summary>
          <InfoFields :value="item" />
        </details>
        <template v-else>{{ format(item, key) }}</template>
      </dd></template
    >
  </dl>
</template>
