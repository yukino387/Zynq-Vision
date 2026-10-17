import "vue";
declare module "@vue/runtime-core" {
  interface ComponentCustomProperties {
    uni: typeof uni;
  }
}
