<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { chinese } from "@vision/shared";
import { api, post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useNotificationStore } from "../stores/notifications";
import { useList } from "../composables/useList";
import Drawer from "../components/Drawer.vue";
import AsyncState from "../components/AsyncState.vue";
import Pager from "../components/Pager.vue";
import type { Named } from "../types";
import {
  UiButton,
  UiInput,
  UiSelect,
  UiCard,
  UiBadge,
  UiTable,
} from "../components/ui";
const route = useRoute(),
  auth = useAuthStore(),
  notices = useNotificationStore();
const tab = computed(() => String(route.params.tab || "users"));
const endpoint = computed(() =>
  tab.value === "codes" ? "/registration-codes" : "/users",
);
const list = useList<Named>(endpoint),
  form = ref(false),
  busy = ref(false),
  issued = ref(""),
  issuedRole = ref<"OPERATOR" | "ENGINEER">("OPERATOR"),
  label = ref(""),
  days = ref(7),
  codeRole = ref<"OPERATOR" | "ENGINEER">("OPERATOR"),
  newUser = ref(false),
  newName = ref(""),
  newUsername = ref(""),
  newPassword = ref(""),
  newRole = ref<"ADMIN" | "ENGINEER" | "OPERATOR">("ENGINEER"),
  user = ref<Named | null>(null),
  role = ref("OPERATOR"),
  disabled = ref(false);
const resetPassword = ref(""),
  resetConfirmation = ref("");
const permissions = [
  [
    "方案与采样任务",
    "创建、修改、删除和安排任务",
    "查看方案、执行采样任务",
    "执行采样任务",
  ],
  [
    "样本与标注",
    "采样、导入、标注、审核、删除",
    "采样、导入、标注和质量处理",
    "采样、上传和查看结果",
  ],
  [
    "数据集",
    "整理、冻结、导出、删除",
    "整理草稿、移入移出样本、导出",
    "无管理权限",
  ],
  [
    "模型",
    "训练、评估、批准、发布和回退",
    "导入、训练、评估和兼容性验证",
    "查看现场检测结果",
  ],
  [
    "设备",
    "连接、诊断与运行控制",
    "连接、诊断与运行控制",
    "使用已连接的设备采样",
  ],
  [
    "终端更新",
    "查看更新能力与旧固件档案",
    "查看更新能力与旧固件档案",
    "无管理权限",
  ],
  ["人员与账号", "管理账号、角色和注册码", "维护个人资料", "维护个人资料"],
];
watch(
  () => user.value?.id,
  () => {
    resetPassword.value = resetConfirmation.value = "";
  },
);
const status = (r: Named) =>
  r.usedAt
    ? "已使用"
    : r.revokedAt
      ? "已撤销"
      : Date.parse(String(r.expiresAt)) < Date.now()
        ? "已过期"
        : "可使用";
