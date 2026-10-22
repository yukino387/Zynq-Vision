<script setup lang="ts">
import Icon from "../Icon.vue";

export interface UiCardProps {
  title?: string;
  subtitle?: string;
  icon?: string;
  variant?: "default" | "flat" | "bordered" | "accent";
  padding?: "none" | "sm" | "md" | "lg";
  hover?: boolean;
}

withDefaults(defineProps<UiCardProps>(), {
  variant: "default",
  padding: "md",
  hover: false,
});
</script>

<template>
  <section
    class="ui-card"
    :class="[
      `variant-${variant}`,
      `padding-${padding}`,
      { 'is-hoverable': hover },
    ]"
  >
    <header
      v-if="title || subtitle || icon || $slots.header || $slots.actions"
      class="ui-card-header"
    >
      <slot name="header">
        <div class="ui-card-title-group">
          <span v-if="icon" class="ui-card-icon">
            <Icon :name="icon" :size="18" />
          </span>
          <div class="ui-card-text">
            <h3 v-if="title" class="ui-card-title">
              <slot name="title">{{ title }}</slot>
            </h3>
            <p v-if="subtitle" class="ui-card-subtitle">{{ subtitle }}</p>
          </div>
        </div>
        <div v-if="$slots.actions" class="ui-card-actions">
          <slot name="actions" />
        </div>
      </slot>
    </header>

    <div class="ui-card-body">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="ui-card-footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.ui-card {
  position: relative;
  background: var(--surface);
  background-image: linear-gradient(
    180deg,
    var(--lui-surface-top, var(--surface)) 0%,
    var(--surface) 46%,
    var(--lui-surface-bottom, var(--surface)) 100%
  );
  border: 1px solid var(--line);
  border-radius: var(--radius, 8px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    var(--lui-shadow, 0 1px 3px rgba(0, 0, 0, 0.04));
  transition:
    border-color var(--lui-base, 240ms) var(--lui-ease, ease),
    box-shadow var(--lui-base, 240ms) var(--lui-ease, ease),
    transform var(--lui-base, 240ms) var(--lui-ease, ease);
}

.variant-default {
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    var(--lui-shadow, 0 1px 3px rgba(0, 0, 0, 0.04));
}

.variant-flat {
  border-color: transparent;
  background: var(--surface-2);
  background-image: none;
  box-shadow: inset 0 1px 0 var(--lui-rim, transparent);
}

.variant-bordered {
  border-color: var(--line-strong);
  box-shadow: inset 0 1px 0 var(--lui-rim, transparent);
}

.variant-accent {
  border-left: 4px solid var(--forest);
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    var(--lui-shadow, 0 2px 8px rgba(0, 0, 0, 0.05));
}

.is-hoverable:hover {
  border-color: var(--line-strong);
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    var(--lui-shadow-lift, 0 4px 12px rgba(0, 0, 0, 0.08));
  transform: translateY(-1px);
}

/* 内边距体系 */
.padding-none .ui-card-body {
  padding: 0;
}
.padding-none .ui-card-header,
.padding-none .ui-card-footer {
  padding: 12px 16px;
}

.padding-sm .ui-card-header {
  padding: 10px 14px 6px;
}
.padding-sm .ui-card-body {
  padding: 10px 14px;
}
.padding-sm .ui-card-footer {
  padding: 8px 14px;
}

.padding-md .ui-card-header {
  padding: 16px 20px 8px;
}
.padding-md .ui-card-body {
  padding: 16px 20px;
}
.padding-md .ui-card-footer {
  padding: 12px 20px;
}

.padding-lg .ui-card-header {
  padding: 24px 28px 12px;
}
.padding-lg .ui-card-body {
  padding: 24px 28px;
}
.padding-lg .ui-card-footer {
  padding: 16px 28px;
}

/* 头部排版 */
.ui-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid transparent;
}

.ui-card-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ui-card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--forest);
  flex-shrink: 0;
}

.ui-card-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.ui-card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
}

.ui-card-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.4;
}

.ui-card-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ui-card-body {
  flex: 1;
  min-width: 0;
}

.ui-card-footer {
  border-top: 1px solid var(--line);
  background: var(--surface-2);
  border-bottom-left-radius: inherit;
  border-bottom-right-radius: inherit;
  font-size: 13px;
  color: var(--ink-2);
}
</style>
