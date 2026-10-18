<script setup lang="ts">
import { computed, ref } from "vue";
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
  label = ref(""),
  days = ref(7),
  user = ref<Named | null>(null),
  role = ref("OPERATOR"),
  disabled = ref(false);
const status = (r: Named) =>
  r.usedAt
    ? "已使用"
    : r.revokedAt
      ? "已撤销"
      : Date.parse(String(r.expiresAt)) < Date.now()
        ? "已过期"
        : "可使用";
async function issue() {
  busy.value = true;
  try {
    const r = await post<{ code: string }>("/registration-codes", {
      label: label.value,
      days: days.value,
    });
    issued.value = r.code;
    form.value = false;
    label.value = "";
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
</script>
<template>
  <div class="page-heading">
    <h1>{{ tab === "codes" ? "注册码管理" : "用户管理" }}</h1>
    <button v-if="tab === 'codes'" class="primary" @click="form = true">
      签发注册码</button
    ><RouterLink
      v-else
      class="button-link"
      :to="{ name: 'access', params: { tab: 'codes' } }"
      >邀请新用户</RouterLink
    >
  </div>
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
            <th>{{ tab === "codes" ? "有效期至" : "角色" }}</th>
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
              {{
                tab === "codes"
                  ? new Date(String(r.expiresAt)).toLocaleString()
                  : chinese(r.role)
              }}
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
            <td>
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
        >有效天数<input
          v-model.number="days"
          type="number"
          min="1"
          max="30"
          required
      /></label>
      <p class="note">每个注册码仅可注册一个操作员账号。</p>
      <button class="primary" :disabled="busy">确认签发</button>
    </form></Drawer
  >
  <Drawer v-if="issued" title="注册码已签发" @close="issued = ''"
    ><p>请复制并交给新用户，关闭后不再显示完整注册码。</p>
    <label>注册码<input class="mono" :value="issued" readonly /></label
    ><button class="primary" @click="copy">复制注册码</button></Drawer
  >
  <Drawer v-if="user" :title="`管理用户：${user.name}`" @close="user = null"
    ><form @submit.prevent="saveUser">
      <label
        >角色<select v-model="role">
          <option value="OPERATOR">操作员</option>
          <option value="ENGINEER">工程师</option>
          <option value="ADMIN">管理员</option>
        </select></label
      ><label class="check-row"
        ><input v-model="disabled" type="checkbox" />停用账号</label
      ><button class="primary" :disabled="busy">保存更改</button>
    </form></Drawer
  >
</template>