watch(
  () => route.query.invite,
  (invite) => {
    if (invite === "1" && tab.value === "codes") form.value = true;
  },
  { immediate: true },
);
async function issue() {
  busy.value = true;
  try {
    const r = await post<{ code: string }>("/registration-codes", {
      label: label.value,
      days: days.value,
      role: codeRole.value,
    });
    issued.value = r.code;
    issuedRole.value = codeRole.value;
    form.value = false;
    label.value = "";
    codeRole.value = "OPERATOR";
    await list.load();
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(issued.value);
    notices.add("注册码已复制");
  } catch {
    notices.add("请选中注册码后手动复制");
  }
}
async function revoke(r: Named) {
  busy.value = true;
  try {
    await api(`/registration-codes/${r.id}/revoke`, { method: "PATCH" });
    await list.load();
    notices.add("注册码已撤销");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function createUser() {
  busy.value = true;
  try {
    await post("/users", {
      name: newName.value,
      username: newUsername.value,
      password: newPassword.value,
      role: newRole.value,
    });
    newUser.value = false;
    newName.value = "";
    newUsername.value = "";
    newPassword.value = "";
    newRole.value = "ENGINEER";
    await list.load();
    notices.add("账号已创建");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
function edit(r: Named) {
  user.value = r;
  role.value = String(r.role);
  disabled.value = Boolean(r.disabled);
}
async function saveUser() {
  if (!user.value) return;
  busy.value = true;
  try {
    await api(`/users/${user.value.id}`, {
      method: "PATCH",
      body: JSON.stringify({ role: role.value, disabled: disabled.value }),
    });
    user.value = null;
    await list.load();
    notices.add("用户已更新");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function resetUserPassword() {
  if (!user.value) return;
  if (resetPassword.value !== resetConfirmation.value) {
    notices.add("两次输入的新密码不一致", true);
    return;
  }
  busy.value = true;
  try {
    await post(`/users/${user.value.id}/password`, {
      newPassword: resetPassword.value,
    });
    resetPassword.value = resetConfirmation.value = "";
    notices.add("密码已重置，该账号的旧登录会话已失效");
  } catch (error) {
    notices.error(error);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>{{ tab === "codes" ? "注册码管理" : "用户管理" }}</h1>
      <p>
        管理系统成员、分配操作员/工程师/管理员权限，并签发一次性成员注册邀请码。
      </p>
    </div>
    <div class="heading-actions">
      <UiButton
        v-if="tab === 'codes'"
        variant="primary"
        icon="pairing"
        @click="form = true"
      >
        签发注册码
      </UiButton>
      <template v-else>
        <UiButton variant="primary" icon="users" @click="newUser = true">
          新建账号
        </UiButton>
        <UiButton
          variant="outline"
          :to="{
            name: 'access',
            params: { tab: 'codes' },
            query: { invite: '1' },
          }"
        >
          签发注册码
        </UiButton>
      </template>
    </div>
  </div>

  <UiCard padding="lg" class="permissions-card">
    <template #header>
      <div>
        <h2 class="permissions-title">职责与权限矩阵</h2>
        <p class="permissions-sub">
          明确界定生产现场、技术维护与业务管理的权限边界
        </p>
      </div>
    </template>

    <div class="role-cards">
      <UiCard hover padding="md" class="role-card">
        <template #header>
          <div class="role-card-header">
            <b>操作员</b>
            <UiBadge tone="info" chip size="sm">现场执行</UiBadge>
          </div>
        </template>
        <p>
          按任务执行采样、查看实时结果、提交复核意见。不能审核训练数据、修改方案或发布模型。
        </p>
      </UiCard>

      <UiCard hover padding="md" class="role-card">
        <template #header>
          <div class="role-card-header">
            <b>管理员</b>
            <UiBadge tone="forest" chip size="sm">业务负责人</UiBadge>
          </div>
        </template>
        <p>
          配置和删除产品方案、管理采样任务及业务数据、审核并冻结数据、批准发布与回退、管理人员。
        </p>
      </UiCard>

      <UiCard hover padding="md" class="role-card">
        <template #header>
          <div class="role-card-header">
            <b>工程师</b>
            <UiBadge tone="warn" chip size="sm">开发与维护</UiBadge>
          </div>
        </template>
        <p>
          连接和诊断设备、采样和标注、整理草稿数据集、训练与评估。不能管理方案与审核正式发布。
        </p>
      </UiCard>
    </div>

    <div class="table-wrap section-space">
      <UiTable compact hover>
        <thead>
          <tr>
            <th>操作范围</th>
            <th>管理员</th>
            <th>工程师</th>
            <th>操作员</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in permissions" :key="row[0]">
            <td class="font-semibold">{{ row[0] }}</td>
            <td>{{ row[1] }}</td>
            <td>{{ row[2] }}</td>
            <td>{{ row[3] }}</td>
          </tr>
        </tbody>
      </UiTable>
    </div>

    <p class="note mt-3">
      *
      注册码只能创建操作员或工程师账号，且每个注册码仅支持使用一次；管理员账号由现有管理员直接在用户管理中创建。
    </p>
  </UiCard>

  <form class="access-toolbar" @submit.prevent="list.filter">
    <div class="search-input-wrap">
      <UiInput
        v-model="list.search.value"
        icon="search"
        clearable
        :placeholder="tab === 'codes' ? '搜索用途备注' : '搜索用户姓名或账号'"
        aria-label="搜索"
        block
      />
    </div>
    <UiButton type="submit" variant="primary">搜索</UiButton>
    <UiButton
      type="button"
      variant="secondary"
      icon="refresh"
      @click="list.load"
      >刷新</UiButton
    >
  </form>

  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    @retry="list.load"
  >
    <UiTable hover>
      <thead>
        <tr>
          <th>{{ tab === "codes" ? "用途备注" : "用户" }}</th>
          <th>{{ tab === "codes" ? "注册码前缀" : "账号" }}</th>
          <th>{{ tab === "codes" ? "角色 · 有效期至" : "角色" }}</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in list.items.value" :key="r.id">
          <td class="font-semibold">
            {{ tab === "codes" ? r.label : r.name }}
          </td>
          <td class="mono">
            {{ tab === "codes" ? `${r.prefix}…` : r.username }}
          </td>
          <td>
            <template v-if="tab === 'codes'">
              <UiBadge tone="info" chip size="sm">{{
                chinese(r.role)
              }}</UiBadge>
              <span class="mono text-muted text-xs ml-2">{{
                new Date(String(r.expiresAt)).toLocaleString()
              }}</span>
            </template>
            <template v-else>
              <UiBadge
                :tone="
                  r.role === 'ADMIN'
                    ? 'forest'
                    : r.role === 'ENGINEER'
                      ? 'warn'
                      : 'info'
                "
                chip
                size="sm"
              >
                {{ chinese(r.role) }}
              </UiBadge>
            </template>
          </td>
          <td>
            <UiBadge
              :tone="
                tab === 'codes'
                  ? status(r) === '可使用'
                    ? 'success'
                    : 'neutral'
                  : r.disabled
                    ? 'crit'
                    : 'success'
              "
              size="sm"
              dot
            >
              {{ tab === "codes" ? status(r) : r.disabled ? "已停用" : "正常" }}
            </UiBadge>
          </td>
          <td class="action-cell">
            <div class="row-actions">
              <UiButton
                v-if="tab === 'codes' && status(r) === '可使用'"
                variant="danger"
                size="sm"
                @click="revoke(r)"
                :disabled="busy"
              >
                撤销
              </UiButton>
              <UiButton
                v-else-if="tab === 'users' && r.id !== auth.user?.id"
                variant="outline"
                size="sm"
                @click="edit(r)"
              >
                管理
              </UiButton>
              <span v-else class="text-muted text-xs">{{
                r.id === auth.user?.id ? "当前账号" : "其他账号"
              }}</span>
            </div>
          </td>
        </tr>
      </tbody>
    </UiTable>
  </AsyncState>
  <Pager
    :page="list.page.value"
    :page-size="list.pageSize.value"
    :total="list.total.value"
    @update:page="
      (p) => {
        list.page.value = p;
        list.load();
      }
    "
    @update:page-size="list.setPageSize"
  />
  <Drawer v-if="form" title="签发注册码" @close="form = false">
    <form @submit.prevent="issue" class="drawer-form">
      <div class="form-group">
        <label class="form-label">用途备注</label>
        <UiInput
          v-model="label"
          required
          :maxlength="100"
          placeholder="例如：一号工位新操作员"
          block
        />
      </div>
      <div class="form-group">
        <label class="form-label">账号角色</label>
        <UiSelect v-model="codeRole" block>
          <option value="OPERATOR">操作员（采样与反馈）</option>
          <option value="ENGINEER">工程师（设备、标注与训练）</option>
        </UiSelect>
      </div>
      <div class="form-group">
        <label class="form-label">有效天数</label>
        <UiInput
          v-model.number="days"
          type="number"
          :min="1"
          :max="30"
          required
          block
        />
      </div>
      <p class="note">
        每个注册码只能注册一个账号。管理员账号不在注册码范围内，请在用户管理中直接创建。
      </p>
      <div class="form-actions mt-3">
        <UiButton
          type="submit"
          variant="primary"
          :disabled="busy"
          :loading="busy"
        >
          确认签发注册码
        </UiButton>
      </div>
    </form>
  </Drawer>

  <Drawer v-if="issued" title="注册码已签发" @close="issued = ''">
    <p>
      请复制并转交给新用户，抽屉关闭后将不再显示完整注册码。该注册码只能创建<strong
        >{{ chinese(issuedRole) }}</strong
      >账号。
    </p>
    <div class="form-group mt-3">
      <label class="form-label">注册码</label>
      <UiInput
        class="mono font-semibold"
        :model-value="issued"
        readonly
        block
      />
    </div>
    <div class="form-actions mt-3">
      <UiButton variant="primary" icon="clipboard" @click="copy">
        复制注册码
      </UiButton>
    </div>
  </Drawer>

  <Drawer v-if="newUser" title="新建账号" @close="newUser = false">
    <form @submit.prevent="createUser" class="drawer-form">
      <div class="form-group">
        <label class="form-label">姓名</label>
        <UiInput
          v-model="newName"
          required
          :maxlength="60"
          autocomplete="off"
          placeholder="用户姓名"
          block
        />
      </div>
      <div class="form-group">
        <label class="form-label">登录账号</label>
        <UiInput
          v-model.trim="newUsername"
          required
          :maxlength="40"
          autocomplete="off"
          placeholder="英文、数字、下划线组合"
          block
        />
      </div>
      <div class="form-group">
        <label class="form-label">初始密码</label>
        <UiInput
          v-model="newPassword"
          required
          type="password"
          :minlength="8"
          :maxlength="100"
          autocomplete="new-password"
          placeholder="至少 8 位初始密码"
          block
        />
      </div>
      <div class="form-group">
        <label class="form-label">账号角色</label>
        <UiSelect v-model="newRole" block>
          <option value="OPERATOR">操作员（采样与反馈）</option>
          <option value="ENGINEER">工程师（设备、标注与训练）</option>
          <option value="ADMIN">管理员（人员、审核与发布）</option>
        </UiSelect>
      </div>
      <p class="note">创建的账号可立即登录；请通过安全渠道转交初始密码。</p>
      <div class="form-actions mt-3">
        <UiButton
          type="submit"
          variant="primary"
          :disabled="busy"
          :loading="busy"
        >
          创建新账号
        </UiButton>
      </div>
    </form>
  </Drawer>

  <Drawer v-if="user" :title="`管理用户：${user.name}`" @close="user = null">
    <form @submit.prevent="saveUser" class="drawer-form">
      <div class="form-group">
        <label class="form-label">角色权限</label>
        <UiSelect v-model="role" block>
          <option value="OPERATOR">工人（采样与反馈）</option>
          <option value="ENGINEER">技术维护人员（设备、标注与训练）</option>
          <option value="ADMIN">管理员</option>
        </UiSelect>
      </div>
      <div class="check-row">
        <input id="user-disabled-chk" v-model="disabled" type="checkbox" />
        <label for="user-disabled-chk">停用此账号</label>
      </div>
      <div class="form-actions mt-2">
        <UiButton
          type="submit"
          variant="primary"
          :disabled="busy"
          :loading="busy"
        >
          保存更改
        </UiButton>
      </div>
    </form>

    <details v-if="user.id !== auth.user?.id" class="password-reset">
      <summary>重置此账号的密码</summary>
      <p class="note">
        用于协助忘记密码的用户。重置后，该账号的所有旧登录会话失效，需使用新密码重新登录。
      </p>
      <form @submit.prevent="resetUserPassword" class="drawer-form mt-2">
        <div class="form-group">
          <label class="form-label">新密码</label>
          <UiInput
            v-model="resetPassword"
            type="password"
            autocomplete="new-password"
            required
            :minlength="8"
            :maxlength="72"
            placeholder="至少 8 位"
            :disabled="busy"
            block
          />
        </div>
        <div class="form-group">
          <label class="form-label">确认新密码</label>
          <UiInput
            v-model="resetConfirmation"
            type="password"
            autocomplete="new-password"
            required
            :minlength="8"
            :maxlength="72"
            :disabled="busy"
            block
          />
        </div>
        <div class="form-actions mt-2">
          <UiButton
            type="submit"
            variant="secondary"
            :disabled="busy"
            :loading="busy"
          >
            重置密码并使旧会话失效
          </UiButton>
        </div>
      </form>
    </details>
    <p v-else class="note section-space">
      修改自己的密码请到
      <RouterLink to="/account" @click="user = null">账号设置</RouterLink
      >，并验证当前密码。
    </p>
  </Drawer>
</template>
<style scoped>
.password-reset {
  margin-top: 26px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.permissions-summary {
  padding: 24px;
  background: var(--surface);
  border: 1px solid var(--line);
  margin-bottom: 24px;
}
.permissions-summary h2 {
  font-size: 18px;
  margin-top: 0;
}
.permissions-summary > .role-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.permissions-summary article p {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.8;
}
@media (max-width: 760px) {
  .permissions-summary > .role-cards {
    grid-template-columns: 1fr;
  }
}
</style>
