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
    String(route.params.tab || route.meta.defaultTab || "all"),
  );

function applyTab() {
  list.realOnly.value = "true";
  list.result.value =
    tab.value === "uncertain"
      ? "REVIEW"
      : tab.value === "errors"
        ? "ERROR"
        : "";
  list.reviewed.value = "";
  list.filter();
}
watch(tab, applyTab);
applyTab();
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>
        {{
          tab === "uncertain"
            ? "判定不确定"
            : tab === "errors"
              ? "检测错误"
              : "全部检测记录"
        }}
      </h1>
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
      v-if="auth.engineer"
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
    >
      查询</button
    ><button
      v-else
      type="button"
      :disabled="list.loading.value"
      @click="list.load"
    >
      刷新记录</button
    ><span class="right inline-count">{{ list.total.value }} 条记录</span>
  </form>

  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    hint="当前筛选下没有检测记录。"
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
            <th>检测结果</th>
            <th>运行状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in list.items.value" :key="i.id">
            <td v-if="auth.engineer" class="mono" :title="i.id">
              {{ i.id.slice(-10) }}
            </td>
            <td>{{ new Date(i.createdAt).toLocaleString() }}</td>
            <td>
              <Status chip :value="i.reviewResult ?? i.result" />
              <small v-if="i.reviewResult">已更正</small>
            </td>
            <td>
              {{
                i.result === "ERROR"
                  ? "检测执行失败"
                  : i.result === "REVIEW"
                    ? "证据不足，未能明确判定"
                    : "检测完成"
              }}
            </td>
            <td class="action-cell">
              <div class="row-actions">
                <RouterLink
                  class="table-action"
                  :to="{
                    name: 'inspection',
                    params: { id: i.id },
                  }"
                  >查看详情</RouterLink
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
