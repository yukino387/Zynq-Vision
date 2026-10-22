<script setup lang="ts">
import { onMounted, ref } from "vue";
import type { Role } from "@vision/contracts";
import { chinese } from "@vision/shared";
import { api, post, errorText } from "../api";
import { useAuthStore } from "../stores/auth";
import { useNotificationStore } from "../stores/notifications";
import AsyncState from "../components/AsyncState.vue";
import Icon from "../components/Icon.vue";
import {
  UiAlert,
  UiBadge,
  UiButton,
  UiCard,
  UiInput,
  UiSwitch,
} from "../components/ui";

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
    <div v-if="auth.admin" class="heading-actions">
      <UiButton variant="outline" size="sm" to="/access/users">
        管理所有账号
      </UiButton>
    </div>
  </div>

  <AsyncState :loading="loading" :error="loadError" @retry="load">
    <div v-if="profile" class="account-grid">
      <!-- 个人资料卡片 -->
      <UiCard padding="lg" class="account-card">
        <header class="account-header">
          <span class="account-icon"><Icon name="users" :size="22" /></span>
          <div>
            <h2>个人资料</h2>
            <p>姓名用于页面顶栏显示及操作追溯记录。</p>
          </div>
        </header>

        <dl class="account-facts">
          <div class="fact-row">
            <dt>登录账号</dt>
            <dd class="mono font-semibold">{{ profile.username }}</dd>
          </div>
          <div class="fact-row">
            <dt>当前角色</dt>
            <dd>
              <UiBadge tone="info" chip size="sm">{{
                chinese(profile.role)
              }}</UiBadge>
            </dd>
          </div>
          <div class="fact-row">
            <dt>加入时间</dt>
            <dd class="mono text-muted">
              {{ new Date(profile.createdAt).toLocaleDateString() }}
            </dd>
          </div>
        </dl>

        <form @submit.prevent="saveProfile" class="form-content">
          <div class="form-group">
            <label class="form-label" for="account-name-input">姓名</label>
            <UiInput
              id="account-name-input"
              v-model="name"
              autocomplete="name"
              required
              :maxlength="60"
              :disabled="saving"
              block
              placeholder="输入你的显示姓名"
            />
          </div>
          <div class="form-actions">
            <UiButton
              type="submit"
              variant="primary"
              :disabled="saving || !name.trim() || name.trim() === profile.name"
              :loading="saving"
            >
              {{ saving ? "保存中…" : "保存资料" }}
            </UiButton>
          </div>
        </form>
      </UiCard>

      <!-- 修改密码卡片 -->
      <UiCard padding="lg" class="account-card">
        <header class="account-header">
          <span class="account-icon"><Icon name="audit" :size="22" /></span>
          <div>
            <h2>修改密码</h2>
            <p>修改成功后，所有设备上的旧登录会话都会失效。</p>
          </div>
        </header>

        <form @submit.prevent="changePassword" class="form-content">
          <fieldset :disabled="changing" class="form-fieldset">
            <div class="form-group">
              <label class="form-label" for="pwd-current">当前密码</label>
              <UiInput
                id="pwd-current"
                v-model="currentPassword"
                :type="showPasswords ? 'text' : 'password'"
                autocomplete="current-password"
                required
                :maxlength="200"
                placeholder="输入当前使用的登录密码"
                block
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="pwd-new">新密码</label>
              <UiInput
                id="pwd-new"
                v-model="newPassword"
                :type="showPasswords ? 'text' : 'password'"
                autocomplete="new-password"
                required
                :minlength="8"
                :maxlength="72"
                placeholder="至少 8 位（字母、数字与符号组合）"
                block
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="pwd-confirm">确认新密码</label>
              <UiInput
                id="pwd-confirm"
                v-model="confirmation"
                :type="showPasswords ? 'text' : 'password'"
                autocomplete="new-password"
                required
                :minlength="8"
                :maxlength="72"
                placeholder="再次输入新密码"
                block
              />
            </div>

            <div class="check-row">
              <UiSwitch v-model="showPasswords" label="显示密码明文" />
            </div>

            <p class="pwd-tip">
              建议使用包含大小写字母、数字和符号的强密码，并避免与其他平台共用密码。
            </p>

            <UiAlert v-if="passwordError" tone="crit" title="密码未更新">
              {{ passwordError }}
            </UiAlert>

            <div class="form-actions">
              <UiButton
                type="submit"
                variant="primary"
                :disabled="
                  changing || !currentPassword || !newPassword || !confirmation
                "
                :loading="changing"
              >
                {{ changing ? "更新中…" : "修改密码并重新登录" }}
              </UiButton>
            </div>
          </fieldset>
        </form>
      </UiCard>
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

.account-header {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 22px;
}

.account-header h2 {
  font-size: 18px;
  font-weight: 650;
  margin: 0 0 4px;
  color: var(--ink);
}

.account-header p {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.4;
}

.account-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: var(--forest);
  background: color-mix(in srgb, var(--forest) 10%, var(--surface));
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--forest) 20%, transparent);
}

.account-facts {
  margin: 0 0 24px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 8px 0;
}

.fact-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  font-size: 13px;
}

.fact-row dt {
  color: var(--muted);
  flex-shrink: 0;
}

.fact-row dd {
  margin: 0;
  text-align: right;
  color: var(--ink);
}

.font-semibold {
  font-weight: 600;
}

.text-muted {
  color: var(--muted);
}

.form-content {
  display: flex;
  flex-direction: column;
}

.form-fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
}

.form-group {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 13px;
  font-weight: 550;
  color: var(--ink);
}

.check-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 14px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  user-select: none;
}

.check-row input[type="checkbox"] {
  cursor: pointer;
  accent-color: var(--forest);
  width: 15px;
  height: 15px;
  margin: 0;
}

.check-row label {
  cursor: pointer;
  margin: 0;
}

.pwd-tip {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
  margin: 0 0 16px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--crit-bg, #f5e0da);
  border: 1px solid var(--crit-line, #d9a097);
  color: var(--red, #b6372a);
  padding: 10px 14px;
  border-radius: var(--radius, 6px);
  font-size: 13px;
  margin-bottom: 16px;
}

.form-actions {
  margin-top: 8px;
  display: flex;
}

@media (max-width: 1000px) {
  .account-grid {
    grid-template-columns: 1fr;
    max-width: 640px;
    gap: 20px;
  }
}
</style>
