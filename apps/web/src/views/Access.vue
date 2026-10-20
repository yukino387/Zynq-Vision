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
    <h1>{{ tab === "codes" ? "注册码管理" : "用户管理" }}</h1>
    <button v-if="tab === 'codes'" class="primary" @click="form = true">
      签发注册码</button
    ><template v-else>
      <button class="primary" @click="newUser = true">新建账号</button>
      <RouterLink
        class="button-link"
        :to="{
          name: 'access',
          params: { tab: 'codes' },
          query: { invite: '1' },
        }"
        >签发注册码</RouterLink
      >
    </template>
  </div>
  <section class="permissions-summary">
    <h2>职责与权限</h2>
    <div class="role-cards">
      <article>
        <b>操作员 · 现场执行</b>
        <p>
          按任务采样、查看结果、提交复核意见。不能审核训练数据、修改方案或发布模型。
        </p>
      </article>
      <article>
        <b>管理员 · 业务负责人</b>
        <p>
          配置和删除产品方案、管理采样任务及业务数据、审核并冻结数据、批准发布与回退、管理人员。具有工程师和操作员的全部业务能力。
        </p>
      </article>
      <article>
        <b>工程师 · 开发与维护</b>
        <p>
          连接和诊断设备、采样和标注、整理草稿数据集、训练与评估。不能管理方案与采样任务、删除原始图片或整个数据集、执行正式审核和发布。
        </p>
      </article>
    </div>
    <div class="table-wrap section-space">
      <table>
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
            <td v-for="(value, index) in row" :key="index">{{ value }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="note">
      注册码只能创建操作员或工程师账号，且每个注册码只能注册一个账号；管理员账号只能由现有管理员在用户管理中直接创建。当前为角色级权限，尚未提供按人员隔离工位数据的绑定授权。
    </p>
  </section>
  <form class="toolbar" @submit.prevent="list.filter">
    <input
      v-model="list.search.value"
      :placeholder="tab === 'codes' ? '搜索用途备注' : '搜索用户姓名'"
      aria-label="搜索"
    /><button>搜索</button
    ><button type="button" @click="list.load">刷新</button>
  </form>
  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    @retry="list.load"
  >
    <div class="panel table-wrap">
      <table>
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
            <td>{{ tab === "codes" ? r.label : r.name }}</td>
            <td class="mono">
              {{ tab === "codes" ? `${r.prefix}…` : r.username }}
            </td>
            <td>
              <template v-if="tab === 'codes'">
                <span class="tag">{{ chinese(r.role) }}</span>
                {{ new Date(String(r.expiresAt)).toLocaleString() }}
              </template>
              <template v-else>{{ chinese(r.role) }}</template>
            </td>
            <td>
              <span
                class="tag"
                :class="{ crit: tab === 'users' && r.disabled }"
                >{{
                  tab === "codes" ? status(r) : r.disabled ? "已停用" : "正常"
                }}</span
              >
            </td>
            <td class="action-cell">
              <div class="row-actions">
                <button
                  v-if="tab === 'codes' && status(r) === '可使用'"
                  class="table-action danger"
                  @click="revoke(r)"
                  :disabled="busy"
                >
                  撤销</button
                ><button
                  v-else-if="tab === 'users' && r.id !== auth.user?.id"
                  class="table-action"
                  @click="edit(r)"
                >
                  管理</button
                ><span v-else class="muted">{{
                  r.id === auth.user?.id ? "当前账号" : "—"
                }}</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
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
  <Drawer v-if="form" title="签发注册码" @close="form = false"
    ><form @submit.prevent="issue">
      <label
        >用途备注<input
          v-model="label"
          required
          maxlength="100"
          placeholder="例如：一号工位新操作员" /></label
      ><label
        >账号角色<select v-model="codeRole">
          <option value="OPERATOR">操作员（采样与反馈）</option>
          <option value="ENGINEER">工程师（设备、标注与训练）</option>
        </select></label
      ><label
        >有效天数<input
          v-model.number="days"
          type="number"
          min="1"
          max="30"
          required
      /></label>
      <p class="note">
        每个注册码只能注册一个账号。管理员账号不在注册码范围内，请在用户管理中直接创建。
      </p>
      <button class="primary" :disabled="busy">确认签发</button>
    </form></Drawer
  >
  <Drawer v-if="issued" title="注册码已签发" @close="issued = ''"
    ><p>
      请复制并交给新用户，关闭后不再显示完整注册码。该注册码只能创建<strong>{{
        chinese(issuedRole)
      }}</strong
      >账号。
    </p>
    <label>注册码<input class="mono" :value="issued" readonly /></label
    ><button class="primary" @click="copy">复制注册码</button></Drawer
  >
  <Drawer v-if="newUser" title="新建账号" @close="newUser = false"
    ><form @submit.prevent="createUser">
      <label
        >姓名<input
          v-model="newName"
          required
          maxlength="60"
          autocomplete="off" /></label
      ><label
        >登录账号<input
          v-model.trim="newUsername"
          required
          pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]{2,39}"
          title="3 至 40 位字母、数字、下划线、短横线或点"
          maxlength="40"
          autocomplete="off" /></label
      ><label
        >初始密码<input
          v-model="newPassword"
          required
          type="password"
          minlength="8"
          maxlength="100"
          autocomplete="new-password"
          placeholder="至少 8 位" /></label
      ><label
        >账号角色<select v-model="newRole">
          <option value="OPERATOR">操作员（采样与反馈）</option>
          <option value="ENGINEER">工程师（设备、标注与训练）</option>
          <option value="ADMIN">管理员（人员、审核与发布）</option>
        </select></label
      >
      <p class="note">创建的账号可立即登录；请通过安全渠道转交初始密码。</p>
      <button class="primary" :disabled="busy">创建账号</button>
    </form></Drawer
  >
  <Drawer v-if="user" :title="`管理用户：${user.name}`" @close="user = null"
    ><form @submit.prevent="saveUser">
      <label
        >角色<select v-model="role">
          <option value="OPERATOR">工人（采样与反馈）</option>
          <option value="ENGINEER">技术维护人员（设备、标注与训练）</option>
          <option value="ADMIN">管理员</option>
        </select></label
      ><label class="check-row"
        ><input v-model="disabled" type="checkbox" />停用账号</label
      ><button class="primary" :disabled="busy">保存更改</button>
    </form>
    <details v-if="user.id !== auth.user?.id" class="password-reset">
      <summary>重置此账号的密码</summary>
      <p class="note">
        用于协助忘记密码的用户。重置后，该账号的所有旧登录会话失效，需使用新密码重新登录。
      </p>
      <form @submit.prevent="resetUserPassword">
        <label
          >新密码<input
            v-model="resetPassword"
            type="password"
            autocomplete="new-password"
            required
            minlength="8"
            maxlength="72"
            placeholder="至少 8 位"
            :disabled="busy"
        /></label>
        <label
          >确认新密码<input
            v-model="resetConfirmation"
            type="password"
            autocomplete="new-password"
            required
            minlength="8"
            maxlength="72"
            :disabled="busy"
        /></label>
        <button :disabled="busy" :aria-busy="busy">
          {{ busy ? "重置中…" : "重置密码并使旧会话失效" }}
        </button>
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
