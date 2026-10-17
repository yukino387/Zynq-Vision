import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { Role } from "@vision/contracts";
import { api, post, RequestError } from "../api";
export const useAuthStore = defineStore("auth", () => {
  const user = ref<{ id: string; name: string; role: Role } | null>(null),
    ready = ref(false);
  const role = computed(() => user.value?.role ?? null);
  const engineer = computed(
    () => user.value?.role === "ADMIN" || user.value?.role === "ENGINEER",
  );
  const admin = computed(() => user.value?.role === "ADMIN");
  let pending: Promise<void> | null = null;
  /** 记忆化：路由守卫和 App 挂载可能同时触发，恢复只应跑一次。 */
  function restore() {
    return (pending ??= doRestore());
  }
  async function doRestore() {
    try {
      if (sessionStorage.getItem("vision.token"))
        user.value = await api("/auth/me");
    } catch (error) {
      if (error instanceof RequestError && error.status === 401) {
        sessionStorage.removeItem("vision.token");
        sessionStorage.removeItem("vision.user");
      } else {
        const cached = sessionStorage.getItem("vision.user");
        if (cached) user.value = JSON.parse(cached) as typeof user.value;
      }
    } finally {
      ready.value = true;
    }
  }
  async function login(username: string, password: string) {
    const result = await post<{
      token: string;
      user: NonNullable<typeof user.value>;
    }>("/auth/login", { username, password });
    sessionStorage.setItem("vision.token", result.token);
    user.value = result.user;
    sessionStorage.setItem("vision.user", JSON.stringify(result.user));
  }
  async function register(body: {
    code: string;
    name: string;
    username: string;
    password: string;
  }) {
    const result = await post<{
      token: string;
      user: NonNullable<typeof user.value>;
    }>("/auth/register", body);
    sessionStorage.setItem("vision.token", result.token);
    sessionStorage.setItem("vision.user", JSON.stringify(result.user));
    user.value = result.user;
  }
  function logout() {
    sessionStorage.removeItem("vision.user");
    sessionStorage.removeItem("vision.token");
    user.value = null;
  }
  return {
    user,
    role,
    ready,
    admin,
    engineer,
    restore,
    login,
    register,
    logout,
  };
});
