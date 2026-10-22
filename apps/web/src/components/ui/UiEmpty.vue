<script setup lang="ts">
import Icon from "../Icon.vue";

export interface UiEmptyProps {
  title?: string;
  description?: string;
  icon?: string;
}

withDefaults(defineProps<UiEmptyProps>(), {
  title: "暂无数据",
  description: "",
  icon: "dashboard",
});
</script>

<template>
  <div class="ui-empty">
    <div class="ui-empty-icon" aria-hidden="true">
      <slot name="icon">
        <Icon :name="icon" :size="32" />
      </slot>
    </div>

    <h4 class="ui-empty-title">{{ title }}</h4>
    <p v-if="description || $slots.default" class="ui-empty-desc">
      <slot>{{ description }}</slot>
    </p>

    <div v-if="$slots.actions" class="ui-empty-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.ui-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
  color: var(--muted);
  box-sizing: border-box;
}

.ui-empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--muted);
  margin-bottom: 14px;
  border: 1px dashed var(--line-strong);
}

.ui-empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.ui-empty-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--muted);
  max-width: 380px;
  line-height: 1.5;
}

.ui-empty-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
}
</style>
