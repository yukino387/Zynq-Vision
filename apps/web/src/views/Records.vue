<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import type { Inspection } from "../types";
import { useList } from "../composables/useList";
import { useAuthStore } from "../stores/auth";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import Pager from "../components/Pager.vue";
import SortableTh from "../components/SortableTh.vue";

const auth = useAuthStore();
const route = useRoute(),
  endpoint = ref("/inspections"),
  list = useList<Inspection>(endpoint),
  tab = computed(() =>
    String(route.params.tab || route.meta.defaultTab || "queue"),
  );

/** 待办 tab 只要待复核的；「全部」不加结果筛选。
 *  useList 创建时已按空筛选取过一次，这里按 tab 纠正并重载。 */
function applyTab() {
  list.realOnly.value = "true";
  list.result.value = tab.value === "queue" ? "REVIEW" : "";
  list.reviewed.value = tab.value === "queue" ? "false" : "";
  list.filter();
}
watch(tab, applyTab);
applyTab();
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>{{ tab === "queue" ? "待复核记录" : "全部检测记录" }}</h1>
    </div>
    <RouterLink :to="{ name: 'workbench' }">返回工作台</RouterLink>
  </div>

  <form class="toolbar" @submit.prevent="list.filter">
    <input
      v-if="auth.engineer"
      v-model="list.search.value"
      type="search"
      placeholder="搜索检测编号…"
      aria-label="搜索检测编号"
    /><button
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
    >
      查询</button
    ><span class="right inline-count">{{ list.total.value }} 条记录</span>
  </form>

  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    :hint="
      tab === 'queue'
        ? '所有待复核记录已处理，可返回工作台继续采样。'
        : '还没有检测记录。'
    "
    @retry="list.load"
    ><div class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th v-if="auth.engineer">检测编号</th>
            <SortableTh
              field="createdAt"
              label="时间"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th>机器原判 / 平台核验</th>
            <th>人工复核</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in list.items.value" :key="i.id">
            <td v-if="auth.engineer" class="mono">{{ i.id.slice(-10) }}</td>
            <td>{{ new Date(i.createdAt).toLocaleString() }}</td>
            <td>
              <Status chip :value="i.metadata?.localResult || i.result" /> /
              <Status :value="i.result" />
              <span v-if="i.source === 'SIMULATION'" class="tag simulated"
                >模拟</span
              >
            </td>
            <td>
              {{
                i.reviewResult === "PASS" || i.reviewResult === "FAIL"
                  ? "已复核"
                  : i.result === "REVIEW" ||
                      i.result === "ERROR" ||
                      i.reviewResult === "REVIEW"
                    ? "待复核"
                    : "—"
              }}
            </td>
            <td class="action-cell">
              <div class="row-actions">
                <RouterLink
                  class="table-action"
                  :to="{
                    name: 'inspection',
                    params: { id: i.id },
                    query: tab === 'queue' ? { queue: '1' } : {},
                  }"
                  >{{ tab === "queue" ? "立即复核" : "查看详情" }}</RouterLink
                >
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div></AsyncState
  >
  <Pager
    :page="list.page.value"
    :total="list.total.value"
    :page-size="list.pageSize.value"
    @update:page="
      (p) => {
        list.page.value = p;
        list.load();
      }
    "
    @update:page-size="list.setPageSize"
  />
</template>
