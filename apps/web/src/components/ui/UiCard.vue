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
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  background: var(--surface);
  background-image: none;
  border: 1px solid var(--line);
  border-radius: 2px;
  box-shadow: none;
  transition: border-color 160ms ease;
}

.ui-card::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  width: 9px;
  height: 9px;
  border-top: 1px solid var(--ink);
  border-left: 1px solid var(--ink);
  opacity: 0.4;
  pointer-events: none;
}

.variant-flat {
  border-color: transparent;
  background: var(--surface-2);
}
.variant-bordered {
  border-color: var(--line-strong);
}
.variant-accent {
  border-left: 2px solid var(--forest);
}

.is-hoverable:hover {
  border-color: var(--line-strong);
}
.is-hoverable:hover::before {
  border-color: var(--forest);
  opacity: 1;
}

.padding-none .ui-card-body {
  padding: 0;
}
.padding-none .ui-card-header,
.padding-none .ui-card-footer {
  padding: 12px 16px;
}

.padding-sm .ui-card-header {
  padding: 9px 13px 7px;
}
.padding-sm .ui-card-body {
  padding: 10px 13px;
}
.padding-sm .ui-card-footer {
  padding: 8px 13px;
}

.padding-md .ui-card-header {
  padding: 13px 17px 10px;
}
.padding-md .ui-card-body {
  padding: 16px 17px;
}
.padding-md .ui-card-footer {
  padding: 11px 17px;
}

.padding-lg .ui-card-header {
  padding: 18px 22px 12px;
}
.padding-lg .ui-card-body {
  padding: 22px 22px;
}
.padding-lg .ui-card-footer {
  padding: 14px 22px;
}

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
  gap: 9px;
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
  font-family: var(--font);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--ink);
  line-height: 1.4;
}
.ui-card-subtitle {
  margin: 3px 0 0;
  font-size: 9.5px;
  letter-spacing: 0.03em;
  color: var(--muted);
  line-height: 1.5;
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
  background: transparent;
  font-size: 10px;
  color: var(--muted);
}
</style>