<script setup lang="ts">
import { onMounted, ref } from "vue";
import type { Role } from "@vision/contracts";
import { chinese } from "@vision/shared";
import { api, post, errorText } from "../api";
import { useAuthStore } from "../stores/auth";
import { useNotificationStore } from "../stores/notifications";
import AsyncState from "../components/AsyncState.vue";
import Icon from "../components/Icon.vue";
interface Profile {
  id: string;
  name: string;
  username: string;
  role: Role;
  createdAt: string;
}
const auth = useAuthStore(),
  notices = useNotificationStore();
const profile = ref<Profile | null>(null),
  name = ref(""),
  loading = ref(false),
  loadError = ref("");
const saving = ref(false),
  changing = ref(false),
  showPasswords = ref(false);
const currentPassword = ref(""),
  newPassword = ref(""),
  confirmation = ref(""),
  passwordError = ref("");
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    profile.value = await api<Profile>("/auth/profile");
    name.value = profile.value.name;
  } catch (error) {
    loadError.value = errorText(error);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
async function saveProfile() {
  saving.value = true;
  try {
    const result = await auth.updateProfile(name.value.trim());
    name.value = result.name;
    if (profile.value) profile.value.name = result.name;
    notices.add("账号资料已保存");
  } catch (error) {
    notices.error(error);
  } finally {
    saving.value = false;
  }
}
async function changePassword() {
  passwordError.value = "";
  if (newPassword.value !== confirmation.value) {
    passwordError.value = "两次输入的新密码不一致";
    return;
  }
  if (currentPassword.value === newPassword.value) {
    passwordError.value = "新密码不能与当前密码相同";
    return;
  }
  if (new TextEncoder().encode(newPassword.value).length > 72) {
    passwordError.value = "新密码过长，请减少字符后重试";
    return;
  }
  changing.value = true;
  try {
    await post("/auth/password", {
      currentPassword: currentPassword.value,
      newPassword: newPassword.value,
    });
    currentPassword.value = newPassword.value = confirmation.value = "";
    auth.notice = "密码已更新，请使用新密码重新登录。";
    auth.logout();
  } catch (error) {
    passwordError.value = errorText(error);
  } finally {
    changing.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>账号设置</h1>
      <p>管理个人资料和登录密码。</p>
    </div>
    <RouterLink v-if="auth.admin" class="button-link" to="/access/users"
      >管理所有账号 <span aria-hidden="true">→</span></RouterLink
    >
  </div>
  <AsyncState :loading="loading" :error="loadError" @retry="load">
    <div v-if="profile" class="account-grid">
      <section class="panel account-card">
        <header>
          <span class="account-icon"><Icon name="users" :size="22" /></span>
          <div>
            <h2>个人资料</h2>
            <p>姓名用于页面显示及操作记录。</p>
          </div>
        </header>
        <dl class="account-facts">
          <div>
            <dt>登录账号</dt>
            <dd>{{ profile.username }}</dd>
          </div>
          <div>
            <dt>当前角色</dt>
            <dd>{{ chinese(profile.role) }}</dd>
          </div>
          <div>
            <dt>加入时间</dt>
            <dd>{{ new Date(profile.createdAt).toLocaleDateString() }}</dd>
          </div>
        </dl>
        <form @submit.prevent="saveProfile">
          <label
            >姓名<input
              v-model="name"
              autocomplete="name"
              required
              maxlength="60"
              :disabled="saving"
          /></label>
          <div class="form-actions">
            <button
              class="primary"
              :disabled="saving || !name.trim() || name.trim() === profile.name"
              :aria-busy="saving"
            >
              {{ saving ? "保存中…" : "保存资料" }}
            </button>
          </div>
        </form>
      </section>
      <section class="panel account-card">
        <header>
          <span class="account-icon"><Icon name="audit" :size="22" /></span>
          <div>
            <h2>修改密码</h2>
            <p>修改后，所有设备上的旧登录会话都会失效。</p>
          </div>
        </header>
        <form @submit.prevent="changePassword">
          <fieldset :disabled="changing">
            <label
              >当前密码<input
                v-model="currentPassword"
                :type="showPasswords ? 'text' : 'password'"
                autocomplete="current-password"
                required
                maxlength="200"
                placeholder="输入当前登录密码"
            /></label>
            <label
              >新密码<input
                v-model="newPassword"
                :type="showPasswords ? 'text' : 'password'"
                autocomplete="new-password"
                required
                minlength="8"
                maxlength="72"
                placeholder="至少 8 位"
            /></label>
            <label
              >确认新密码<input
                v-model="confirmation"
                :type="showPasswords ? 'text' : 'password'"
                autocomplete="new-password"
                required
                minlength="8"
                maxlength="72"
                placeholder="再次输入新密码"
            /></label>
            <label class="check-row"
              ><input v-model="showPasswords" type="checkbox" />显示密码</label
            >
            <p class="note">
              建议使用字母、数字和符号的组合，并避免与其他平台共用密码。
            </p>
            <p v-if="passwordError" class="error-box" role="alert">
              {{ passwordError }}
            </p>
            <div class="form-actions">
              <button
                class="primary"
                :disabled="changing"
                :aria-busy="changing"
              >
                {{ changing ? "更新中…" : "修改密码并重新登录" }}
              </button>
            </div>
          </fieldset>
        </form>
      </section>
    </div>
  </AsyncState>
</template>
<style scoped>
.account-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
  gap: 24px;
  align-items: start;
  max-width: 1120px;
}
.account-card {
  padding: 26px;
}
.account-card header {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 24px;
}
.account-card h2 {
  font-size: 18px;
  margin: 0 0 5px;
}
.account-card header p {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.account-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: var(--forest);
  background: color-mix(in srgb, var(--forest) 8%, var(--surface));
  flex-shrink: 0;
}
.account-facts {
  margin: 0 0 24px;
  border-block: 1px solid var(--line);
  padding: 12px 0;
}
.account-facts > div {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 13px;
}
.account-facts dt {
  color: var(--muted);
  flex-shrink: 0;
}
.account-facts dd {
  margin: 0;
  overflow-wrap: anywhere;
  text-align: right;
}
.account-card label {
  margin: 0 0 18px;
}
.account-card input {
  width: 100%;
}
.account-card .check-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.account-card .check-row input {
  width: auto;
}
.account-card fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.account-card .form-actions {
  margin: 24px 0 0;
}
.account-card .note {
  font-size: 12px;
}
@media (max-width: 1000px) {
  .account-grid {
    grid-template-columns: 1fr;
    max-width: 680px;
    gap: 18px;
  }
}
@media (max-width: 600px) {
  .account-card {
    padding: 20px;
  }
}
</style>
